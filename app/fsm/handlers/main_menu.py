"""
HSM-based Main Menu state handler.

This module contains the HSM handler for the MAIN_MENU state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class MainMenuHSMHandler(HSMStateHandler):
    """Handler for the MAIN_MENU state in HSM."""
    
    def __init__(self):
        """Initialize the main menu handler."""
        super().__init__(ConversationHSMStates.MAIN_MENU)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the MAIN_MENU state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Generate a main menu message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            try:
                main_menu = await agent._handle_main_menu("")
                # Store the main menu message in the context
                context["main_menu_response"] = main_menu
                logger.info("Generated main menu response")
            except Exception as e:
                logger.error(f"Error generating main menu response: {e}")
        else:
            logger.warning("No frontline agent available for main menu")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the MAIN_MENU state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.REQUEST_MENU_INFO:
            # Stay in the same state, but set a flag for menu info request
            context["requesting_menu_info"] = True
            logger.info("User requesting menu info, staying in MAIN_MENU")
            return None
        
        elif event.name == ConversationHSMEvents.START_ORDER:
            # Transition to ORDERING
            logger.info("User starting order, transitioning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        elif event.name == ConversationHSMEvents.REQUEST_ESCALATION:
            # Transition to ESCALATION
            logger.info("User requesting escalation, transitioning to ESCALATION")
            return ConversationHSMStates.ESCALATION
        
        elif event.name == ConversationHSMEvents.REQUEST_HELP:
            # Transition to GLOBAL_HELP
            logger.info("User requesting help, transitioning to GLOBAL_HELP")
            return ConversationHSMStates.GLOBAL_HELP
        
        elif event.name == ConversationHSMEvents.USER_REQUESTS_CANCELLATION:
            # Transition to GLOBAL_CANCELLATION
            logger.info("User requesting cancellation, transitioning to GLOBAL_CANCELLATION")
            return ConversationHSMStates.GLOBAL_CANCELLATION
        
        elif event.name == ConversationHSMEvents.USER_SAYS_GOODBYE:
            # Transition to COMPLETION
            logger.info("User saying goodbye, transitioning to COMPLETION")
            return ConversationHSMStates.COMPLETION
        
        return None