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

from app.utils.monitoring import log_with_context
from app.utils.agent_monitoring import log_agent_call, log_tool_call
from app.utils.conversation_store_sdk import agents_conversation_store

# Configure logging
logger = logging.getLogger(__name__)

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
        self.nodes: Dict[str, AgentNode] = {}
        self.transitions: List[AgentTransition] = []
        
        if graph_path:
            self.load_graph(graph_path)
    
    def load_graph(self, path: str) -> None:
        """
        Load an agent graph definition from a file.
        
        Args:
            path: Path to a YAML/JSON file defining the graph
        """
        try:
            with open(path, 'r') as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    graph_def = yaml.safe_load(f)
                else:
                    graph_def = json.load(f)
            
            # Load nodes
            self.nodes = {node['name']: node for node in graph_def.get('nodes', [])}
            
            # Load transitions
            self.transitions = graph_def.get('transitions', [])
            
            logger.info(f"Loaded agent graph with {len(self.nodes)} nodes and {len(self.transitions)} transitions")
        except Exception as e:
            logger.error(f"Error loading agent graph from {path}: {str(e)}")
            raise
    
    def add_node(self, name: str, **node_props) -> None:
        """
        Add a node to the graph.
        
        Args:
            name: The name of the agent node
            **node_props: Additional properties for the node
        """
        self.nodes[name] = {
            'name': name,
            **node_props
        }
        logger.info(f"Added agent node: {name}")
    
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
        transition = {
            'from_agent': from_agent,
            'to_agent': to_agent
        }
        
        if condition:
            transition['condition'] = condition
        
        if description:
            transition['description'] = description
        
        self.transitions.append(transition)
        logger.info(f"Added transition: {from_agent} → {to_agent}")
    
    def get_next_agent(
        self, 
        current_agent: str, 
        state: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determine the next agent based on the current agent and state.
        
        Args:
            current_agent: The current agent
            state: The current conversation state
            
        Returns:
            The next agent or None if no transition is applicable
        """
        # Filter transitions from the current agent
        possible_transitions = [
            t for t in self.transitions if t['from_agent'] == current_agent
        ]
        
        # Check conditions to find valid transitions
        for transition in possible_transitions:
            if self._check_transition_condition(transition, state):
                logger.info(f"Selected transition: {current_agent} → {transition['to_agent']}")
                return transition['to_agent']
        
        # If no transitions match, return None
        logger.warning(f"No valid transitions from {current_agent}")
        return None
    
    def _check_transition_condition(
        self, 
        transition: AgentTransition, 
        state: Dict[str, Any]
    ) -> bool:
        """
        Check if a transition condition is satisfied.
        
        Args:
            transition: The transition to check
            state: The current conversation state
            
        Returns:
            True if the condition is satisfied, False otherwise
        """
        # If no condition, transition is always valid
        if 'condition' not in transition:
            return True
        
        condition = transition['condition']
        condition_type = condition.get('type')
        
        if condition_type == 'slot_filled':
            # Check if a slot has been filled
            slot = condition.get('slot')
            return slot in state.get('slots', {})
        
        elif condition_type == 'slot_value':
            # Check if a slot has a specific value
            slot = condition.get('slot')
            value = condition.get('value')
            return state.get('slots', {}).get(slot) == value
        
        elif condition_type == 'tool_result':
            # Check a field in the result of a tool call
            tool = condition.get('tool')
            field = condition.get('field')
            value = condition.get('value')
            comparison = condition.get('comparison', 'eq')
            
            tool_results = state.get('tool_results', {})
            if tool not in tool_results:
                return False
            
            result = tool_results[tool]
            if field not in result:
                return False
            
            actual_value = result[field]
            
            if comparison == 'eq':
                return actual_value == value
            elif comparison == 'neq':
                return actual_value != value
            elif comparison == 'gt':
                return actual_value > value
            elif comparison == 'lt':
                return actual_value < value
            elif comparison == 'contains':
                return value in actual_value
            else:
                return False
        
        elif condition_type == 'confidence':
            # Check if confidence is above/below threshold
            threshold = condition.get('value', 0.7)
            comparison = condition.get('comparison', 'lt')
            
            confidence = state.get('last_confidence', 1.0)
            
            if comparison == 'lt':
                return confidence < threshold
            elif comparison == 'gt':
                return confidence > threshold
            else:
                return False
        
        elif condition_type == 'default':
            # Default transition if no other conditions match
            return True
        
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
        self.redis = redis_client
        self.local_store = {}
    
    def get_slot(self, call_sid: str, slot_name: str) -> Any:
        """
        Get a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            
        Returns:
            The slot value or None if not found
        """
        if self.redis:
            try:
                slot_key = f"slot:{call_sid}:{slot_name}"
                value = self.redis.get(slot_key)
                if value:
                    return json.loads(value)
                return None
            except Exception as e:
                logger.error(f"Error getting slot from Redis: {str(e)}")
                # Fall back to local store
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        return self.local_store.get(store_key, {}).get(slot_name)
    
    def set_slot(self, call_sid: str, slot_name: str, value: Any) -> None:
        """
        Set a slot value.
        
        Args:
            call_sid: The call SID
            slot_name: The name of the slot
            value: The value to set
        """
        if self.redis:
            try:
                slot_key = f"slot:{call_sid}:{slot_name}"
                self.redis.set(slot_key, json.dumps(value))
                # Also set a TTL (2 hours)
                self.redis.expire(slot_key, 7200)
                return
            except Exception as e:
                logger.error(f"Error setting slot in Redis: {str(e)}")
                # Fall back to local store
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        if store_key not in self.local_store:
            self.local_store[store_key] = {}
        self.local_store[store_key][slot_name] = value
    
    def get_all_slots(self, call_sid: str) -> Dict[str, Any]:
        """
        Get all slots for a call.
        
        Args:
            call_sid: The call SID
            
        Returns:
            Dictionary of all slots
        """
        if self.redis:
            try:
                # Get all keys for this call
                pattern = f"slot:{call_sid}:*"
                keys = self.redis.keys(pattern)
                
                # Get all values
                result = {}
                for key in keys:
                    # Extract slot name from key
                    slot_name = key.decode('utf-8').split(':')[-1]
                    value = self.redis.get(key)
                    if value:
                        result[slot_name] = json.loads(value)
                
                return result
            except Exception as e:
                logger.error(f"Error getting all slots from Redis: {str(e)}")
                # Fall back to local store
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        return self.local_store.get(store_key, {})
    
    def clear_slots(self, call_sid: str) -> None:
        """
        Clear all slots for a call.
        
        Args:
            call_sid: The call SID
        """
        if self.redis:
            try:
                # Delete all keys for this call
                pattern = f"slot:{call_sid}:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
                return
            except Exception as e:
                logger.error(f"Error clearing slots from Redis: {str(e)}")
                # Fall back to local store
        
        # Use local store if Redis is not available or fails
        store_key = f"{call_sid}:slots"
        if store_key in self.local_store:
            del self.local_store[store_key]


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
    
    def __init__(self):
        """Initialize the model escalator."""
        # Default model tiers (weakest to strongest)
        self.model_tiers = [
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o1-mini"
        ]
    
    def should_escalate(
        self, 
        confidence: float,
        current_model: str,
        is_critical: bool = False,
        threshold: float = 0.7
    ) -> bool:
        """
        Determine if escalation is needed.
        
        Args:
            confidence: The confidence score (0-1)
            current_model: The current model
            is_critical: Whether this is a critical operation
            threshold: The confidence threshold
            
        Returns:
            True if escalation is needed, False otherwise
        """
        # Lower threshold for critical operations
        if is_critical:
            threshold = max(threshold, 0.8)
        
        # Check if confidence is below threshold
        if confidence < threshold:
            # Check if we can escalate to a stronger model
            model_index = self.model_tiers.index(current_model) if current_model in self.model_tiers else -1
            return model_index < len(self.model_tiers) - 1
        
        return False
    
    def get_escalation_model(self, current_model: str) -> str:
        """
        Get the next stronger model.
        
        Args:
            current_model: The current model
            
        Returns:
            The next stronger model
        """
        if current_model not in self.model_tiers:
            # Default to the strongest model
            return self.model_tiers[-1]
        
        model_index = self.model_tiers.index(current_model)
        if model_index < len(self.model_tiers) - 1:
            return self.model_tiers[model_index + 1]
        else:
            # Already at the strongest model
            return current_model
    
    def escalate_request(
        self,
        original_request: Dict[str, Any],
        current_model: str
    ) -> Dict[str, Any]:
        """
        Prepare a request for escalation to a stronger model.
        
        Args:
            original_request: The original request
            current_model: The current model
            
        Returns:
            The updated request with the stronger model
        """
        # Clone the request
        escalated_request = original_request.copy()
        
        # Get the escalation model
        escalation_model = self.get_escalation_model(current_model)
        
        # Update the model in the request
        escalated_request["model"] = escalation_model
        
        # Mark as escalated for tracking
        escalated_request["is_escalated"] = True
        escalated_request["original_model"] = current_model
        
        # Log the escalation
        log_with_context(
            "info",
            f"Escalating from {current_model} to {escalation_model}",
            {
                "original_model": current_model,
                "escalation_model": escalation_model
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
    try:
        # Try to connect to Redis
        from redis import Redis
        
        # Check for Render environment first
        is_render = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("RENDER_SERVICE_ID")
        
        if is_render:
            # Use Render-specific Redis host
            redis_host = "red-ceqpb6rf1sgc739ut8e0"
            redis_port = 6379
            redis_db = 0
            redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            logger.info(f"Using Render-specific Redis URL: {redis_url}")
            
            # Update environment variables for other components to use
            os.environ["REDIS_URL"] = redis_url
            os.environ["CELERY_BROKER_URL"] = f"redis://{redis_host}:{redis_port}/1"
            os.environ["CELERY_RESULT_BACKEND"] = f"redis://{redis_host}:{redis_port}/1"
        else:
            # Use standard Redis URL from environment variables
            redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
        
        if redis_url:
            # Make sure URL has proper format
            if not redis_url.startswith("redis://"):
                redis_url = f"redis://{redis_url}"
                
            logger.info(f"Connecting to Redis at: {redis_url}")
            redis_client = Redis.from_url(redis_url, socket_timeout=2.0)
            # Test the connection
            redis_client.ping()
            logger.info("✅ Successfully connected to Redis")
        else:
            logger.warning("No Redis URL found, using in-memory storage")
            redis_client = None
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {str(e)}")
        logger.info("Using in-memory fallback for orchestration data")
        redis_client = None
    
    # Use provided slot_store or create a new one
    if slot_store is None:
        slot_store = SlotStore(redis_client)
    
    # Use provided agent_graph or create a new one
    if agent_graph is None:
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
    
    # Use provided fsm_orchestrator or create a new one
    if fsm_orchestrator is None:
        # Create the FSM orchestrator with templates
        # Write templates to a temp file
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
            yaml.dump(DEFAULT_AUTH_TEMPLATES, f)
            template_path = f.name
        
        fsm_orchestrator = FSMOrchestrator(slot_store, template_path)
    
    # Use provided model_escalator or create a new one
    if model_escalator is None:
        model_escalator = ModelEscalator()
    
    return agent_graph, slot_store, fsm_orchestrator, model_escalator