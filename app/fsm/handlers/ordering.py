"""
Ordering state handler for the conversation FSM.

This module contains the handler for the ORDERING state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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