"""
Completion state handler for the conversation FSM.

This module contains the handler for the COMPLETION state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

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