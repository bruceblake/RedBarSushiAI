"""
Error state handler for the conversation FSM.

This module contains the handler for the ERROR state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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