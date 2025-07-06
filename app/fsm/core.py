"""
Core FSM/HSM implementation for RedBarSushiAI.

This module provides the core finite state machine functionality,
now redirecting to the HSM implementation for backwards compatibility.
"""

import logging
from typing import Dict, Any, Optional, Set, Callable, List
from enum import Enum
from abc import ABC, abstractmethod

# Import HSM components for backwards compatibility
from app.fsm.hsm_core import (
    ConversationHSMStates,
    ConversationHSMEvents
)
from app.fsm.hsm_manager import HSMManager as BaseHSMManager
from enum import Enum

# Create compatibility aliases
class ConversationState(Enum):
    """Backwards compatibility enum for conversation states."""
    INITIAL = ConversationHSMStates.INITIAL
    GREETING = ConversationHSMStates.GREETING
    MAIN_MENU = ConversationHSMStates.MAIN_MENU
    ORDERING = ConversationHSMStates.ORDERING
    VALIDATION = ConversationHSMStates.VALIDATION
    CONFIRMATION = ConversationHSMStates.CONFIRMATION
    FULFILLMENT = ConversationHSMStates.FULFILLMENT
    COMPLETION = ConversationHSMStates.COMPLETION
    ERROR_RECOVERY = ConversationHSMStates.ERROR_RECOVERY
    ESCALATION = ConversationHSMStates.ESCALATION


class ConversationEvent(Enum):
    """Backwards compatibility enum for conversation events."""
    START_CONVERSATION = ConversationHSMEvents.START_CONVERSATION
    END_CONVERSATION = ConversationHSMEvents.END_CONVERSATION
    USER_GREETS = ConversationHSMEvents.USER_GREETS
    USER_SAYS_GOODBYE = ConversationHSMEvents.USER_SAYS_GOODBYE
    REQUEST_MENU_INFO = ConversationHSMEvents.REQUEST_MENU_INFO
    START_ORDER = ConversationHSMEvents.START_ORDER
    ADD_ITEM = ConversationHSMEvents.ADD_ITEM
    REMOVE_ITEM = ConversationHSMEvents.REMOVE_ITEM
    MODIFY_ITEM = ConversationHSMEvents.MODIFY_ITEM
    SELECT_ITEM = ConversationHSMEvents.SELECT_ITEM

logger = logging.getLogger(__name__)


class AsyncStateHandler(ABC):
    """Abstract base class for async state handlers."""
    
    @abstractmethod
    async def handle(self, event: ConversationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle state logic asynchronously."""
        pass


class AsyncConversationFSM:
    """
    Async Finite State Machine for conversation management.
    
    This is a compatibility wrapper around the HSM implementation.
    """
    
    def __init__(self, initial_state: ConversationState = ConversationState.GREETING):
        """Initialize the FSM with HSM backend."""
        self.hsm_manager = BaseHSMManager()
        self.current_state = initial_state
        self.handlers: Dict[ConversationState, AsyncStateHandler] = {}
    
    def add_handler(self, state: ConversationState, handler: AsyncStateHandler):
        """Add a state handler."""
        self.handlers[state] = handler
    
    async def transition(self, event: ConversationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute state transition."""
        try:
            # Use HSM manager for transition logic
            result = await self.hsm_manager.handle_event(event, context)
            
            # Update current state if transition was successful
            if result.get('success', False):
                new_state = result.get('new_state')
                if new_state:
                    self.current_state = new_state
            
            return result
            
        except Exception as e:
            logger.error(f"FSM transition error: {e}")
            return {
                'success': False,
                'error': str(e),
                'state': self.current_state
            }
    
    def get_current_state(self) -> ConversationState:
        """Get current state."""
        return self.current_state
    
    def get_valid_events(self) -> Set[ConversationEvent]:
        """Get valid events for current state."""
        return self.hsm_manager.get_valid_events(self.current_state)


class AsyncFSMManager:
    """
    Async FSM Manager for managing conversation state machines.
    
    This provides a compatibility layer over the HSM implementation.
    """
    
    def __init__(self):
        """Initialize the FSM manager."""
        self.fsm_instances: Dict[str, AsyncConversationFSM] = {}
        self.hsm_manager = BaseHSMManager()
    
    async def get_fsm(self, session_id: str) -> AsyncConversationFSM:
        """Get or create FSM instance for session."""
        if session_id not in self.fsm_instances:
            self.fsm_instances[session_id] = AsyncConversationFSM()
        return self.fsm_instances[session_id]
    
    async def handle_event(
        self,
        session_id: str,
        event: ConversationEvent,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle event for a specific session."""
        fsm = await self.get_fsm(session_id)
        return await fsm.transition(event, context)
    
    async def get_state(self, session_id: str) -> ConversationState:
        """Get current state for session."""
        fsm = await self.get_fsm(session_id)
        return fsm.get_current_state()
    
    async def reset_session(self, session_id: str):
        """Reset session state."""
        if session_id in self.fsm_instances:
            del self.fsm_instances[session_id]
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        # This could be implemented with TTL logic
        pass
    
    async def cleanup_all(self):
        """Clean up all FSM instances."""
        self.fsm_instances.clear()


# Global FSM manager instance
async_fsm_manager = AsyncFSMManager()


# Backwards compatibility exports
__all__ = [
    'ConversationState',
    'ConversationEvent', 
    'AsyncStateHandler',
    'AsyncConversationFSM',
    'AsyncFSMManager',
    'async_fsm_manager'
]