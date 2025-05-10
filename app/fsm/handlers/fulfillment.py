"""
Fulfillment state handler for the conversation FSM.

This module contains the handler for the FULFILLMENT state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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