"""
Core FSM implementation for RedBarSushiAI.

This module provides the core FSM classes and components for managing
conversation states and transitions.
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Callable, Union, Set
from enum import Enum, auto

from app.utils.conversation_store_async import async_conversation_store

# Set up logging
logger = logging.getLogger(__name__)


class FSMError(Exception):
    """Base exception for FSM-related errors."""
    pass

class ConversationState(Enum):
    """Enum representing the states in the voice conversation FSM."""
    
    INITIAL = auto()
    GREETING = auto()
    MAIN_MENU = auto()
    ORDERING = auto()
    VALIDATION = auto()
    CONFIRMATION = auto()
    FULFILLMENT = auto()
    COMPLETION = auto()
    FOLLOW_UP = auto()
    ESCALATION = auto()
    ERROR = auto()
    
    def __str__(self) -> str:
        """Return the string representation of the state."""
        return self.name


class ConversationEvent(Enum):
    """Enum representing events that trigger state transitions."""
    
    START_CONVERSATION = auto()
    USER_PROVIDES_NAME = auto()
    REQUEST_MENU_INFO = auto()
    START_ORDER = auto()
    ADD_ITEM = auto()
    REMOVE_ITEM = auto()
    MODIFY_ITEM = auto()
    COMPLETE_ORDER = auto()
    CANCEL_ORDER = auto()
    VALIDATE_ORDER = auto()
    ORDER_VALID = auto()
    ORDER_INVALID = auto()
    MODIFY_ORDER = auto()
    CONFIRM_ORDER = auto()
    REJECT_ORDER = auto()
    FULFILL_ORDER = auto()
    PROVIDE_DELIVERY_INFO = auto()
    CHOOSE_PICKUP = auto()
    COMPLETE_INTERACTION = auto()
    REQUEST_FOLLOW_UP = auto()
    REQUEST_ESCALATION = auto()
    ERROR_OCCURRED = auto()
    
    def __str__(self) -> str:
        """Return the string representation of the event."""
        return self.name


class AsyncStateHandler:
    """Base class for state handlers in the FSM."""
    
    def __init__(self, state: ConversationState):
        """
        Initialize the state handler.
        
        Args:
            state: The state this handler is responsible for
        """
        self.state = state
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering this state.
        
        Args:
            context: The conversation context
        """
        logger.info(f"Entering state: {self.state}")
    
    async def on_exit(self, context: Dict[str, Any]) -> None:
        """
        Called when exiting this state.
        
        Args:
            context: The conversation context
        """
        logger.info(f"Exiting state: {self.state}")
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle an event in this state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        logger.info(f"Handling event {event} in state {self.state}")
        return None


