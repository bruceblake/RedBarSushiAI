"""
Async handler for the cancellation pending state.

This handler manages order cancellation confirmation.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

logger = logging.getLogger(__name__)


class AsyncCancellationPendingHandler(AsyncStateHandler):
    """Handler for the cancellation pending state."""
    
    def __init__(self):
        """Initialize the cancellation pending handler."""
        super().__init__(ConversationState.CANCELLATION_PENDING)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the cancellation pending state.
        
        Prompt user to confirm cancellation.
        """
        logger.info(f"Entering cancellation pending state from {context.get('previous_fsm_state', 'unknown')}")
        
        # Set context to indicate we need a cancellation confirmation prompt
        context['needs_cancellation_prompt'] = True
    
    async def on_exit(self, context: Dict[str, Any]) -> None:
        """
        Called when exiting the cancellation pending state.
        """
        logger.info("Exiting cancellation pending state")
        
        # Clear the cancellation prompt flag
        context.pop('needs_cancellation_prompt', None)
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the cancellation pending state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur
        """
        logger.info(f"Cancellation pending state handling event: {event}")
        
        if event == ConversationEvent.CONFIRM_CANCELLATION:
            # User confirmed cancellation
            # Update order status if there's an active order
            if context.get('order_id'):
                context['order_cancelled'] = True
                logger.info(f"Order {context['order_id']} marked for cancellation")
            
            # Clear cart
            context['cart_items'] = []
            context['order_total'] = 0
            
            return ConversationState.COMPLETION
            
        elif event == ConversationEvent.DECLINE_CANCELLATION:
            # User declined cancellation - return to previous state
            previous_state_name = context.get('previous_fsm_state')
            if previous_state_name:
                try:
                    return ConversationState[previous_state_name]
                except KeyError:
                    logger.error(f"Invalid previous state: {previous_state_name}")
                    return ConversationState.MAIN_MENU
            else:
                logger.warning("No previous state stored, returning to MAIN_MENU")
                return ConversationState.MAIN_MENU
        
        # Let base class handle other events
        return None