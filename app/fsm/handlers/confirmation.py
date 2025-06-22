"""
Confirmation state handler for the conversation FSM.

This module contains the handler for the CONFIRMATION state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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
            cart = context["cart"]
            confirmation = await agent._generate_confirmation_prompt(cart)
            
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