class AsyncConversationFSM:
    """
    Async Finite State Machine for managing conversation states and transitions.
    
    This FSM manages the state of a conversation, handling events and transitioning
    between states based on defined rules.
    """
    
    def __init__(self, call_sid: str):
        """
        Initialize the FSM.
        
        Args:
            call_sid: The Twilio call SID or session ID
        """
        self.call_sid = call_sid
        self.current_state = ConversationState.INITIAL
        self.context: Dict[str, Any] = {"call_sid": call_sid}
        
        # Initialize state handlers - imported at the instance level to avoid circular imports
        from app.fsm.handlers import (
            AsyncGreetingHandler,
            AsyncMainMenuHandler, 
            AsyncOrderingHandler,
            AsyncValidationHandler,
            AsyncConfirmationHandler,
            AsyncFulfillmentHandler,
            AsyncCompletionHandler,
            AsyncFollowUpHandler,
            AsyncEscalationHandler,
            AsyncErrorHandler
        )
        
        # Initialize state handlers
        self.handlers = {
            ConversationState.INITIAL: None,  # No handler for initial state
            ConversationState.GREETING: AsyncGreetingHandler(),
            ConversationState.MAIN_MENU: AsyncMainMenuHandler(),
            ConversationState.ORDERING: AsyncOrderingHandler(),
            ConversationState.VALIDATION: AsyncValidationHandler(),
            ConversationState.CONFIRMATION: AsyncConfirmationHandler(),
            ConversationState.FULFILLMENT: AsyncFulfillmentHandler(),
            ConversationState.COMPLETION: AsyncCompletionHandler(),
            ConversationState.FOLLOW_UP: AsyncFollowUpHandler(),
            ConversationState.ESCALATION: AsyncEscalationHandler(),
            ConversationState.ERROR: AsyncErrorHandler()
        }
        
        # Define valid transitions
        self.transitions = {
            ConversationState.INITIAL: {
                ConversationEvent.START_CONVERSATION: ConversationState.GREETING
            },
            ConversationState.GREETING: {
                ConversationEvent.USER_PROVIDES_NAME: ConversationState.MAIN_MENU,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.MAIN_MENU: {
                ConversationEvent.START_ORDER: ConversationState.ORDERING,
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.ORDERING: {
                ConversationEvent.COMPLETE_ORDER: ConversationState.VALIDATION,
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.VALIDATION: {
                ConversationEvent.ORDER_VALID: ConversationState.CONFIRMATION,
                ConversationEvent.ORDER_INVALID: ConversationState.ORDERING,
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.CONFIRMATION: {
                ConversationEvent.CONFIRM_ORDER: ConversationState.FULFILLMENT,
                ConversationEvent.REJECT_ORDER: ConversationState.ORDERING,
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.FULFILLMENT: {
                ConversationEvent.COMPLETE_INTERACTION: ConversationState.COMPLETION,
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.COMPLETION: {
                ConversationEvent.REQUEST_FOLLOW_UP: ConversationState.FOLLOW_UP,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.FOLLOW_UP: {
                ConversationEvent.START_ORDER: ConversationState.ORDERING,
                ConversationEvent.COMPLETE_INTERACTION: None,  # End the conversation
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.ESCALATION: {
                ConversationEvent.ERROR_OCCURRED: ConversationState.ERROR
            },
            ConversationState.ERROR: {
                ConversationEvent.REQUEST_ESCALATION: ConversationState.ESCALATION,
                ConversationEvent.START_ORDER: ConversationState.ORDERING,
                ConversationEvent.START_CONVERSATION: ConversationState.GREETING
            }
        }
    
    async def start(self) -> None:
        """Start the FSM by transitioning to the GREETING state."""
        await self.trigger(ConversationEvent.START_CONVERSATION)
    
    async def trigger(self, event: ConversationEvent) -> None:
        """
        Trigger an event in the FSM.
        
        Args:
            event: The event to trigger
        """
        logger.info(f"Triggering event {event} in state {self.current_state}")
        
        # Check if this event is valid for the current state
        if self.current_state not in self.transitions or event not in self.transitions[self.current_state]:
            logger.warning(f"Invalid event {event} for state {self.current_state}")
            return
        
        # Get the next state from the transition table
        next_state = self.transitions[self.current_state][event]
        
        # Always let the current handler process the event first
        handler = self.handlers.get(self.current_state)
        if handler:
            # Let the handler process the event and possibly override the next state
            handler_next_state = await handler.handle_event(event, self.context)
            if handler_next_state is not None:
                next_state = handler_next_state
        
        # Now transition if needed
        if next_state is not None:
            await self.transition_to(next_state)
        else:
            logger.info(f"Event {event} does not cause a state transition")
    
    async def transition_to(self, next_state: ConversationState) -> None:
        """
        Transition to a new state.
        
        Args:
            next_state: The state to transition to
        """
        logger.info(f"Transitioning from {self.current_state} to {next_state}")
        
        # Get the current and next state handlers
        current_handler = self.handlers.get(self.current_state)
        next_handler = self.handlers.get(next_state)
        
        # Exit the current state
        if current_handler:
            await current_handler.on_exit(self.context)
        
        # Update the current state
        previous_state = self.current_state
        self.current_state = next_state
        
        # Save the state to the conversation store
        await self._save_state()
        
        # Enter the next state
        if next_handler:
            await next_handler.on_enter(self.context)
            
            # Check for pending events
            pending_event = self.context.pop("_pending_event", None)
            if pending_event:
                logger.info(f"Found pending event {pending_event} after entering {next_state}")
                await self.trigger(pending_event)
    
    async def _save_state(self) -> None:
        """Save the current state to the conversation store."""
        try:
            # Update the conversation store with the current state
            await async_conversation_store.update_conversation(
                self.call_sid,
                {
                    "fsm_state": self.current_state.name,
                    "fsm_context": json.dumps(self._serialize_context())
                }
            )
            
            logger.info(f"Saved FSM state {self.current_state} for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error saving FSM state: {e}")
    
    async def load_state(self) -> None:
        """Load the state from the conversation store."""
        try:
            # Load the conversation data
            conversation = await async_conversation_store.get_conversation(self.call_sid)
            
            # Extract FSM state if present
            if "fsm_state" in conversation:
                state_name = conversation["fsm_state"]
                try:
                    self.current_state = ConversationState[state_name]
                    logger.info(f"Loaded FSM state {self.current_state} for call {self.call_sid}")
                except KeyError:
                    logger.warning(f"Unknown FSM state {state_name}, defaulting to INITIAL")
                    self.current_state = ConversationState.INITIAL
            
            # Extract FSM context if present
            if "fsm_context" in conversation:
                try:
                    context_data = json.loads(conversation["fsm_context"])
                    self._deserialize_context(context_data)
                    logger.info(f"Loaded FSM context for call {self.call_sid}")
                except Exception as e:
                    logger.error(f"Error loading FSM context: {e}")
        except Exception as e:
            logger.error(f"Error loading FSM state: {e}")
    
    def _serialize_context(self) -> Dict[str, Any]:
        """
        Serialize the context for storage.
        
        Returns:
            A serializable version of the context
        """
        # Create a copy of the context
        serializable = {}
        
        # Keep only serializable values
        for key, value in self.context.items():
            # Skip agent instances and complex objects
            if key in ["frontline_agent", "menu_agent", "cart_agent", "guardrail_agent", 
                       "fulfillment_agent", "escalation_agent"] or callable(value):
                continue
            
            # Include simple types and structures
            if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                serializable[key] = value
        
        return serializable
    
    def _deserialize_context(self, context_data: Dict[str, Any]) -> None:
        """
        Deserialize the context from storage.
        
        Args:
            context_data: The context data to load
        """
        # Update the context with the loaded data, preserving existing keys
        for key, value in context_data.items():
            # Don't overwrite agent instances
            if key not in ["frontline_agent", "menu_agent", "cart_agent", "guardrail_agent", 
                          "fulfillment_agent", "escalation_agent"]:
                self.context[key] = value
    
    def update_context(self, updates: Dict[str, Any]) -> None:
        """
        Update the context with new values.
        
        Args:
            updates: The values to update in the context
        """
        self.context.update(updates)
    
    async def process_transcript(self, transcript: str) -> None:
        """
        Process a transcript from the user.
        
        Args:
            transcript: The transcript to process
        """
        # Update the context with the transcript
        self.context["transcript"] = transcript
        
        # Determine the appropriate event based on the current state and transcript
        event = await self._extract_event_from_transcript(transcript)
        
        if event:
            await self.trigger(event)
    
    async def _extract_event_from_transcript(self, transcript: str) -> Optional[ConversationEvent]:
        """
        Extract an event from a transcript using LLM-based intent detection.
        
        Args:
            transcript: The transcript to analyze
            
        Returns:
            The extracted event, or None if no event could be determined
        """
        try:
            # Use LLM-based intent detection
            from app.utils.intent_detector_async import intent_detector
            
            event = await intent_detector.detect_intent(
                transcript=transcript,
                current_state=self.current_state,
                context=self.context
            )
            
            if event:
                logger.info(f"LLM detected event {event.name} from transcript: '{transcript[:50]}...'")
            else:
                logger.info(f"No event detected by LLM for transcript: '{transcript[:50]}...'")
                
            return event
            
        except Exception as e:
            logger.error(f"Error in LLM intent detection: {e}")
            # Don't fall back to keyword detection - let agents handle the transcript
            return None


class AsyncFSMManager:
    """
    Manager for async FSM instances.
    
    This class provides a centralized way to create, retrieve, and manage
    FSM instances for different sessions.
    """
    
    def __init__(self):
        """Initialize the FSM manager."""
        self.fsm_instances: Dict[str, AsyncConversationFSM] = {}
    
    async def get_fsm(self, call_sid: str) -> AsyncConversationFSM:
        """
        Get or create an FSM instance for a call.
        
        Args:
            call_sid: The Twilio call SID or session ID
            
        Returns:
            The FSM instance
        """
        if call_sid in self.fsm_instances:
            return self.fsm_instances[call_sid]
        
        # Create a new FSM instance
        fsm = AsyncConversationFSM(call_sid)
        
        # Load state from the conversation store
        await fsm.load_state()
        
        # Store the instance
        self.fsm_instances[call_sid] = fsm
        
        return fsm
    
    async def start_conversation(self, call_sid: str, context: Optional[Dict[str, Any]] = None) -> AsyncConversationFSM:
        """
        Start a new conversation with an FSM.
        
        Args:
            call_sid: The Twilio call SID or session ID
            context: Optional initial context for the FSM
            
        Returns:
            The FSM instance
        """
        # Create a new FSM instance
        fsm = AsyncConversationFSM(call_sid)
        
        # Update the context if provided
        if context:
            fsm.update_context(context)
        
        # Start the FSM
        await fsm.start()
        
        # Store the instance
        self.fsm_instances[call_sid] = fsm
        
        return fsm
    
    def remove_fsm(self, call_sid: str) -> None:
        """
        Remove an FSM instance.
        
        Args:
            call_sid: The Twilio call SID or session ID
        """
        if call_sid in self.fsm_instances:
            del self.fsm_instances[call_sid]
    
    async def cleanup_all(self) -> None:
        """Clean up all FSM instances."""
        self.fsm_instances.clear()


# Create a global instance of the FSM manager
async_fsm_manager = AsyncFSMManager()