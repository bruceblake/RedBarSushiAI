"""
HSM-based Global state handlers.

This module contains the HSM handlers for global states that can be entered from anywhere.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.hsm_core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class GlobalInquirySuperStateHandler(HSMStateHandler):
    """Handler for the GLOBAL_INQUIRY superstate."""
    
    def __init__(self):
        """Initialize the global inquiry superstate handler."""
        super().__init__(ConversationHSMStates.GLOBAL_INQUIRY)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the GLOBAL_INQUIRY superstate.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Store the previous state for return navigation
        if "state_stack" not in context:
            context["state_stack"] = []
        
        # Save where we came from (get from HSM state store)
        call_sid = context.get("call_sid")
        if call_sid:
            from app.fsm.hsm_manager import hsm_manager
            try:
                current_states = await hsm_manager.get_current_states(call_sid)
                if len(current_states) > 1:  # Don't save GLOBAL_INQUIRY itself
                    previous_state = current_states[-2]
                    context["state_stack"].append(previous_state)
                    logger.info(f"Saved previous state for return: {previous_state}")
            except Exception as e:
                logger.error(f"Error saving previous state: {e}")
        
        logger.info("Entered global inquiry mode")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the GLOBAL_INQUIRY superstate level.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.INQUIRY_RESOLVED:
            # Inquiry completed, return to previous state
            state_stack = context.get("state_stack", [])
            if state_stack:
                previous_state = state_stack.pop()
                logger.info(f"Inquiry resolved, returning to: {previous_state}")
                return previous_state
            else:
                logger.info("Inquiry resolved, defaulting to MAIN_MENU")
                return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.INQUIRY_COMPLETE:
            # Same as resolved
            return await self.handle_event(
                HSMEvent(ConversationHSMEvents.INQUIRY_RESOLVED, event.data),
                context
            )
        
        # Not handled at this level, will bubble down to substates
        return None


class InquiryMenuHandler(HSMStateHandler):
    """Handler for GLOBAL_INQUIRY.MENU substate."""
    
    def __init__(self):
        """Initialize the inquiry menu handler."""
        super().__init__(ConversationHSMStates.INQUIRY_MENU)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the INQUIRY_MENU state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.REQUEST_MENU_INFO:
            # Handling menu inquiry, stay in this state
            logger.info("Processing menu information request")
            context["requesting_menu_info"] = True
            return None
        
        elif event.name == ConversationHSMEvents.ASK_ABOUT_ITEM:
            # Specific item inquiry
            logger.info("Processing specific item inquiry")
            return None
        
        return None


class InquiryHoursHandler(HSMStateHandler):
    """Handler for GLOBAL_INQUIRY.HOURS substate."""
    
    def __init__(self):
        """Initialize the inquiry hours handler."""
        super().__init__(ConversationHSMStates.INQUIRY_HOURS)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle events in the INQUIRY_HOURS state."""
        # Hours inquiries are typically straightforward
        logger.info("Processing hours inquiry")
        return None


class InquiryLocationHandler(HSMStateHandler):
    """Handler for GLOBAL_INQUIRY.LOCATION substate."""
    
    def __init__(self):
        """Initialize the inquiry location handler."""
        super().__init__(ConversationHSMStates.INQUIRY_LOCATION)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle events in the INQUIRY_LOCATION state."""
        # Location inquiries are typically straightforward
        logger.info("Processing location inquiry")
        return None


class InquiryPoliciesHandler(HSMStateHandler):
    """Handler for GLOBAL_INQUIRY.POLICIES substate."""
    
    def __init__(self):
        """Initialize the inquiry policies handler."""
        super().__init__(ConversationHSMStates.INQUIRY_POLICIES)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle events in the INQUIRY_POLICIES state."""
        # Policy inquiries (delivery, refund, etc.)
        logger.info("Processing policy inquiry")
        return None


class GlobalHelpHandler(HSMStateHandler):
    """Handler for the GLOBAL_HELP state."""
    
    def __init__(self):
        """Initialize the global help handler."""
        super().__init__(ConversationHSMStates.GLOBAL_HELP)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the GLOBAL_HELP state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Generate help message if frontline agent available
        if context.get("frontline_agent"):
            try:
                agent = context["frontline_agent"]
                help_msg = await agent._generate_help_message(context)
                context["help_message"] = help_msg
                logger.info("Generated help message")
            except Exception as e:
                logger.error(f"Error generating help message: {e}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the GLOBAL_HELP state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.INQUIRY_COMPLETE:
            # Help provided, return to previous state
            state_stack = context.get("state_stack", [])
            if state_stack:
                previous_state = state_stack.pop()
                logger.info(f"Help complete, returning to: {previous_state}")
                return previous_state
            else:
                logger.info("Help complete, defaulting to MAIN_MENU")
                return ConversationHSMStates.MAIN_MENU
        
        return None


class GlobalCancellationSuperStateHandler(HSMStateHandler):
    """Handler for the GLOBAL_CANCELLATION superstate."""
    
    def __init__(self):
        """Initialize the global cancellation superstate handler."""
        super().__init__(ConversationHSMStates.GLOBAL_CANCELLATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the GLOBAL_CANCELLATION superstate.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        logger.warning("User requesting cancellation")
        
        # Store cancellation context
        context["cancellation"] = {
            "requested_at": context.get("timestamp"),
            "cart_at_cancellation": context.get("cart", {}),
            "confirmed": False
        }
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events at the GLOBAL_CANCELLATION superstate level.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.CONFIRM_CANCELLATION:
            # Cancellation confirmed
            logger.info("Cancellation confirmed by user")
            context["cancellation"]["confirmed"] = True
            
            # Clear order context
            context.pop("cart", None)
            context.pop("fulfillment", None)
            
            # Return to main menu
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.DECLINE_CANCELLATION:
            # User doesn't want to cancel
            logger.info("Cancellation declined by user")
            
            # Return to previous state
            state_stack = context.get("state_stack", [])
            if state_stack:
                previous_state = state_stack.pop()
                return previous_state
            else:
                return ConversationHSMStates.MAIN_MENU
        
        # Not handled at this level, will bubble down to substates
        return None


class CancellationPendingHandler(HSMStateHandler):
    """Handler for GLOBAL_CANCELLATION.PENDING substate."""
    
    def __init__(self):
        """Initialize the cancellation pending handler."""
        super().__init__(ConversationHSMStates.CANCELLATION_PENDING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the CANCELLATION_PENDING state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Generate cancellation confirmation prompt
        if context.get("frontline_agent"):
            try:
                agent = context["frontline_agent"]
                cancel_prompt = await agent._generate_cancellation_prompt(context)
                context["cancellation"]["prompt"] = cancel_prompt
                logger.info("Generated cancellation confirmation prompt")
            except Exception as e:
                logger.error(f"Error generating cancellation prompt: {e}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CANCELLATION_PENDING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name in [ConversationHSMEvents.CONFIRM_CANCELLATION, ConversationHSMEvents.DECLINE_CANCELLATION]:
            # Move to confirmed state to handle the response
            return ConversationHSMStates.CANCELLATION_CONFIRMED
        
        return None


class CancellationConfirmedHandler(HSMStateHandler):
    """Handler for GLOBAL_CANCELLATION.CONFIRMED substate."""
    
    def __init__(self):
        """Initialize the cancellation confirmed handler."""
        super().__init__(ConversationHSMStates.CANCELLATION_CONFIRMED)
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the CANCELLATION_CONFIRMED state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        # This state handles the final cancellation processing
        # Events are handled by the superstate
        return None