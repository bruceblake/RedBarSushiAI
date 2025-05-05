"""
Agent orchestration utilities for RedBarSushiAI.
This module provides tools for advanced agentic patterns including
sequential handoffs, background escalation, and state-machine slot filling.
"""

import os
import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable, TypedDict
from enum import Enum
import yaml
import redis
import uuid
from datetime import datetime
import traceback

from app.utils.monitoring import log_with_context
from app.utils.agent_monitoring import log_agent_call, log_tool_call
from app.utils.conversation_store_sdk import agents_conversation_store

# Configure logging
logger = logging.getLogger(__name__)

def log_orchestration_event(level, message, context=None, call_sid=None, phase=None):
    """
    Enhanced logging for agent orchestration with consistent formatting.
    
    Args:
        level: Log level (debug, info, warning, error, critical)
        message: The message to log
        context: Additional context as dictionary
        call_sid: Optional call SID for tracking
        phase: Optional phase tag (GRAPH, FSM, SLOT, ESCALATION)
    """
    prefix = "[ORCH"
    if phase:
        prefix += f"_{phase}"
    prefix += "]"
    
    full_message = f"{prefix} {message}"
    
    log_context = context or {}
    if call_sid:
        log_context["call_sid"] = call_sid
    
    # Add timestamp for performance tracking
    log_context["timestamp"] = time.time()
    
    if level == "debug":
        logger.debug(full_message, extra={"context": log_context})
    elif level == "info":
        logger.info(full_message, extra={"context": log_context})
    elif level == "warning":
        logger.warning(full_message, extra={"context": log_context})
    elif level == "error":
        logger.error(full_message, extra={"context": log_context})
    elif level == "critical":
        logger.critical(full_message, extra={"context": log_context})
    else:
        logger.info(full_message, extra={"context": log_context})

# Type definitions
class AgentNode(TypedDict):
    name: str
    model: Optional[str]
    description: Optional[str]
    escalation_model: Optional[str]
    confidence_threshold: Optional[float]

class TransitionCondition(TypedDict):
    type: str  # 'slot_filled', 'tool_result', 'confidence', 'default'
    slot: Optional[str]
    value: Optional[Any]
    tool: Optional[str]
    field: Optional[str]
    comparison: Optional[str]  # 'eq', 'neq', 'gt', 'lt', 'contains'

class AgentTransition(TypedDict):
    from_agent: str
    to_agent: str
    condition: Optional[TransitionCondition]
    description: Optional[str]

