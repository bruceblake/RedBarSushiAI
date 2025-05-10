"""
Validation state handler for the conversation FSM.

This module contains the handler for the VALIDATION state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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