"""
Async Finite State Machine (FSM) implementation for RedBarSushiAI.

This module provides an async FSM implementation for managing conversation states 
and transitions in voice interactions.
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
    VALIDATE_ORDER = auto()
    ORDER_VALID = auto()
    ORDER_INVALID = auto()
    CONFIRM_ORDER = auto()
    REJECT_ORDER = auto()
    FULFILL_ORDER = auto()
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


class AsyncGreetingHandler(AsyncStateHandler):
    """Handler for the GREETING state."""
    
    def __init__(self):
        """Initialize the greeting handler."""
        super().__init__(ConversationState.GREETING)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the GREETING state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a greeting message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            greeting = await agent.process_voice_input("", {"first_interaction": True})
            
            # Store the greeting in the context
            context["greeting_response"] = greeting
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the GREETING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.USER_PROVIDES_NAME:
            # Extract the user's name if possible
            if "transcript" in context:
                # Simple name extraction (would be more sophisticated in production)
                name_indicators = ["my name is", "i'm", "i am", "call me", "this is"]
                transcript = context["transcript"].lower()
                
                for indicator in name_indicators:
                    if indicator in transcript:
                        start_idx = transcript.find(indicator) + len(indicator)
                        name_part = transcript[start_idx:].strip()
                        
                        # Extract first word as name
                        if name_part:
                            words = name_part.split()
                            if words:
                                context["customer_name"] = words[0]
                                break
            
            # Transition to MAIN_MENU
            return ConversationState.MAIN_MENU
        
        return None


class AsyncMainMenuHandler(AsyncStateHandler):
    """Handler for the MAIN_MENU state."""
    
    def __init__(self):
        """Initialize the main menu handler."""
        super().__init__(ConversationState.MAIN_MENU)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the MAIN_MENU state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a main menu message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            main_menu = await agent._handle_main_menu("")
            
            # Store the main menu message in the context
            context["main_menu_response"] = main_menu
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the MAIN_MENU state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.REQUEST_MENU_INFO:
            # Stay in the same state, but set a flag for menu info request
            context["requesting_menu_info"] = True
            return None
        
        elif event == ConversationEvent.START_ORDER:
            # Transition to ORDERING
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncOrderingHandler(AsyncStateHandler):
    """Handler for the ORDERING state."""
    
    def __init__(self):
        """Initialize the ordering handler."""
        super().__init__(ConversationState.ORDERING)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the ORDERING state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Initialize cart if not present
        if "cart" not in context:
            context["cart"] = {"items": [], "total_price": 0}
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the ORDERING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.ADD_ITEM:
            # Handle adding an item to the cart
            # We stay in the ORDERING state after adding an item
            return None
        
        elif event == ConversationEvent.REMOVE_ITEM:
            # Handle removing an item from the cart
            # We stay in the ORDERING state after removing an item
            return None
        
        elif event == ConversationEvent.MODIFY_ITEM:
            # Handle modifying an item in the cart
            # We stay in the ORDERING state after modifying an item
            return None
        
        elif event == ConversationEvent.COMPLETE_ORDER:
            # Transition to VALIDATION
            return ConversationState.VALIDATION
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncValidationHandler(AsyncStateHandler):
    """Handler for the VALIDATION state."""
    
    def __init__(self):
        """Initialize the validation handler."""
        super().__init__(ConversationState.VALIDATION)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the VALIDATION state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Validate the order if there's a guardrail agent
        if context.get("guardrail_agent") and context.get("cart"):
            agent = context["guardrail_agent"]
            
            # Clone the context to avoid modifying the original
            validation_context = context.copy()
            validation_context["validation_in_progress"] = True
            
            validation_result = await agent.validate(context["cart"], validation_context)
            
            # Store the validation result in the context
            context["validation_result"] = validation_result
            
            # Trigger the appropriate event based on validation result
            if validation_result[0]:  # First element is a boolean
                context["_pending_event"] = ConversationEvent.ORDER_VALID
            else:
                context["_pending_event"] = ConversationEvent.ORDER_INVALID
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the VALIDATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.ORDER_VALID:
            # Transition to CONFIRMATION
            return ConversationState.CONFIRMATION
        
        elif event == ConversationEvent.ORDER_INVALID:
            # Go back to ORDERING to fix the issues
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncConfirmationHandler(AsyncStateHandler):
    """Handler for the CONFIRMATION state."""
    
    def __init__(self):
        """Initialize the confirmation handler."""
        super().__init__(ConversationState.CONFIRMATION)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the CONFIRMATION state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a confirmation message if there's a frontline agent
        if context.get("frontline_agent") and context.get("cart"):
            agent = context["frontline_agent"]
            confirmation = await agent._generate_confirmation_prompt()
            
            # Store the confirmation message in the context
            context["confirmation_message"] = confirmation
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the CONFIRMATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.CONFIRM_ORDER:
            # Transition to FULFILLMENT
            return ConversationState.FULFILLMENT
        
        elif event == ConversationEvent.REJECT_ORDER:
            # Go back to ORDERING to modify the order
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncFulfillmentHandler(AsyncStateHandler):
    """Handler for the FULFILLMENT state."""
    
    def __init__(self):
        """Initialize the fulfillment handler."""
        super().__init__(ConversationState.FULFILLMENT)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the FULFILLMENT state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Submit the order if there's a fulfillment agent
        if context.get("fulfillment_agent") and context.get("cart"):
            agent = context["fulfillment_agent"]
            
            # Clone the context to avoid modifying the original
            fulfillment_context = context.copy()
            fulfillment_context["fulfillment_in_progress"] = True
            
            fulfill_result = await agent.process_input("process_order", fulfillment_context)
            
            # Store the fulfillment result in the context
            context["fulfillment_result"] = fulfill_result
            
            # Set a flag indicating if fulfillment is complete
            context["fulfillment_complete"] = fulfill_result.get("fulfillment_complete", False)
            
            # If fulfillment is complete, transition to COMPLETION
            if context["fulfillment_complete"]:
                context["_pending_event"] = ConversationEvent.COMPLETE_INTERACTION
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the FULFILLMENT state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.COMPLETE_INTERACTION:
            # Transition to COMPLETION
            return ConversationState.COMPLETION
        
        elif event == ConversationEvent.ERROR_OCCURRED:
            # Transition to ERROR
            return ConversationState.ERROR
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncCompletionHandler(AsyncStateHandler):
    """Handler for the COMPLETION state."""
    
    def __init__(self):
        """Initialize the completion handler."""
        super().__init__(ConversationState.COMPLETION)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the COMPLETION state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a completion message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            completion = await agent._handle_completion("")
            
            # Store the completion message in the context
            context["completion_response"] = completion
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the COMPLETION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.REQUEST_FOLLOW_UP:
            # Transition to FOLLOW_UP
            return ConversationState.FOLLOW_UP
        
        return None


class AsyncFollowUpHandler(AsyncStateHandler):
    """Handler for the FOLLOW_UP state."""
    
    def __init__(self):
        """Initialize the follow-up handler."""
        super().__init__(ConversationState.FOLLOW_UP)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the FOLLOW_UP state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a follow-up message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            follow_up = await agent._handle_follow_up("")
            
            # Store the follow-up message in the context
            context["follow_up_response"] = follow_up
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the FOLLOW_UP state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.START_ORDER:
            # Reset cart and transition to ORDERING
            context["cart"] = {"items": [], "total_price": 0}
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.COMPLETE_INTERACTION:
            # End the conversation (no state transition, conversation will end)
            context["conversation_ended"] = True
            return None
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None


class AsyncEscalationHandler(AsyncStateHandler):
    """Handler for the ESCALATION state."""
    
    def __init__(self):
        """Initialize the escalation handler."""
        super().__init__(ConversationState.ESCALATION)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the ESCALATION state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Handle escalation if there's an escalation agent
        if context.get("escalation_agent"):
            agent = context["escalation_agent"]
            escalation_result = await agent.process_input("escalate", context)
            
            # Store the escalation result in the context
            context["escalation_result"] = escalation_result
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the ESCALATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        # No transitions from ESCALATION, as it's a terminal state
        return None


class AsyncErrorHandler(AsyncStateHandler):
    """Handler for the ERROR state."""
    
    def __init__(self):
        """Initialize the error handler."""
        super().__init__(ConversationState.ERROR)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the ERROR state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Log the error
        error_message = context.get("error_message", "Unknown error")
        logger.error(f"FSM entered ERROR state: {error_message}")
        
        # Generate an error message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            error_response = await agent.process_input(
                f"I'm sorry, but there was an error: {error_message}. " +
                "Would you like to try again or speak to a staff member?",
                {"error_occurred": True}
            )
            
            # Store the error response in the context
            context["error_response"] = error_response
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the ERROR state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        elif event == ConversationEvent.START_ORDER:
            # Reset and go back to ORDERING
            context["cart"] = {"items": [], "total_price": 0}
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.START_CONVERSATION:
            # Reset and go back to GREETING
            return ConversationState.GREETING
        
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
        
        if next_state is not None:
            await self.transition_to(next_state)
        else:
            logger.info(f"Event {event} does not cause a state transition")
            
            # Handle the event in the current state
            handler = self.handlers.get(self.current_state)
            if handler:
                await handler.handle_event(event, self.context)
    
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
        Extract an event from a transcript based on the current state.
        
        Args:
            transcript: The transcript to analyze
            
        Returns:
            The extracted event, or None if no event could be determined
        """
        transcript_lower = transcript.lower()
        
        # Common phrases for different events
        greeting_phrases = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        name_phrases = ["my name is", "i'm", "i am", "call me", "this is"]
        order_phrases = ["i want to order", "i'd like to order", "can i order", "i want", "i would like", "give me", "i'll have"]
        menu_phrases = ["what's on the menu", "what do you have", "tell me about", "what's your", "do you have"]
        complete_phrases = ["that's all", "that's it", "i'm done", "finish my order", "complete my order", "place my order"]
        confirm_phrases = ["yes", "confirm", "sounds good", "correct", "that's right", "yeah", "yep", "please", "sure"]
        reject_phrases = ["no", "cancel", "change", "modify", "wrong", "incorrect", "that's not right", "nope"]
        follow_up_phrases = ["anything else", "what else", "more information", "tell me more", "another question"]
        escalation_phrases = ["manager", "human", "person", "staff", "talk to someone", "speak to someone", "help me"]
        
        # State-specific event extraction
        if self.current_state == ConversationState.GREETING:
            for phrase in name_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.USER_PROVIDES_NAME
            
            # Default to providing name even if no explicit phrase
            return ConversationEvent.USER_PROVIDES_NAME
        
        elif self.current_state == ConversationState.MAIN_MENU:
            for phrase in order_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.START_ORDER
            
            for phrase in menu_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_MENU_INFO
            
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # If ordering phrases are detected, start order
            if "order" in transcript_lower:
                return ConversationEvent.START_ORDER
            
            # Default to starting an order if no specific intent
            return ConversationEvent.START_ORDER
        
        elif self.current_state == ConversationState.ORDERING:
            for phrase in complete_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.COMPLETE_ORDER
            
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # If there are items in the cart and they say "that's it", complete the order
            if (self.context.get("cart", {}).get("items", []) and 
                ("that's it" in transcript_lower or "that is it" in transcript_lower)):
                return ConversationEvent.COMPLETE_ORDER
            
            # Default: no specific event, stay in current state with ADD_ITEM
            return ConversationEvent.ADD_ITEM
        
        elif self.current_state == ConversationState.VALIDATION:
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # No default event for validation, let the validation handler determine
            return None
        
        elif self.current_state == ConversationState.CONFIRMATION:
            for phrase in confirm_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.CONFIRM_ORDER
            
            for phrase in reject_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REJECT_ORDER
            
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # If transcript looks like a confirmation, confirm the order
            if "okay" in transcript_lower or "k" == transcript_lower:
                return ConversationEvent.CONFIRM_ORDER
            
            # No default event for confirmation
            return None
        
        elif self.current_state == ConversationState.FULFILLMENT:
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # No default event for fulfillment
            return None
        
        elif self.current_state == ConversationState.COMPLETION:
            for phrase in follow_up_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_FOLLOW_UP
            
            # Default to follow-up
            return ConversationEvent.REQUEST_FOLLOW_UP
        
        elif self.current_state == ConversationState.FOLLOW_UP:
            for phrase in order_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.START_ORDER
            
            for phrase in escalation_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.REQUEST_ESCALATION
            
            # If they say "goodbye" or similar, complete the interaction
            goodbye_phrases = ["goodbye", "bye", "thank you", "thanks", "done"]
            for phrase in goodbye_phrases:
                if phrase in transcript_lower:
                    return ConversationEvent.COMPLETE_INTERACTION
            
            # No default event for follow-up
            return None
        
        # Default fallback
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