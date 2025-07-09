"""
HSM-based Initial state handler.

This module contains the HSM handler for the INITIAL state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class InitialHSMHandler(HSMStateHandler):
    """Handler for the INITIAL state in HSM."""
    
    def __init__(self):
        """Initialize the initial state handler."""
        super().__init__(ConversationHSMStates.INITIAL)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the INITIAL state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        logger.info("System initialized and ready to start conversation")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the INITIAL state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        logger.info(f"InitialHSMHandler: Received event {event.name}")
        
        if event.name == ConversationHSMEvents.START_CONVERSATION:
            # Transition to ACTIVE.GREETING to start the conversation
            logger.info("START_CONVERSATION event received, transitioning to ACTIVE.GREETING")
            return ConversationHSMStates.GREETING
        
        logger.info(f"InitialHSMHandler: No handler for event {event.name}")
        return None