"""
Main menu state handler for the conversation FSM.

This module contains the handler for the MAIN_MENU state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

class AsyncMainMenuHandler(AsyncStateHandler):
    """Handler for the MAIN_MENU state."""
    
    def __init__(self):
        """Initialize the main menu handler."""
        super().__init__(ConversationState.MAIN_MENU)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the MAIN_MENU state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Generate a main menu message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            main_menu = await agent._handle_main_menu("")
            
            # Store the main menu message in the context
            context["main_menu_response"] = main_menu
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the MAIN_MENU state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.REQUEST_MENU_INFO:
            # Stay in the same state, but set a flag for menu info request
            context["requesting_menu_info"] = True
            return None
        
        elif event == ConversationEvent.START_ORDER:
            # Transition to ORDERING
            return ConversationState.ORDERING
        
        elif event == ConversationEvent.REQUEST_ESCALATION:
            # Transition to ESCALATION
            return ConversationState.ESCALATION
        
        return None