class AgentGraph:
    """
    A directed acyclic graph (DAG) of agents with conditional transitions.
    Enables sequential agent handoffs and orchestration.
    """
    
    def __init__(self, graph_path: Optional[str] = None):
        """
        Initialize the agent graph.
        
        Args:
            graph_path: Optional path to a YAML/JSON file defining the graph
        """
        start_time = time.time()
        log_orchestration_event("debug", "Initializing agent graph", 
                               {"graph_path": graph_path if graph_path else "None"},
                               phase="GRAPH")
                               
        self.nodes: Dict[str, AgentNode] = {}
        self.transitions: List[AgentTransition] = []
        
        if graph_path:
            self.load_graph(graph_path)
            
        elapsed = time.time() - start_time
        log_orchestration_event("debug", f"Agent graph initialization completed in {elapsed:.3f}s", 
                               {"node_count": len(self.nodes), 
                                "transition_count": len(self.transitions)},
                               phase="GRAPH")
    
    def load_graph(self, path: str) -> None:
        """
        Load an agent graph definition from a file.
        
        Args:
            path: Path to a YAML/JSON file defining the graph
        """
        start_time = time.time()
        log_orchestration_event("info", f"Loading agent graph from {path}", 
                               {"path": path, "format": "yaml" if path.endswith(('.yaml', '.yml')) else "json"},
                               phase="GRAPH")
        try:
            with open(path, 'r') as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    graph_def = yaml.safe_load(f)
                    file_format = "YAML"
                else:
                    graph_def = json.load(f)
                    file_format = "JSON"
            
            # Log the graph structure for debugging
            log_orchestration_event("debug", f"Loaded {file_format} graph definition", 
                                   {"node_count": len(graph_def.get('nodes', [])),
                                    "transition_count": len(graph_def.get('transitions', []))},
                                   phase="GRAPH")
            
            # Load nodes
            self.nodes = {node['name']: node for node in graph_def.get('nodes', [])}
            
            # Load transitions
            self.transitions = graph_def.get('transitions', [])
            
            # Log individual node and transition details for debugging
            for node_name, node in self.nodes.items():
                log_orchestration_event("debug", f"Loaded node: {node_name}", 
                                       {"model": node.get('model', 'default'),
                                        "description": node.get('description', 'No description')},
                                       phase="GRAPH")
            
            for idx, transition in enumerate(self.transitions):
                log_orchestration_event("debug", f"Loaded transition {idx+1}: {transition.get('from_agent')} → {transition.get('to_agent')}", 
                                       {"description": transition.get('description', 'No description'),
                                        "has_condition": 'condition' in transition},
                                       phase="GRAPH")
            
            elapsed = time.time() - start_time
            log_orchestration_event("info", f"Successfully loaded agent graph with {len(self.nodes)} nodes and {len(self.transitions)} transitions in {elapsed:.3f}s", 
                                   {"node_count": len(self.nodes), 
                                    "transition_count": len(self.transitions)},
                                   phase="GRAPH")
        except Exception as e:
            error_details = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "path": path
            }
            log_orchestration_event("error", f"Error loading agent graph from {path}: {str(e)}", 
                                   error_details,
                                   phase="GRAPH")
            raise
    
    def add_node(self, name: str, **node_props) -> None:
        """
        Add a node to the graph.
        
        Args:
            name: The name of the agent node
            **node_props: Additional properties for the node
        """
        log_orchestration_event("info", f"Adding agent node: {name}", 
                               {"name": name, 
                                "model": node_props.get('model', 'default'),
                                "properties": str(list(node_props.keys()))},
                               phase="GRAPH")
                               
        self.nodes[name] = {
            'name': name,
            **node_props
        }
        
        log_orchestration_event("debug", f"Successfully added agent node: {name}", 
                               {"node_count": len(self.nodes)},
                               phase="GRAPH")
    
    def add_transition(
        self, 
        from_agent: str, 
        to_agent: str, 
        condition: Optional[TransitionCondition] = None,
        description: Optional[str] = None
    ) -> None:
        """
        Add a transition to the graph.
        
        Args:
            from_agent: The source agent
            to_agent: The destination agent
            condition: Optional transition condition
            description: Optional description of the transition
        """
        # Log detailed info about the transition being added
        condition_type = condition.get('type') if condition else "None"
        transition_details = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "condition_type": condition_type,
            "description": description or "No description"
        }
        
        # Add more details based on condition type
        if condition:
            transition_details["condition_details"] = str(condition)
            
        log_orchestration_event("info", f"Adding transition: {from_agent} → {to_agent}", 
                               transition_details,
                               phase="GRAPH")
        
        transition = {
            'from_agent': from_agent,
            'to_agent': to_agent
        }
        
        if condition:
            transition['condition'] = condition
        
        if description:
            transition['description'] = description
        
        self.transitions.append(transition)
        
        log_orchestration_event("debug", f"Successfully added transition: {from_agent} → {to_agent}", 
                               {"transition_count": len(self.transitions)},
                               phase="GRAPH")
    
    def get_next_agent(
        self, 
        current_agent: str, 
        state: Dict[str, Any],
        call_sid: Optional[str] = None
    ) -> Optional[str]:
        """
        Determine the next agent based on the current agent and state.
        
        Args:
            current_agent: The current agent
            state: The current conversation state
            call_sid: Optional call SID for tracking
            
        Returns:
            The next agent or None if no transition is applicable
        """
        start_time = time.time()
        
        # Log at start of agent selection
        log_orchestration_event("info", f"Finding next agent from {current_agent}", 
                              {"current_agent": current_agent,
                               "state_keys": list(state.keys()) if state else []},
                              call_sid=call_sid,
                              phase="GRAPH")
        
        # Filter transitions from the current agent
        possible_transitions = [
            t for t in self.transitions if t['from_agent'] == current_agent
        ]
        
        # Log possible transitions for debugging
        log_orchestration_event("debug", f"Found {len(possible_transitions)} possible transitions from {current_agent}", 
                              {"transition_count": len(possible_transitions),
                               "transitions": [f"{t.get('from_agent')} → {t.get('to_agent')}" for t in possible_transitions]},
                              call_sid=call_sid,
                              phase="GRAPH")
        
        # Check conditions to find valid transitions
        transition_results = []
        for idx, transition in enumerate(possible_transitions):
            transition_start = time.time()
            result = self._check_transition_condition(transition, state, call_sid)
            transition_elapsed = time.time() - transition_start
            
            transition_data = {
                "index": idx,
                "from": transition['from_agent'],
                "to": transition['to_agent'],
                "satisfied": result,
                "time_ms": transition_elapsed * 1000,
                "description": transition.get('description', 'No description')
            }
            transition_results.append(transition_data)
            
            if result:
                log_orchestration_event("info", f"Selected transition: {current_agent} → {transition['to_agent']}", 
                                      {"transition": transition_data,
                                       "elapsed_ms": transition_elapsed * 1000},
                                      call_sid=call_sid,
                                      phase="GRAPH")
                
                elapsed = time.time() - start_time
                log_orchestration_event("debug", f"Agent selection completed in {elapsed:.3f}s", 
                                      {"elapsed_ms": elapsed * 1000},
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return transition['to_agent']
        
        # If no transitions match, return None
        elapsed = time.time() - start_time
        log_orchestration_event("warning", f"No valid transitions from {current_agent}", 
                              {"elapsed_ms": elapsed * 1000,
                               "checked_transitions": transition_results},
                              call_sid=call_sid,
                              phase="GRAPH")
        return None
    
    def _check_transition_condition(
        self, 
        transition: AgentTransition, 
        state: Dict[str, Any],
        call_sid: Optional[str] = None
    ) -> bool:
        """
        Check if a transition condition is satisfied.
        
        Args:
            transition: The transition to check
            state: The current conversation state
            call_sid: Optional call SID for tracking
            
        Returns:
            True if the condition is satisfied, False otherwise
        """
        # For debug logging
        transition_debug = {
            "from": transition.get('from_agent'),
            "to": transition.get('to_agent'),
            "description": transition.get('description', 'No description')
        }
        
        # If no condition, transition is always valid
        if 'condition' not in transition:
            log_orchestration_event("debug", "Transition has no condition, automatically satisfied", 
                                  transition_debug,
                                  call_sid=call_sid,
                                  phase="GRAPH")
            return True
        
        condition = transition['condition']
        condition_type = condition.get('type')
        
        # Add condition details to debug info
        transition_debug["condition_type"] = condition_type
        transition_debug["condition"] = condition
        
        try:
            # Different condition types
            if condition_type == 'slot_filled':
                # Check if a slot has been filled
                slot = condition.get('slot')
                transition_debug["slot"] = slot
                transition_debug["slots_in_state"] = list(state.get('slots', {}).keys())
                
                result = slot in state.get('slots', {})
                
                log_orchestration_event("debug", f"Checking slot_filled condition for slot '{slot}': {result}", 
                                      transition_debug,
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return result
            
            elif condition_type == 'slot_value':
                # Check if a slot has a specific value
                slot = condition.get('slot')
                value = condition.get('value')
                transition_debug["slot"] = slot
                transition_debug["expected_value"] = value
                
                actual_value = state.get('slots', {}).get(slot)
                transition_debug["actual_value"] = actual_value
                
                result = actual_value == value
                
                log_orchestration_event("debug", f"Checking slot_value condition for slot '{slot}': {result}", 
                                      transition_debug,
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return result
            
            elif condition_type == 'tool_result':
                # Check a field in the result of a tool call
                tool = condition.get('tool')
                field = condition.get('field')
                value = condition.get('value')
                comparison = condition.get('comparison', 'eq')
                
                transition_debug["tool"] = tool
                transition_debug["field"] = field
                transition_debug["expected_value"] = value
                transition_debug["comparison"] = comparison
                
                tool_results = state.get('tool_results', {})
                if tool not in tool_results:
                    log_orchestration_event("debug", f"Tool '{tool}' not found in tool_results", 
                                          transition_debug,
                                          call_sid=call_sid,
                                          phase="GRAPH")
                    return False
                
                result = tool_results[tool]
                if field not in result:
                    log_orchestration_event("debug", f"Field '{field}' not found in tool result", 
                                          transition_debug,
                                          call_sid=call_sid,
                                          phase="GRAPH")
                    return False
                
                actual_value = result[field]
                transition_debug["actual_value"] = actual_value
                
                # Perform comparison
                if comparison == 'eq':
                    result = actual_value == value
                elif comparison == 'neq':
                    result = actual_value != value
                elif comparison == 'gt':
                    result = actual_value > value
                elif comparison == 'lt':
                    result = actual_value < value
                elif comparison == 'contains':
                    result = value in actual_value
                else:
                    result = False
                
                log_orchestration_event("debug", f"Checking tool_result condition for tool '{tool}', field '{field}', comparison '{comparison}': {result}", 
                                      transition_debug,
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return result
            
            elif condition_type == 'confidence':
                # Check if confidence is above/below threshold
                threshold = condition.get('value', 0.7)
                comparison = condition.get('comparison', 'lt')
                
                transition_debug["threshold"] = threshold
                transition_debug["comparison"] = comparison
                
                confidence = state.get('last_confidence', 1.0)
                transition_debug["actual_confidence"] = confidence
                
                if comparison == 'lt':
                    result = confidence < threshold
                elif comparison == 'gt':
                    result = confidence > threshold
                else:
                    result = False
                
                log_orchestration_event("debug", f"Checking confidence condition ({comparison} {threshold}): {result}", 
                                      transition_debug,
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return result
            
            elif condition_type == 'default':
                # Default transition if no other conditions match
                log_orchestration_event("debug", "Default condition, automatically satisfied", 
                                      transition_debug,
                                      call_sid=call_sid,
                                      phase="GRAPH")
                return True
            
            # Unknown condition type
            log_orchestration_event("warning", f"Unknown condition type: {condition_type}", 
                                  transition_debug,
                                  call_sid=call_sid,
                                  phase="GRAPH")
            return False
            
        except Exception as e:
            error_details = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                **transition_debug
            }
            log_orchestration_event("error", f"Error checking transition condition: {str(e)}", 
                                   error_details,
                                   call_sid=call_sid,
                                   phase="GRAPH")
            return False


class FSMState(Enum):
    """States for the finite state machine."""
    INITIAL = "initial"
    ASK_NAME = "ask_name"
    CONFIRM_NAME = "confirm_name"
    ASK_PHONE = "ask_phone"
    CONFIRM_PHONE = "confirm_phone"
    ASK_DIGIT = "ask_digit"
    CONFIRM_DIGIT = "confirm_digit"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


class SlotStore:
    """
    Store for slots (key-value pairs) in Redis.
    Used for tracking state in the state machine.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the slot store.
        
        Args:
            redis_client: Optional Redis client
        """
        start_time = time.time()
        using_redis = redis_client is not None
        
        log_orchestration_event("info", f"Initializing SlotStore {'with Redis' if using_redis else 'with local storage only'}", 
                               {"has_redis": using_redis},
                               phase="SLOT")
        
        self.redis = redis_client
        self.local_store = {}
        
        elapsed = time.time() - start_time
        log_orchestration_event("debug", f"SlotStore initialization completed in {elapsed:.3f}s", 
                               {"has_redis": using_redis},
                               phase="SLOT")
    
    def get_slot(self, call_sid: str, slot_name: str) -> Any:
        """
        Get a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            
        Returns:
            The slot value or None if not found
        """
        start_time = time.time()
        
        log_orchestration_event("debug", f"Getting slot '{slot_name}' for call {call_sid}", 
                               {"slot_name": slot_name, "call_sid": call_sid},
                               call_sid=call_sid,
                               phase="SLOT")
        
        if self.redis:
            try:
                slot_key = f"slot:{call_sid}:{slot_name}"
                log_orchestration_event("debug", f"Retrieving from Redis key '{slot_key}'", 
                                       {"key": slot_key},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                value = self.redis.get(slot_key)
                if value:
                    try:
                        parsed_value = json.loads(value)
                        
                        # Create a safe value for logging that won't expose sensitive data
                        log_value = parsed_value
                        if slot_name in ["phone", "phone_raw", "credit_card", "payment_info"]:
                            log_value = "[REDACTED]"
                        elif isinstance(parsed_value, str) and len(parsed_value) > 100:
                            log_value = f"{parsed_value[:50]}... [truncated, total length: {len(parsed_value)}]"
                        
                        elapsed = time.time() - start_time
                        log_orchestration_event("debug", f"Successfully retrieved slot '{slot_name}' from Redis in {elapsed:.3f}s", 
                                               {"value_type": type(parsed_value).__name__, 
                                                "value_summary": str(log_value)[:50] if isinstance(log_value, str) else log_value,
                                                "elapsed_ms": elapsed * 1000},
                                               call_sid=call_sid,
                                               phase="SLOT")
                        
                        return parsed_value
                    except json.JSONDecodeError as json_err:
                        log_orchestration_event("warning", f"Error decoding JSON for slot '{slot_name}': {str(json_err)}", 
                                              {"raw_value": str(value)[:100]},
                                              call_sid=call_sid,
                                              phase="SLOT")
                
                # If we get here, the value was None or failed to parse
                log_orchestration_event("debug", f"Slot '{slot_name}' not found in Redis", 
                                       {},
                                       call_sid=call_sid,
                                       phase="SLOT")
                return None
            except Exception as e:
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "slot_name": slot_name,
                    "call_sid": call_sid
                }
                log_orchestration_event("error", f"Error getting slot from Redis: {str(e)}", 
                                       error_details,
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                # Fall back to local store
                log_orchestration_event("warning", "Falling back to local store due to Redis error", 
                                       {},
                                       call_sid=call_sid,
                                       phase="SLOT")
        else:
            log_orchestration_event("debug", "No Redis client, using local store", 
                                   {},
                                   call_sid=call_sid,
                                   phase="SLOT")
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        value = self.local_store.get(store_key, {}).get(slot_name)
        
        # Create a safe value for logging
        log_value = value
        if slot_name in ["phone", "phone_raw", "credit_card", "payment_info"]:
            log_value = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 100:
            log_value = f"{value[:50]}... [truncated, total length: {len(value)}]"
        
        elapsed = time.time() - start_time
        if value is not None:
            log_orchestration_event("debug", f"Retrieved slot '{slot_name}' from local store in {elapsed:.3f}s", 
                                   {"value_type": type(value).__name__, 
                                    "value_summary": str(log_value)[:50] if isinstance(log_value, str) else log_value,
                                    "elapsed_ms": elapsed * 1000},
                                   call_sid=call_sid,
                                   phase="SLOT")
        else:
            log_orchestration_event("debug", f"Slot '{slot_name}' not found in local store", 
                                   {"elapsed_ms": elapsed * 1000},
                                   call_sid=call_sid,
                                   phase="SLOT")
        
        return value
    
    def set_slot(self, call_sid: str, slot_name: str, value: Any) -> None:
        """
        Set a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            value: The value to set
        """
        start_time = time.time()
        
        # Create a safe value for logging
        log_value = value
        if slot_name in ["phone", "phone_raw", "credit_card", "payment_info"]:
            log_value = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 100:
            log_value = f"{value[:50]}... [truncated, total length: {len(value)}]"
        
        log_orchestration_event("info", f"Setting slot '{slot_name}' for call {call_sid}", 
                               {"slot_name": slot_name, 
                                "call_sid": call_sid, 
                                "value_type": type(value).__name__,
                                "value_summary": str(log_value)[:50] if isinstance(log_value, str) else log_value},
                               call_sid=call_sid,
                               phase="SLOT")
        
        if self.redis:
            try:
                slot_key = f"slot:{call_sid}:{slot_name}"
                serialized_value = json.dumps(value)
                
                log_orchestration_event("debug", f"Storing in Redis key '{slot_key}'", 
                                       {"key": slot_key, "serialized_size": len(serialized_value)},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                self.redis.set(slot_key, serialized_value)
                # Also set a TTL (2 hours)
                self.redis.expire(slot_key, 7200)
                
                elapsed = time.time() - start_time
                log_orchestration_event("debug", f"Successfully stored slot in Redis in {elapsed:.3f}s", 
                                       {"elapsed_ms": elapsed * 1000},
                                       call_sid=call_sid,
                                       phase="SLOT")
                return
            except Exception as e:
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "slot_name": slot_name,
                    "call_sid": call_sid,
                    "value_type": type(value).__name__
                }
                log_orchestration_event("error", f"Error setting slot in Redis: {str(e)}", 
                                       error_details,
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                # Fall back to local store
                log_orchestration_event("warning", "Falling back to local store due to Redis error", 
                                       {},
                                       call_sid=call_sid,
                                       phase="SLOT")
        else:
            log_orchestration_event("debug", "No Redis client, using local store", 
                                   {},
                                   call_sid=call_sid,
                                   phase="SLOT")
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        if store_key not in self.local_store:
            self.local_store[store_key] = {}
        self.local_store[store_key][slot_name] = value
        
        elapsed = time.time() - start_time
        log_orchestration_event("debug", f"Successfully stored slot in local store in {elapsed:.3f}s", 
                               {"elapsed_ms": elapsed * 1000, "store_key": store_key},
                               call_sid=call_sid,
                               phase="SLOT")
    
    def get_all_slots(self, call_sid: str) -> Dict[str, Any]:
        """
        Get all slots for a call.
        
        Args:
            call_sid: The call SID
            
        Returns:
            Dictionary of all slots
        """
        start_time = time.time()
        
        log_orchestration_event("info", f"Getting all slots for call {call_sid}", 
                               {"call_sid": call_sid},
                               call_sid=call_sid,
                               phase="SLOT")
        
        if self.redis:
            try:
                # Get all keys for this call
                pattern = f"slot:{call_sid}:*"
                
                log_orchestration_event("debug", f"Searching Redis with pattern '{pattern}'", 
                                       {"pattern": pattern},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                keys = self.redis.keys(pattern)
                
                log_orchestration_event("debug", f"Found {len(keys) if keys else 0} slot keys in Redis", 
                                       {"key_count": len(keys) if keys else 0},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                # Get all values
                result = {}
                for key in keys:
                    # Extract slot name from key
                    slot_name = key.decode('utf-8').split(':')[-1]
                    value = self.redis.get(key)
                    if value:
                        try:
                            result[slot_name] = json.loads(value)
                        except json.JSONDecodeError as e:
                            log_orchestration_event("warning", f"Failed to decode slot value for '{slot_name}': {str(e)}", 
                                                   {"key": key.decode('utf-8'), "raw_value": value.decode('utf-8')[:50]},
                                                   call_sid=call_sid,
                                                   phase="SLOT")
                
                elapsed = time.time() - start_time
                
                # Create a safe summary for logging (exclude sensitive fields)
                safe_keys = set(result.keys())
                sensitive_keys = {"phone", "phone_raw", "credit_card", "payment_info"}
                safe_keys_list = list(safe_keys - sensitive_keys)
                
                log_orchestration_event("info", f"Successfully retrieved {len(result)} slots from Redis in {elapsed:.3f}s", 
                                       {"slot_count": len(result), 
                                        "elapsed_ms": elapsed * 1000,
                                        "slot_names": safe_keys_list},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                return result
            except Exception as e:
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "call_sid": call_sid
                }
                log_orchestration_event("error", f"Error getting all slots from Redis: {str(e)}", 
                                       error_details,
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                # Fall back to local store
                log_orchestration_event("warning", "Falling back to local store due to Redis error", 
                                       {},
                                       call_sid=call_sid,
                                       phase="SLOT")
        else:
            log_orchestration_event("debug", "No Redis client, using local store", 
                                   {},
                                   call_sid=call_sid,
                                   phase="SLOT")
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        result = self.local_store.get(store_key, {})
        
        elapsed = time.time() - start_time
        
        # Create a safe summary for logging (exclude sensitive fields)
        safe_keys = set(result.keys())
        sensitive_keys = {"phone", "phone_raw", "credit_card", "payment_info"}
        safe_keys_list = list(safe_keys - sensitive_keys)
        
        log_orchestration_event("info", f"Retrieved {len(result)} slots from local store in {elapsed:.3f}s", 
                               {"slot_count": len(result), 
                                "elapsed_ms": elapsed * 1000,
                                "slot_names": safe_keys_list},
                               call_sid=call_sid,
                               phase="SLOT")
        
        return result
    
    def clear_slots(self, call_sid: str) -> None:
        """
        Clear all slots for a call.
        
        Args:
            call_sid: The call SID
        """
        start_time = time.time()
        
        log_orchestration_event("info", f"Clearing all slots for call {call_sid}", 
                               {"call_sid": call_sid},
                               call_sid=call_sid,
                               phase="SLOT")
        
        if self.redis:
            try:
                # Delete all keys for this call
                pattern = f"slot:{call_sid}:*"
                
                log_orchestration_event("debug", f"Searching Redis with pattern '{pattern}'", 
                                       {"pattern": pattern},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                keys = self.redis.keys(pattern)
                
                log_orchestration_event("debug", f"Found {len(keys) if keys else 0} slot keys to delete in Redis", 
                                       {"key_count": len(keys) if keys else 0},
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                if keys:
                    self.redis.delete(*keys)
                    
                elapsed = time.time() - start_time
                log_orchestration_event("info", f"Successfully cleared {len(keys) if keys else 0} slots from Redis in {elapsed:.3f}s", 
                                       {"key_count": len(keys) if keys else 0, "elapsed_ms": elapsed * 1000},
                                       call_sid=call_sid,
                                       phase="SLOT")
                return
            except Exception as e:
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "call_sid": call_sid
                }
                log_orchestration_event("error", f"Error clearing slots from Redis: {str(e)}", 
                                       error_details,
                                       call_sid=call_sid,
                                       phase="SLOT")
                
                # Fall back to local store
                log_orchestration_event("warning", "Falling back to local store due to Redis error", 
                                       {},
                                       call_sid=call_sid,
                                       phase="SLOT")
        else:
            log_orchestration_event("debug", "No Redis client, using local store", 
                                   {},
                                   call_sid=call_sid,
                                   phase="SLOT")
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        slot_count = len(self.local_store.get(store_key, {}))
        
        if store_key in self.local_store:
            del self.local_store[store_key]
        
        elapsed = time.time() - start_time
        log_orchestration_event("info", f"Cleared {slot_count} slots from local store in {elapsed:.3f}s", 
                               {"slot_count": slot_count, "elapsed_ms": elapsed * 1000},
                               call_sid=call_sid,
                               phase="SLOT")


class FSMPromptTemplate:
    """
    Prompt template for state machine-based dialogues.
    Generates prompts based on the current state and slots.
    """
    
    def __init__(self, template_path: Optional[str] = None):
        """
        Initialize the prompt template.
        
        Args:
            template_path: Optional path to a YAML file defining the templates
        """
        self.templates = {}
        
        if template_path:
            self.load_templates(template_path)
    
    def load_templates(self, path: str) -> None:
        """
        Load templates from a file.
        
        Args:
            path: Path to a YAML file defining the templates
        """
        try:
            with open(path, 'r') as f:
                self.templates = yaml.safe_load(f)
            
            logger.info(f"Loaded {len(self.templates)} prompt templates")
        except Exception as e:
            logger.error(f"Error loading prompt templates from {path}: {str(e)}")
            raise
    
    def get_template(self, state: str) -> Dict[str, str]:
        """
        Get the template for a state.
        
        Args:
            state: The state name
            
        Returns:
            Template dictionary with 'system' and 'user' fields
        """
        if state in self.templates:
            return self.templates[state]
        else:
            logger.warning(f"No template found for state: {state}")
            return {
                "system": "You are an assistant helping with authentication.",
                "user": "Please help me authenticate."
            }
    
    def apply_template(
        self, 
        state: str, 
        slots: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, str]:
        """
        Apply a template with slot values.
        
        Args:
            state: The state name
            slots: The current slot values
            retry_count: The number of retries for this state
            
        Returns:
            Dictionary with 'system' and 'user' prompts
        """
        template = self.get_template(state)
        
        # Add retry information to slots
        slots_with_retry = {**slots, "retry_count": retry_count}
        
        # Apply template substitution for system prompt
        system_prompt = template.get("system", "")
        for key, value in slots_with_retry.items():
            placeholder = f"{{{key}}}"
            if placeholder in system_prompt:
                system_prompt = system_prompt.replace(placeholder, str(value))
        
        # Apply template substitution for user prompt
        user_prompt = template.get("user", "")
        for key, value in slots_with_retry.items():
            placeholder = f"{{{key}}}"
            if placeholder in user_prompt:
                user_prompt = user_prompt.replace(placeholder, str(value))
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }


class FSMOrchestrator:
    """
    Finite State Machine (FSM) orchestrator for authentication and slot filling.
    Manages state transitions and slot values.
    """
    
    def __init__(
        self, 
        slot_store: Optional[SlotStore] = None,
        template_path: Optional[str] = None
    ):
        """
        Initialize the FSM orchestrator.
        
        Args:
            slot_store: Optional slot store
            template_path: Optional path to prompt templates
        """
        self.slot_store = slot_store or SlotStore()
        self.templates = FSMPromptTemplate(template_path)
        
        # Default state transitions
        self.transitions = {
            FSMState.INITIAL: {
                "next": FSMState.ASK_NAME
            },
            FSMState.ASK_NAME: {
                "has_input": FSMState.CONFIRM_NAME
            },
            FSMState.CONFIRM_NAME: {
                "yes": FSMState.ASK_PHONE,
                "no": FSMState.ASK_NAME,
                "retries_exceeded": FSMState.FAILED
            },
            FSMState.ASK_PHONE: {
                "has_input": FSMState.CONFIRM_PHONE,
                "digit_by_digit": FSMState.ASK_DIGIT
            },
            FSMState.CONFIRM_PHONE: {
                "yes": FSMState.AUTHENTICATED,
                "no": FSMState.ASK_PHONE,
                "retries_exceeded": FSMState.FAILED
            },
            FSMState.ASK_DIGIT: {
                "has_input": FSMState.CONFIRM_DIGIT,
                "all_digits_collected": FSMState.CONFIRM_PHONE
            },
            FSMState.CONFIRM_DIGIT: {
                "yes": FSMState.ASK_DIGIT,
                "no": FSMState.ASK_DIGIT,
                "all_digits_confirmed": FSMState.CONFIRM_PHONE,
                "retries_exceeded": FSMState.FAILED
            },
            FSMState.AUTHENTICATED: {},
            FSMState.FAILED: {}
        }
    
    def get_current_state(self, call_sid: str) -> FSMState:
        """
        Get the current state for a call.
        
        Args:
            call_sid: The call SID
            
        Returns:
            The current state
        """
        state_str = self.slot_store.get_slot(call_sid, "current_state")
        if state_str:
            try:
                return FSMState(state_str)
            except ValueError:
                logger.warning(f"Invalid state value: {state_str}")
        
        # Default to initial state
        return FSMState.INITIAL
    
    def set_current_state(self, call_sid: str, state: FSMState) -> None:
        """
        Set the current state for a call.
        
        Args:
            call_sid: The call SID
            state: The state to set
        """
        self.slot_store.set_slot(call_sid, "current_state", state.value)
        
        # Also store the retry count for this state
        retry_key = f"retry_{state.value}"
        retry_count = self.slot_store.get_slot(call_sid, retry_key) or 0
        self.slot_store.set_slot(call_sid, retry_key, retry_count + 1)
        
        # Log the state change
        log_with_context(
            "info",
            f"State change: {state.value}",
            {
                "call_sid": call_sid,
                "state": state.value,
                "retry_count": retry_count + 1
            }
        )
    
    def get_retry_count(self, call_sid: str, state: FSMState) -> int:
        """
        Get the retry count for a state.
        
        Args:
            call_sid: The call SID
            state: The state
            
        Returns:
            The retry count
        """
        retry_key = f"retry_{state.value}"
        return self.slot_store.get_slot(call_sid, retry_key) or 0
    
    def set_slot(self, call_sid: str, slot_name: str, value: Any) -> None:
        """
        Set a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            value: The value to set
        """
        self.slot_store.set_slot(call_sid, slot_name, value)
        
        # Log the slot update
        log_with_context(
            "info",
            f"Slot update: {slot_name}={value}",
            {
                "call_sid": call_sid,
                "slot_name": slot_name,
                "slot_value": value
            }
        )
    
    def get_slot(self, call_sid: str, slot_name: str) -> Any:
        """
        Get a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            
        Returns:
            The slot value
        """
        return self.slot_store.get_slot(call_sid, slot_name)
    
    def get_next_state(
        self, 
        call_sid: str, 
        transition_key: str
    ) -> Optional[FSMState]:
        """
        Get the next state based on a transition key.
        
        Args:
            call_sid: The call SID
            transition_key: The transition key
            
        Returns:
            The next state or None if no transition is applicable
        """
        current_state = self.get_current_state(call_sid)
        
        # Get transitions for the current state
        state_transitions = self.transitions.get(current_state, {})
        
        # Check if transition key exists
        if transition_key in state_transitions:
            return state_transitions[transition_key]
        
        # Check for retry_exceeded transition
        retry_count = self.get_retry_count(call_sid, current_state)
        if retry_count >= 3 and "retries_exceeded" in state_transitions:
            return state_transitions["retries_exceeded"]
        
        # No applicable transition
        return None
    
    def process_user_input(
        self, 
        call_sid: str,
        user_input: str,
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Process user input and transition to the next state.
        
        Args:
            call_sid: The call SID
            user_input: The user's input
            confidence: The confidence score (0-1)
            
        Returns:
            The next prompt to send to the agent
        """
        current_state = self.get_current_state(call_sid)
        
        # Process input based on current state
        if current_state == FSMState.ASK_NAME:
            # Store the raw name
            self.set_slot(call_sid, "name_raw", user_input)
            # Transition to confirm name
            next_state = FSMState.CONFIRM_NAME
            self.set_current_state(call_sid, next_state)
            
        elif current_state == FSMState.CONFIRM_NAME:
            # Check confirmation
            if user_input.lower() in ["yes", "yeah", "correct", "that's right", "right", "yep", "yup", "true"]:
                # Confirmed, transition to ask phone
                next_state = FSMState.ASK_PHONE
                # Store the confirmed name
                confirmed_name = self.get_slot(call_sid, "name_raw")
                self.set_slot(call_sid, "name", confirmed_name)
            else:
                # Not confirmed, go back to ask name
                next_state = FSMState.ASK_NAME
            
            self.set_current_state(call_sid, next_state)
            
        elif current_state == FSMState.ASK_PHONE:
            # Store the raw phone number
            self.set_slot(call_sid, "phone_raw", user_input)
            # Transition to confirm phone
            next_state = FSMState.CONFIRM_PHONE
            self.set_current_state(call_sid, next_state)
            
        elif current_state == FSMState.CONFIRM_PHONE:
            # Check confirmation
            if user_input.lower() in ["yes", "yeah", "correct", "that's right", "right", "yep", "yup", "true"]:
                # Confirmed, transition to authenticated
                next_state = FSMState.AUTHENTICATED
                # Store the confirmed phone
                confirmed_phone = self.get_slot(call_sid, "phone_raw")
                self.set_slot(call_sid, "phone", confirmed_phone)
                self.set_slot(call_sid, "authenticated", True)
            else:
                # Not confirmed, go back to ask phone
                next_state = FSMState.ASK_PHONE
            
            self.set_current_state(call_sid, next_state)
            
        elif current_state == FSMState.ASK_DIGIT:
            # Store the current digit
            current_index = self.get_slot(call_sid, "current_digit_index") or 0
            digits = self.get_slot(call_sid, "digits") or []
            
            # Extract the digit from input
            digit = self._extract_digit(user_input)
            if digit is not None:
                digits.append(digit)
                self.set_slot(call_sid, "digits", digits)
                
                # Check if we've collected all digits (10 for US phone numbers)
                if len(digits) >= 10:
                    # All digits collected, transition to confirm phone
                    next_state = FSMState.CONFIRM_PHONE
                    # Format the phone number
                    phone = ''.join(str(d) for d in digits)
                    self.set_slot(call_sid, "phone_raw", phone)
                else:
                    # More digits needed, transition to confirm digit
                    next_state = FSMState.CONFIRM_DIGIT
                    self.set_slot(call_sid, "current_digit", digit)
                    self.set_slot(call_sid, "current_digit_index", current_index + 1)
            else:
                # Invalid input, stay in ask_digit state
                next_state = FSMState.ASK_DIGIT
            
            self.set_current_state(call_sid, next_state)
            
        elif current_state == FSMState.CONFIRM_DIGIT:
            # Check confirmation
            if user_input.lower() in ["yes", "yeah", "correct", "that's right", "right", "yep", "yup", "true"]:
                # Digit confirmed, move to next digit
                current_index = self.get_slot(call_sid, "current_digit_index") or 0
                digits = self.get_slot(call_sid, "digits") or []
                
                # Check if we've collected all digits
                if len(digits) >= 10:
                    # All digits collected, transition to confirm phone
                    next_state = FSMState.CONFIRM_PHONE
                    # Format the phone number
                    phone = ''.join(str(d) for d in digits)
                    self.set_slot(call_sid, "phone_raw", phone)
                else:
                    # More digits needed, transition back to ask digit
                    next_state = FSMState.ASK_DIGIT
            else:
                # Digit not confirmed, go back to ask the same digit
                digits = self.get_slot(call_sid, "digits") or []
                if digits:
                    # Remove the last digit
                    digits.pop()
                    self.set_slot(call_sid, "digits", digits)
                
                next_state = FSMState.ASK_DIGIT
            
            self.set_current_state(call_sid, next_state)
            
        else:
            # For other states, default to initial
            next_state = FSMState.INITIAL
            self.set_current_state(call_sid, next_state)
        
        # Get the slots
        slots = self.slot_store.get_all_slots(call_sid)
        
        # Get the retry count for the new state
        retry_count = self.get_retry_count(call_sid, next_state)
        
        # Generate the prompt for the next state
        prompt = self.templates.apply_template(next_state.value, slots, retry_count)
        
        return {
            "state": next_state.value,
            "system_prompt": prompt["system"],
            "user_prompt": prompt["user"],
            "slots": slots
        }
    
    def _extract_digit(self, input_text: str) -> Optional[int]:
        """
        Extract a digit from input text.
        
        Args:
            input_text: The input text
            
        Returns:
            The extracted digit or None if not found
        """
        # Map digit words to numbers
        digit_words = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9
        }
        
        # Check for digit words
        input_lower = input_text.lower()
        for word, digit in digit_words.items():
            if word in input_lower:
                return digit
        
        # Check for actual digits
        for char in input_text:
            if char.isdigit():
                return int(char)
        
        return None


class ModelEscalator:
    """
    Handler for background escalation to stronger models.
    Monitors confidence and triggers escalation when needed.
    """
    
    def __init__(self, custom_tiers: Optional[List[str]] = None):
        """
        Initialize the model escalator.
        
        Args:
            custom_tiers: Optional custom model tier list (weakest to strongest)
        """
        start_time = time.time()
        
        log_orchestration_event("info", "Initializing ModelEscalator", 
                               {"has_custom_tiers": custom_tiers is not None},
                               phase="ESCALATION")
        
        # Default model tiers (weakest to strongest)
        self.default_tiers = [
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o1-mini"
        ]
        
        # Use custom tiers if provided
        self.model_tiers = custom_tiers if custom_tiers else self.default_tiers
        
        log_orchestration_event("debug", "Model tiers configured (weakest to strongest)", 
                               {"model_tiers": self.model_tiers},
                               phase="ESCALATION")
        
        elapsed = time.time() - start_time
        log_orchestration_event("debug", f"ModelEscalator initialization completed in {elapsed:.3f}s", 
                               {"elapsed_ms": elapsed * 1000},
                               phase="ESCALATION")
    
    def should_escalate(
        self, 
        confidence: float,
        current_model: str,
        is_critical: bool = False,
        threshold: float = 0.7,
        call_sid: Optional[str] = None
    ) -> bool:
        """
        Determine if escalation is needed.
        
        Args:
            confidence: The confidence score (0-1)
            current_model: The current model
            is_critical: Whether this is a critical operation
            threshold: The confidence threshold
            call_sid: Optional call SID for tracking
            
        Returns:
            True if escalation is needed, False otherwise
        """
        start_time = time.time()
        
        # Context for logging
        escalation_context = {
            "confidence": confidence,
            "current_model": current_model,
            "is_critical": is_critical,
            "threshold": threshold
        }
        
        log_orchestration_event("info", "Checking if model escalation is needed", 
                               escalation_context,
                               call_sid=call_sid,
                               phase="ESCALATION")
        
        # Adjust threshold for critical operations
        original_threshold = threshold
        if is_critical:
            threshold = max(threshold, 0.8)
            if threshold != original_threshold:
                log_orchestration_event("debug", f"Adjusted threshold from {original_threshold} to {threshold} for critical operation", 
                                       {"original_threshold": original_threshold, "new_threshold": threshold},
                                       call_sid=call_sid,
                                       phase="ESCALATION")
        
        # Check if confidence is below threshold
        if confidence < threshold:
            # Check if we can escalate to a stronger model
            in_tiers = current_model in self.model_tiers
            
            if not in_tiers:
                log_orchestration_event("warning", f"Current model '{current_model}' not found in model tiers", 
                                       {"available_tiers": self.model_tiers},
                                       call_sid=call_sid,
                                       phase="ESCALATION")
                # Can still escalate to the strongest model
                result = True
            else:
                model_index = self.model_tiers.index(current_model)
                has_stronger = model_index < len(self.model_tiers) - 1
                
                if has_stronger:
                    next_model = self.model_tiers[model_index + 1]
                    log_orchestration_event("info", f"Confidence {confidence} below threshold {threshold}, can escalate to {next_model}", 
                                           {"next_model": next_model, "current_index": model_index},
                                           call_sid=call_sid,
                                           phase="ESCALATION")
                else:
                    log_orchestration_event("info", f"Confidence {confidence} below threshold {threshold}, but already at strongest model", 
                                           {"current_index": model_index, "is_strongest": True},
                                           call_sid=call_sid,
                                           phase="ESCALATION")
                
                result = has_stronger
        else:
            log_orchestration_event("info", f"Confidence {confidence} above threshold {threshold}, no escalation needed", 
                                   {},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            result = False
        
        elapsed = time.time() - start_time
        log_orchestration_event("debug", f"Escalation check completed in {elapsed:.3f}s: {result}", 
                               {"should_escalate": result, "elapsed_ms": elapsed * 1000},
                               call_sid=call_sid,
                               phase="ESCALATION")
        
        return result
    
    def get_escalation_model(self, current_model: str, call_sid: Optional[str] = None) -> str:
        """
        Get the next stronger model.
        
        Args:
            current_model: The current model
            call_sid: Optional call SID for tracking
            
        Returns:
            The next stronger model
        """
        start_time = time.time()
        
        log_orchestration_event("info", f"Finding escalation model for {current_model}", 
                               {"current_model": current_model},
                               call_sid=call_sid,
                               phase="ESCALATION")
        
        if current_model not in self.model_tiers:
            # Default to the strongest model
            strongest_model = self.model_tiers[-1]
            
            log_orchestration_event("warning", f"Model '{current_model}' not in defined tiers, using strongest model {strongest_model}", 
                                   {"strongest_model": strongest_model, "available_tiers": self.model_tiers},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            elapsed = time.time() - start_time
            log_orchestration_event("debug", f"Escalation model selection completed in {elapsed:.3f}s", 
                                   {"elapsed_ms": elapsed * 1000, "selected_model": strongest_model},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            return strongest_model
        
        model_index = self.model_tiers.index(current_model)
        if model_index < len(self.model_tiers) - 1:
            next_model = self.model_tiers[model_index + 1]
            
            log_orchestration_event("info", f"Escalating from tier {model_index} to tier {model_index + 1}: {current_model} → {next_model}", 
                                   {"from_index": model_index, "to_index": model_index + 1,
                                    "from_model": current_model, "to_model": next_model},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            elapsed = time.time() - start_time
            log_orchestration_event("debug", f"Escalation model selection completed in {elapsed:.3f}s", 
                                   {"elapsed_ms": elapsed * 1000, "selected_model": next_model},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            return next_model
        else:
            # Already at the strongest model
            log_orchestration_event("info", f"Already at strongest model tier {model_index}: {current_model}", 
                                   {"current_index": model_index, "is_strongest": True},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            elapsed = time.time() - start_time
            log_orchestration_event("debug", f"Escalation model selection completed in {elapsed:.3f}s", 
                                   {"elapsed_ms": elapsed * 1000, "selected_model": current_model, "unchanged": True},
                                   call_sid=call_sid,
                                   phase="ESCALATION")
            
            return current_model
    
    def escalate_request(
        self,
        original_request: Dict[str, Any],
        current_model: str,
        call_sid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare a request for escalation to a stronger model.
        
        Args:
            original_request: The original request
            current_model: The current model
            call_sid: Optional call SID for tracking
            
        Returns:
            The updated request with the stronger model
        """
        start_time = time.time()
        
        # Log safe request details (excluding any sensitive content)
        safe_request = {
            "has_messages": "messages" in original_request,
            "message_count": len(original_request.get("messages", [])) if "messages" in original_request else 0,
            "has_functions": "functions" in original_request,
            "function_count": len(original_request.get("functions", [])) if "functions" in original_request else 0,
            "current_model": original_request.get("model", current_model)
        }
        
        log_orchestration_event("info", f"Preparing escalation request for {current_model}", 
                               safe_request,
                               call_sid=call_sid,
                               phase="ESCALATION")
        
        # Clone the request
        escalated_request = original_request.copy()
        
        # Get the escalation model
        escalation_model = self.get_escalation_model(current_model, call_sid)
        
        # Update the model in the request
        escalated_request["model"] = escalation_model
        
        # Mark as escalated for tracking
        escalated_request["is_escalated"] = True
        escalated_request["original_model"] = current_model
        
        elapsed = time.time() - start_time
        
        # Log the escalation with both logging systems for redundancy
        escalation_context = {
            "original_model": current_model,
            "escalation_model": escalation_model,
            "elapsed_ms": elapsed * 1000
        }
        
        log_orchestration_event("info", f"Escalation request prepared: {current_model} → {escalation_model}", 
                               escalation_context,
                               call_sid=call_sid,
                               phase="ESCALATION")
        
        # Also log with standard monitoring system
        log_with_context(
            "info",
            f"Escalating from {current_model} to {escalation_model}",
            {
                "original_model": current_model,
                "escalation_model": escalation_model,
                "call_sid": call_sid if call_sid else "unknown"
            }
        )
        
        return escalated_request


# Default agent graph definition
DEFAULT_AGENT_GRAPH = {
    "nodes": [
        {
            "name": "Frontline",
            "model": "gpt-4.1-mini",
            "description": "Primary voice interface agent",
            "escalation_model": "gpt-4o",
            "confidence_threshold": 0.7
        },
        {
            "name": "Authenticator",
            "model": "gpt-4.1-mini",
            "description": "User authentication agent",
            "escalation_model": "gpt-4o",
            "confidence_threshold": 0.8
        },
        {
            "name": "Menu",
            "model": "gpt-4.1-mini",
            "description": "Menu information agent",
            "escalation_model": "gpt-4o",
            "confidence_threshold": 0.7
        },
        {
            "name": "Cart",
            "model": "gpt-4.1-mini",
            "description": "Cart management agent",
            "escalation_model": "gpt-4o",
            "confidence_threshold": 0.7
        },
        {
            "name": "Fulfillment",
            "model": "gpt-4.1-mini",
            "description": "Order fulfillment agent",
            "escalation_model": "gpt-4o-mini",
            "confidence_threshold": 0.8
        },
        {
            "name": "Escalation",
            "model": "gpt-4o-mini",
            "description": "Escalation handler agent",
            "escalation_model": "o1-mini",
            "confidence_threshold": 0.9
        }
    ],
    "transitions": [
        {
            "from_agent": "Frontline",
            "to_agent": "Authenticator",
            "condition": {
                "type": "slot_value",
                "slot": "authenticated",
                "value": False
            },
            "description": "Route to authentication if not authenticated"
        },
        {
            "from_agent": "Authenticator",
            "to_agent": "Frontline",
            "condition": {
                "type": "slot_value",
                "slot": "authenticated",
                "value": True
            },
            "description": "Return to Frontline after successful authentication"
        },
        {
            "from_agent": "Frontline",
            "to_agent": "Menu",
            "condition": {
                "type": "tool_result",
                "tool": "intent_classifier",
                "field": "intent",
                "value": "menu_inquiry"
            },
            "description": "Route to Menu Agent for menu questions"
        },
        {
            "from_agent": "Menu",
            "to_agent": "Frontline",
            "condition": {
                "type": "default"
            },
            "description": "Return to Frontline after menu inquiry"
        },
        {
            "from_agent": "Frontline",
            "to_agent": "Cart",
            "condition": {
                "type": "tool_result",
                "tool": "intent_classifier",
                "field": "intent",
                "value": "place_order"
            },
            "description": "Route to Cart Agent for order placement"
        },
        {
            "from_agent": "Cart",
            "to_agent": "Fulfillment",
            "condition": {
                "type": "slot_value",
                "slot": "cart_ready",
                "value": True
            },
            "description": "Route to Fulfillment when cart is ready"
        },
        {
            "from_agent": "Fulfillment",
            "to_agent": "Frontline",
            "condition": {
                "type": "slot_value",
                "slot": "order_placed",
                "value": True
            },
            "description": "Return to Frontline after order fulfillment"
        },
        {
            "from_agent": "Frontline",
            "to_agent": "Escalation",
            "condition": {
                "type": "confidence",
                "value": 0.6,
                "comparison": "lt"
            },
            "description": "Escalate when confidence is low"
        }
    ]
}

# Default authentication FSM prompt templates
DEFAULT_AUTH_TEMPLATES = {
    "initial": {
        "system": "You are an authentication assistant for Red Bar Sushi. You're in the initial state, about to begin the authentication process.",
        "user": "Hello, I need to verify your identity before we proceed. I'll ask for your name and phone number."
    },
    "ask_name": {
        "system": "You are an authentication assistant. You're in the ask_name state with retry_count {retry_count}. Ask for the customer's name one word at a time.",
        "user": "Please tell me your name, one word at a time."
    },
    "confirm_name": {
        "system": "You are an authentication assistant. You're in the confirm_name state with retry_count {retry_count}. Confirm the name '{name_raw}'.",
        "user": "Did you say '{name_raw}'? Please say yes or no."
    },
    "ask_phone": {
        "system": "You are an authentication assistant. You're in the ask_phone state with retry_count {retry_count}. Ask for the customer's phone number.",
        "user": "Now, please tell me your phone number. I'll confirm each digit as you say it."
    },
    "confirm_phone": {
        "system": "You are an authentication assistant. You're in the confirm_phone state with retry_count {retry_count}. Confirm the phone number '{phone_raw}'.",
        "user": "Did you say '{phone_raw}'? Please say yes or no."
    },
    "ask_digit": {
        "system": "You are an authentication assistant. You're in the ask_digit state with retry_count {retry_count}. Ask for digit {current_digit_index} of their phone number.",
        "user": "Please say digit {current_digit_index} of your phone number."
    },
    "confirm_digit": {
        "system": "You are an authentication assistant. You're in the confirm_digit state with retry_count {retry_count}. Confirm the digit '{current_digit}'.",
        "user": "Did you say '{current_digit}'? Please say yes or no."
    },
    "authenticated": {
        "system": "You are an authentication assistant. You're in the authenticated state. Authentication has succeeded.",
        "user": "Thanks! You've been successfully authenticated. You can now place an order or ask about our menu."
    },
    "failed": {
        "system": "You are an authentication assistant. You're in the failed state. Authentication has failed after multiple attempts.",
        "user": "I'm sorry, but I'm having trouble authenticating you. Let me connect you to a staff member who can help."
    }
}

# Initialize the orchestrators with default configs
def initialize_orchestrators(agent_graph=None, slot_store=None, fsm_orchestrator=None, model_escalator=None):
    """
    Initialize the agent orchestration components.
    
    Args:
        agent_graph: Optional existing AgentGraph instance to configure
        slot_store: Optional existing SlotStore instance to configure
        fsm_orchestrator: Optional existing FSMOrchestrator instance to configure
        model_escalator: Optional existing ModelEscalator instance to configure
    
    Returns:
        Tuple of (AgentGraph, SlotStore, FSMOrchestrator, ModelEscalator)
    """
    start_time = time.time()
    
    log_orchestration_event("info", "Initializing orchestration components", 
                          {"has_agent_graph": agent_graph is not None,
                           "has_slot_store": slot_store is not None,
                           "has_fsm_orchestrator": fsm_orchestrator is not None,
                           "has_model_escalator": model_escalator is not None},
                           phase="INIT")
    
    redis_client = None
    try:
        # Try to connect to Redis
        from redis import Redis
        
        # Check for Render environment first
        is_render = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("RENDER_SERVICE_ID")
        
        redis_connection_start = time.time()
        log_orchestration_event("info", f"Setting up Redis connection (Render environment: {is_render})", 
                              {"is_render": is_render},
                              phase="INIT")
        
        # Always use REDIS_URL from environment variables first
        redis_url = os.environ.get("REDIS_URL")
        
        if redis_url:
            log_orchestration_event("info", f"Using Redis URL from environment variable: {redis_url}", 
                                  {"source": "environment_variable", "redis_url": redis_url},
                                  phase="INIT")
            
            # If CELERY URLs aren't set, derive them from REDIS_URL
            if not os.environ.get("CELERY_BROKER_URL"):
                # Extract base Redis URL without DB number
                redis_base = redis_url.rsplit('/', 1)[0] if '/' in redis_url else redis_url
                celery_url = f"{redis_base}/1"
                os.environ["CELERY_BROKER_URL"] = celery_url
                os.environ["CELERY_RESULT_BACKEND"] = celery_url
                log_orchestration_event("debug", "Set CELERY_BROKER_URL and CELERY_RESULT_BACKEND based on REDIS_URL", 
                                      {"CELERY_BROKER_URL": celery_url},
                                      phase="INIT")
        elif is_render:
            # Fallback for Render environment if REDIS_URL is not set
            log_orchestration_event("warning", "REDIS_URL not set in environment but running in Render - check deployment configuration", 
                                   {"is_render": is_render},
                                   phase="INIT")
            
            # Try to construct URL from default Render Redis settings as fallback
            redis_url = os.environ.get("CELERY_BROKER_URL") or "redis://localhost:6379/0"
            log_orchestration_event("info", f"Falling back to derived Redis URL: {redis_url}", 
                                  {"source": "fallback", "redis_url": redis_url},
                                  phase="INIT")
        else:
            # Standard environment - use default Redis URL if available
            redis_url = os.environ.get("CELERY_BROKER_URL") or "redis://localhost:6379/0"
            log_orchestration_event("info", f"Using standard Redis URL: {redis_url}", 
                                  {"source": "fallback", "redis_url": redis_url},
                                  phase="INIT")
        
        if redis_url:
            # Make sure URL has proper format
            if not redis_url.startswith("redis://"):
                original_url = redis_url
                redis_url = f"redis://{redis_url}"
                log_orchestration_event("debug", f"Added redis:// prefix to Redis URL: {original_url} → {redis_url}", 
                                      {"original_url": original_url, "formatted_url": redis_url},
                                      phase="INIT")
            
            # Attempt connection with timeout
            connection_timeout = 2.0
            log_orchestration_event("info", f"Attempting to connect to Redis at: {redis_url} (timeout: {connection_timeout}s)", 
                                  {"redis_url": redis_url, "timeout": connection_timeout},
                                  phase="INIT")
            
            try:
                # Use socket_connect_timeout for initial connection
                redis_client = Redis.from_url(
                    redis_url, 
                    socket_timeout=connection_timeout,
                    socket_connect_timeout=connection_timeout,
                    retry_on_timeout=True
                )
                
                # Test the connection with ping
                ping_start = time.time()
                ping_result = redis_client.ping()
                ping_elapsed = time.time() - ping_start
                
                log_orchestration_event("info", f"Successfully connected to Redis and received ping response in {ping_elapsed:.3f}s", 
                                      {"ping_response": ping_result, "ping_time_ms": ping_elapsed * 1000},
                                      phase="INIT")
                
                # Successfully connected - ensure the URL is available to other components
                os.environ["REDIS_URL"] = redis_url
            except Exception as redis_ex:
                # Detailed Redis connection error handling
                error_details = {
                    "error": str(redis_ex),
                    "traceback": traceback.format_exc(),
                    "redis_url": redis_url
                }
                log_orchestration_event("error", f"Redis connection error: {str(redis_ex)}", 
                                      error_details,
                                      phase="INIT")
                
                # Try one more time with different options if this might be a DNS issue
                if "Name or service not known" in str(redis_ex) or "cannot resolve" in str(redis_ex).lower():
                    log_orchestration_event("warning", "Possible DNS issue with Redis hostname - trying localhost fallback", 
                                          {"original_url": redis_url},
                                          phase="INIT")
                    try:
                        # Try localhost fallback
                        fallback_url = "redis://localhost:6379/0"
                        redis_client = Redis.from_url(
                            fallback_url, 
                            socket_timeout=connection_timeout,
                            socket_connect_timeout=connection_timeout
                        )
                        ping_result = redis_client.ping()
                        log_orchestration_event("info", "Successfully connected to Redis using localhost fallback", 
                                              {"fallback_url": fallback_url},
                                              phase="INIT")
                    except Exception as fallback_ex:
                        log_orchestration_event("error", f"Redis fallback connection also failed: {str(fallback_ex)}", 
                                              {"fallback_error": str(fallback_ex)},
                                              phase="INIT")
                        redis_client = None
                else:
                    redis_client = None
        else:
            log_orchestration_event("warning", "No Redis URL found in environment variables", 
                                  {"env_vars": {k: v for k, v in os.environ.items() if 'REDIS' in k}},
                                  phase="INIT")
            redis_client = None
        
        redis_connection_elapsed = time.time() - redis_connection_start
        if redis_client:
            log_orchestration_event("info", f"Redis connection setup completed successfully in {redis_connection_elapsed:.3f}s", 
                                  {"elapsed_ms": redis_connection_elapsed * 1000, "has_redis": True},
                                  phase="INIT")
        else:
            log_orchestration_event("warning", f"Redis connection setup failed in {redis_connection_elapsed:.3f}s, using in-memory storage", 
                                  {"elapsed_ms": redis_connection_elapsed * 1000, "has_redis": False},
                                  phase="INIT")
    except Exception as e:
        # General error handling for the Redis connection attempt
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "has_redis_module": 'redis' in globals() or 'redis' in locals()
        }
        log_orchestration_event("error", f"Failed to set up Redis: {str(e)}", 
                              error_details,
                              phase="INIT")
        
        log_orchestration_event("info", "Using in-memory fallback for orchestration data", 
                              {},
                              phase="INIT")
        redis_client = None
    
    # Components creation timing
    components_start = time.time()
    
    # Use provided slot_store or create a new one
    if slot_store is None:
        log_orchestration_event("debug", "Creating new SlotStore", 
                              {"has_redis": redis_client is not None},
                              phase="INIT")
        slot_store = SlotStore(redis_client)
    else:
        log_orchestration_event("debug", "Using existing SlotStore", 
                              {},
                              phase="INIT")
    
    # Use provided agent_graph or create a new one
    if agent_graph is None:
        log_orchestration_event("debug", "Creating new AgentGraph with default configuration", 
                              {"node_count": len(DEFAULT_AGENT_GRAPH["nodes"]),
                               "transition_count": len(DEFAULT_AGENT_GRAPH["transitions"])},
                              phase="INIT")
        
        agent_graph = AgentGraph()
        
        # Populate with default nodes
        for node in DEFAULT_AGENT_GRAPH["nodes"]:
            agent_graph.add_node(**node)
        
        # Add default transitions
        for transition in DEFAULT_AGENT_GRAPH["transitions"]:
            agent_graph.add_transition(
                transition["from_agent"],
                transition["to_agent"],
                transition.get("condition"),
                transition.get("description")
            )
    else:
        log_orchestration_event("debug", "Using existing AgentGraph", 
                              {"node_count": len(agent_graph.nodes),
                               "transition_count": len(agent_graph.transitions)},
                              phase="INIT")
    
    # Use provided fsm_orchestrator or create a new one
    if fsm_orchestrator is None:
        log_orchestration_event("debug", "Creating new FSMOrchestrator with default templates", 
                              {},
                              phase="INIT")
        
        # Create the FSM orchestrator with templates
        # Write templates to a temp file
        import tempfile
        temp_file_start = time.time()
        
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
                yaml.dump(DEFAULT_AUTH_TEMPLATES, f)
                template_path = f.name
                
                temp_file_elapsed = time.time() - temp_file_start
                log_orchestration_event("debug", f"Created temporary template file at {template_path} in {temp_file_elapsed:.3f}s", 
                                      {"template_path": template_path, 
                                       "template_count": len(DEFAULT_AUTH_TEMPLATES),
                                       "elapsed_ms": temp_file_elapsed * 1000},
                                      phase="INIT")
                
            fsm_orchestrator = FSMOrchestrator(slot_store, template_path)
        except Exception as temp_ex:
            error_details = {
                "error": str(temp_ex),
                "traceback": traceback.format_exc()
            }
            log_orchestration_event("error", f"Failed to create template file: {str(temp_ex)}", 
                                  error_details,
                                  phase="INIT")
            
            # Fallback: create FSMOrchestrator without templates
            log_orchestration_event("warning", "Creating FSMOrchestrator without templates due to error", 
                                  {},
                                  phase="INIT")
            fsm_orchestrator = FSMOrchestrator(slot_store)
    else:
        log_orchestration_event("debug", "Using existing FSMOrchestrator", 
                              {},
                              phase="INIT")
    
    # Use provided model_escalator or create a new one
    if model_escalator is None:
        log_orchestration_event("debug", "Creating new ModelEscalator with default tiers", 
                              {},
                              phase="INIT")
        model_escalator = ModelEscalator()
    else:
        log_orchestration_event("debug", "Using existing ModelEscalator", 
                              {},
                              phase="INIT")
    
    components_elapsed = time.time() - components_start
    log_orchestration_event("info", f"Created orchestration components in {components_elapsed:.3f}s", 
                          {"elapsed_ms": components_elapsed * 1000},
                          phase="INIT")
    
    # Overall timing
    total_elapsed = time.time() - start_time
    log_orchestration_event("info", f"Orchestration initialization completed in {total_elapsed:.3f}s", 
                          {"total_elapsed_ms": total_elapsed * 1000,
                           "has_redis": redis_client is not None},
                          phase="INIT")
    
    return agent_graph, slot_store, fsm_orchestrator, model_escalator