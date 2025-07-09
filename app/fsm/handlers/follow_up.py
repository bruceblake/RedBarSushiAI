"""
HSM-based Follow-up state handler.

This module contains the HSM handler for the FOLLOW_UP state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class FollowUpHSMHandler(HSMStateHandler):
    """Handler for the FOLLOW_UP state in HSM."""
    
    def __init__(self):
        """Initialize the follow-up handler."""
        super().__init__(ConversationHSMStates.FOLLOW_UP)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the FOLLOW_UP state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        logger.info("Entered FOLLOW_UP state - handling follow-up questions")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the FOLLOW_UP state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.START_ORDER:
            # User wants to start another order - transition to ORDERING
            logger.info("User wants to start new order, transitioning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.REQUEST_MENU_INFO:
            # User wants menu info - transition to MAIN_MENU
            logger.info("User requesting menu info, transitioning to MAIN_MENU")
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.USER_SAYS_GOODBYE:
            # User is ending conversation - transition to COMPLETION
            logger.info("User saying goodbye, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        elif event.name == ConversationHSMEvents.END_CONVERSATION:
            # Conversation ending - transition to COMPLETION
            logger.info("Conversation ending, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        elif event.name == ConversationHSMEvents.REQUEST_HELP:
            # User requesting help - transition to GLOBAL_HELP
            logger.info("User requesting help, transitioning to GLOBAL_HELP")
            return ConversationHSMStates.GLOBAL_HELP
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # User requesting escalation - transition to ESCALATION
            logger.info("User requesting escalation, transitioning to ESCALATION")
            return ConversationHSMStates.ESCALATION
        
        return None