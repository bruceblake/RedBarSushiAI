"""
HSM-based Validation state handler.

This module contains the HSM handler for the VALIDATION state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class ValidationHSMHandler(HSMStateHandler):
    """Handler for the VALIDATION state in HSM."""
    
    def __init__(self):
        """Initialize the validation handler."""
        super().__init__(ConversationHSMStates.VALIDATION)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the VALIDATION state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        logger.info("Entered VALIDATION state - validating order")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the VALIDATION state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.ORDER_VALID:
            # Order is valid - transition to CONFIRMATION
            logger.info("Order validation successful, transitioning to CONFIRMATION")
            return ConversationHSMStates.CONFIRMATION
        
        elif event.name == ConversationHSMEvents.ORDER_INVALID:
            # Order is invalid - transition back to ORDERING
            logger.info("Order validation failed, transitioning back to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.MODIFY_ORDER:
            # User wants to modify order - transition to ORDERING
            logger.info("User wants to modify order, transitioning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.USER_REQUESTS_CANCELLATION:
            # User wants to cancel - transition to GLOBAL_CANCELLATION
            logger.info("User requesting cancellation, transitioning to GLOBAL_CANCELLATION")
            return ConversationHSMStates.GLOBAL_CANCELLATION
        
        elif event.name == ConversationHSMEvents.REQUEST_HELP:
            # User requesting help - transition to GLOBAL_HELP
            logger.info("User requesting help, transitioning to GLOBAL_HELP")
            return ConversationHSMStates.GLOBAL_HELP
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # User requesting escalation - transition to ESCALATION
            logger.info("User requesting escalation, transitioning to ESCALATION")
            return ConversationHSMStates.ESCALATION
        
        return None