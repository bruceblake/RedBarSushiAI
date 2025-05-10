"""
Escalation state handler for the conversation FSM.

This module contains the handler for the ESCALATION state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

class AsyncEscalationHandler(AsyncStateHandler):
    """Handler for the ESCALATION state."""
    
    def __init__(self):
        """Initialize the escalation handler."""
        super().__init__(ConversationState.ESCALATION)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the ESCALATION state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Handle escalation if there's an escalation agent
        if context.get("escalation_agent"):
            agent = context["escalation_agent"]
            escalation_result = await agent.process_input("escalate", context)
            
            # Store the escalation result in the context
            context["escalation_result"] = escalation_result
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the ESCALATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        # No transitions from ESCALATION, as it's a terminal state
        return None