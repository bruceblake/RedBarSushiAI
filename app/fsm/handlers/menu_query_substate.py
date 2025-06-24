"""
Async handler for the menu query substate.

This handler manages when users ask menu questions during other states.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

logger = logging.getLogger(__name__)


class AsyncMenuQuerySubstateHandler(AsyncStateHandler):
    """Handler for the menu query substate."""
    
    def __init__(self):
        """Initialize the menu query substate handler."""
        super().__init__(ConversationState.MENU_QUERY_SUBSTATE)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the menu query substate.
        
        Store the previous state and prepare for menu questions.
        """
        logger.info(f"Entering menu query substate from {context.get('previous_fsm_state', 'unknown')}")
        
        # The orchestrator should route to the menu agent
        context['preferred_agent'] = 'menu'
        context['in_menu_query'] = True
    
    async def on_exit(self, context: Dict[str, Any]) -> None:
        """
        Called when exiting the menu query substate.
        """
        logger.info("Exiting menu query substate")
        
        # Clear the menu query flag
        context.pop('in_menu_query', None)
        context.pop('preferred_agent', None)
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the menu query substate.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur
        """
        logger.info(f"Menu query substate handling event: {event}")
        
        # Menu query resolved - return to previous state
        if event == ConversationEvent.MENU_QUERY_RESOLVED:
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