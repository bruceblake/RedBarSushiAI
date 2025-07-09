"""
HSM-based Completion state handler.

This module contains the HSM handler for the COMPLETION state.
"""

import logging
import time
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class CompletionHandler(HSMStateHandler):
    """Handler for the COMPLETION state."""
    
    def __init__(self):
        """Initialize the completion handler."""
        super().__init__(ConversationHSMStates.COMPLETION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the COMPLETION state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Log conversation completion
        session_start = context.get("session_started_at", time.time())
        duration = time.time() - session_start
        
        cart = context.get("cart", {})
        items_count = len(cart.get("items", []))
        total_price = cart.get("total_price", 0)
        
        logger.info(f"Conversation completed after {duration:.1f} seconds")
        logger.info(f"Order summary: {items_count} items, ${total_price}")
        
        # Mark conversation as completed
        context["conversation_completed"] = True
        context["completed_at"] = time.time()
        
        # Generate completion message if there's a frontline agent
        if context.get("frontline_agent"):
            try:
                agent = context["frontline_agent"]
                completion_msg = await agent._generate_completion_message(context)
                context["completion_message"] = completion_msg
                logger.info("Generated completion message")
            except Exception as e:
                logger.error(f"Error generating completion message: {e}")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the COMPLETION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.REQUEST_FOLLOW_UP:
            # Customer wants follow-up service
            logger.info("Customer requesting follow-up, transitioning to FOLLOW_UP")
            return ConversationHSMStates.FOLLOW_UP
        
        elif event.name == ConversationHSMEvents.START_ORDER:
            # Customer wants to place another order
            logger.info("Customer wants to place another order, returning to MAIN_MENU")
            # Clear previous order context
            context.pop("cart", None)
            context.pop("fulfillment", None)
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.USER_SAYS_GOODBYE:
            # Customer saying final goodbye, stay in completion
            logger.info("Customer saying final goodbye")
            return None
        
        elif event.name == ConversationHSMEvents.END_CONVERSATION:
            # Explicit end of conversation
            logger.info("Conversation explicitly ended")
            return None
        
        return None