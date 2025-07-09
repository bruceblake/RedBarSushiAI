"""
HSM-based Escalation state handler.

This module contains the HSM handler for the ESCALATION state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class EscalationHSMHandler(HSMStateHandler):
    """Handler for the ESCALATION state in HSM."""
    
    def __init__(self):
        """Initialize the escalation handler."""
        super().__init__(ConversationHSMStates.ESCALATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the ESCALATION state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        logger.info("Entered ESCALATION state - escalating to human agent")
        
        # Set escalation flag in context
        context["escalation_requested"] = True
        context["escalation_reason"] = event.data.get("reason", "User requested escalation")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the ESCALATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.COMPLETE_INTERACTION:
            # Escalation complete - transition to COMPLETION
            logger.info("Escalation complete, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        elif event.name == ConversationHSMEvents.FALLBACK_TO_MAIN_MENU:
            # Fallback to main menu - transition to MAIN_MENU
            logger.info("Falling back to main menu, transitioning to MAIN_MENU")
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.END_CONVERSATION:
            # Conversation ending - transition to COMPLETION
            logger.info("Conversation ending, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        elif event.name == ConversationHSMEvents.ERROR_OCCURRED:
            # Error occurred - transition to ERROR_RECOVERY
            logger.info("Error occurred during escalation, transitioning to ERROR_RECOVERY")
            return ConversationHSMStates.ERROR_RECOVERY
        
        return None