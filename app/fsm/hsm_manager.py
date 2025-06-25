"""
HSM Manager for orchestrating the Hierarchical State Machine.

This module provides the main HSM manager that handles state transitions,
event processing, and coordinates between state definitions, handlers, and storage.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict

from app.fsm.hsm_core import (
    HSMStateDefinition, HSMEvent, HSMStateHandler, HSMTransition,
    HSMTransitionType, ConversationHSMStates, create_conversation_hsm_states
)
from app.fsm.state_store import hsm_state_store
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class HSMManager:
    """
    Manages the Hierarchical State Machine for conversations.
    
    Coordinates state transitions, event handling, and maintains
    the state hierarchy and active configuration.
    """
    
    def __init__(self):
        """Initialize the HSM Manager."""
        self.states: Dict[str, HSMStateDefinition] = {}
        self.handlers: Dict[str, HSMStateHandler] = {}
        self.transitions: Dict[str, List[HSMTransition]] = defaultdict(list)
        self.state_store = hsm_state_store
        
        # Initialize with default conversation states
        self._initialize_states()
    
    def _initialize_states(self):
        """Initialize the default conversation states."""
        self.states = create_conversation_hsm_states()
        logger.info(f"Initialized HSM with {len(self.states)} states")
    
    def register_handler(self, state_name: str, handler: HSMStateHandler) -> None:
        """
        Register a handler for a specific state.
        
        Args:
            state_name: Name of the state
            handler: Handler instance for the state
        """
        if state_name not in self.states:
            raise ValueError(f"State '{state_name}' not defined")
        
        self.handlers[state_name] = handler
        logger.info(f"Registered handler for state: {state_name}")
    
    def add_transition(self, transition: HSMTransition) -> None:
        """
        Add a transition rule to the HSM.
        
        Args:
            transition: Transition definition
        """
        key = f"{transition.source_state}:{transition.event_name}"
        self.transitions[key].append(transition)
        logger.debug(f"Added transition: {transition.source_state} --{transition.event_name}--> {transition.target_state}")
    
    async def initialize_conversation(self, call_sid: str, initial_state: str = ConversationHSMStates.INITIAL) -> None:
        """
        Initialize a new conversation HSM.
        
        Args:
            call_sid: Conversation identifier
            initial_state: Initial state name
        """
        await self.state_store.initialize_hsm(call_sid, initial_state)
        
        # Trigger entry actions for initial state
        await self._enter_state(call_sid, initial_state, None, {})
    
    async def handle_event(self, call_sid: str, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Process an event for a conversation.
        
        Args:
            call_sid: Conversation identifier
            event: Event to process
            context: Conversation context
            
        Returns:
            New leaf state after processing, or None if no change
        """
        try:
            # Get current state configuration
            current_path = await self.state_store.get_current_state_path(call_sid)
            if not current_path:
                logger.warning(f"[{call_sid}] No active state path")
                return None
            
            # Process event from leaf to root (bubbling)
            target_state = None
            handled = False
            
            for i in range(len(current_path) - 1, -1, -1):
                state_name = current_path[i]
                
                # Check for transitions from this state
                transition_key = f"{state_name}:{event.name}"
                transitions = self.transitions.get(transition_key, [])
                
                for transition in transitions:
                    # Check guard condition if present
                    if transition.guard and not await transition.guard(event, context):
                        continue
                    
                    # Found valid transition
                    target_state = transition.target_state
                    handled = True
                    
                    # Execute transition action if present
                    if transition.action:
                        await transition.action(event, context)
                    
                    break
                
                if not handled:
                    # Let state handler process the event
                    handler = self.handlers.get(state_name)
                    if handler:
                        handler_target = await handler.handle_event(event, context)
                        if handler_target:
                            target_state = handler_target
                            handled = True
                
                if handled:
                    break
            
            # Perform transition if needed
            if target_state:
                await self._transition_to(call_sid, target_state, event, context)
                return await self.state_store.get_leaf_state(call_sid)
            
            return None
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error handling event {event}: {e}", exc_info=True)
            return None
    
    async def _transition_to(self, call_sid: str, target_state_name: str, event: HSMEvent, context: Dict[str, Any]) -> None:
        """
        Perform a state transition.
        
        Args:
            call_sid: Conversation identifier
            target_state_name: Target state name
            event: Event that triggered the transition
            context: Conversation context
        """
        current_path = await self.state_store.get_current_state_path(call_sid)
        target_state = self.states.get(target_state_name)
        
        if not target_state:
            logger.error(f"[{call_sid}] Target state '{target_state_name}' not found")
            return
        
        # Determine transition path
        exit_path, enter_path = self._calculate_transition_path(current_path, target_state_name)
        
        logger.info(f"[{call_sid}] Transitioning: {current_path[-1] if current_path else 'None'} -> {target_state_name}")
        logger.debug(f"[{call_sid}] Exit path: {exit_path}, Enter path: {enter_path}")
        
        # Exit states (from leaf to common ancestor)
        for state_name in exit_path:
            await self._exit_state(call_sid, state_name, event, context)
        
        # Update state path
        new_path = await self._calculate_new_path(current_path, target_state_name, exit_path, enter_path)
        await self.state_store.set_state_path(call_sid, new_path)
        
        # Enter states (from common ancestor to target)
        for state_name in enter_path:
            await self._enter_state(call_sid, state_name, event, context)
            
            # Check for initial substate
            state_def = self.states.get(state_name)
            if state_def and state_def.initial_substate_name:
                # Recursively enter initial substates
                await self._enter_initial_substates(call_sid, state_def.initial_substate_name, event, context)
    
    async def _enter_initial_substates(self, call_sid: str, state_name: str, event: HSMEvent, context: Dict[str, Any]) -> None:
        """Recursively enter initial substates."""
        state_def = self.states.get(state_name)
        if not state_def:
            return
        
        # Add to path
        current_path = await self.state_store.get_current_state_path(call_sid)
        current_path.append(state_name)
        await self.state_store.set_state_path(call_sid, current_path)
        
        # Enter the state
        await self._enter_state(call_sid, state_name, event, context)
        
        # Check for initial substate
        if state_def.initial_substate_name:
            await self._enter_initial_substates(call_sid, state_def.initial_substate_name, event, context)
    
    def _calculate_transition_path(self, current_path: List[str], target_state_name: str) -> Tuple[List[str], List[str]]:
        """
        Calculate which states to exit and enter for a transition.
        
        Returns:
            Tuple of (exit_path, enter_path)
        """
        # Build target path
        target_path = self._build_state_path(target_state_name)
        
        # Find common ancestor
        common_length = 0
        for i in range(min(len(current_path), len(target_path))):
            if current_path[i] == target_path[i]:
                common_length = i + 1
            else:
                break
        
        # States to exit (in reverse order)
        exit_path = current_path[common_length:][::-1]
        
        # States to enter
        enter_path = target_path[common_length:]
        
        return exit_path, enter_path
    
    def _build_state_path(self, state_name: str) -> List[str]:
        """Build the complete path from root to the given state."""
        path = []
        current = state_name
        
        while current:
            path.insert(0, current)
            state_def = self.states.get(current)
            current = state_def.parent_state_name if state_def else None
        
        return path
    
    async def _calculate_new_path(self, current_path: List[str], target_state_name: str, 
                                  exit_path: List[str], enter_path: List[str]) -> List[str]:
        """Calculate the new state path after transition."""
        # Remove exited states
        new_path = current_path[:-len(exit_path)] if exit_path else current_path[:]
        
        # Add entered states
        new_path.extend(enter_path)
        
        return new_path
    
    async def _enter_state(self, call_sid: str, state_name: str, event: Optional[HSMEvent], context: Dict[str, Any]) -> None:
        """Execute entry actions for a state."""
        state_def = self.states.get(state_name)
        if state_def and state_def.on_enter:
            await state_def.on_enter(context, event)
        
        handler = self.handlers.get(state_name)
        if handler:
            await handler.on_enter(context, event)
        
        logger.info(f"[{call_sid}] Entered state: {state_name}")
    
    async def _exit_state(self, call_sid: str, state_name: str, event: Optional[HSMEvent], context: Dict[str, Any]) -> None:
        """Execute exit actions for a state."""
        handler = self.handlers.get(state_name)
        if handler:
            await handler.on_exit(context, event)
        
        state_def = self.states.get(state_name)
        if state_def and state_def.on_exit:
            await state_def.on_exit(context, event)
        
        logger.info(f"[{call_sid}] Exited state: {state_name}")
    
    async def get_current_states(self, call_sid: str) -> List[str]:
        """Get the current state configuration (full path)."""
        return await self.state_store.get_current_state_path(call_sid)
    
    async def is_in_state(self, call_sid: str, state_name: str) -> bool:
        """Check if the conversation is in a given state."""
        return await self.state_store.is_in_state(call_sid, state_name)
    
    async def pop_to_parent(self, call_sid: str, event: Optional[HSMEvent] = None, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Pop to the parent state (used for returning from substates).
        
        Args:
            call_sid: Conversation identifier
            event: Optional event that triggered the pop
            context: Optional conversation context
            
        Returns:
            New leaf state name
        """
        context = context or {}
        current_path = await self.state_store.get_current_state_path(call_sid)
        
        if len(current_path) > 1:
            # Exit current leaf
            await self._exit_state(call_sid, current_path[-1], event, context)
            
            # Pop from store
            new_leaf = await self.state_store.pop_state(call_sid)
            
            return new_leaf
        
        return None


# Global instance for easy access
hsm_manager = HSMManager()