"""
Follow-up state handler for the conversation FSM.

This module contains the handler for the FOLLOW_UP state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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