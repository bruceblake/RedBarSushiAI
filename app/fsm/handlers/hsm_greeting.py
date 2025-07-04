"""
HSM-based Greeting state handler.

This module contains the HSM handler for the GREETING state.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.hsm_core import HSMStateHandler, HSMEvent, ConversationHSMStates, ConversationHSMEvents
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class GreetingHSMHandler(HSMStateHandler):
    """Handler for the GREETING state in HSM."""
    
    def __init__(self):
        """Initialize the greeting handler."""
        super().__init__(ConversationHSMStates.GREETING)
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering the GREETING state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        await super().on_enter(context, event)
        
        # Only generate greeting if we haven't already done so
        if not context.get("greeting_sent", False):
            # Generate a greeting message if there's a frontline agent
            if context.get("frontline_agent"):
                agent = context["frontline_agent"]
                greeting = await agent.process_voice_input("", {"first_interaction": True})
                
                # Store the greeting in the context
                context["greeting_response"] = greeting
                context["greeting_sent"] = True
                logger.info("Generated greeting message")
            else:
                logger.warning("No frontline agent available for greeting")
        else:
            logger.info("Greeting already sent, skipping")
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle events in the GREETING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state name if a transition should occur, None otherwise
        """
        if event.name == ConversationHSMEvents.USER_PROVIDES_NAME:
            # The AI intent detector has already determined this is a name response
            # The agent should extract the name using its AI capabilities
            logger.info(f"USER_PROVIDES_NAME event received. Transcript: '{context.get('transcript', '')}'")
            
            # Transition to MAIN_MENU - the agent will handle name extraction
            logger.info("Transitioning from GREETING to MAIN_MENU")
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.USER_GREETS:
            # User said hello/greeting - stay in greeting and respond appropriately
            logger.info("User greeted us, staying in GREETING state")
            return None
        
        elif event.name == ConversationHSMEvents.REQUEST_MENU_INFO:
            # User immediately asks about menu - transition to MAIN_MENU
            logger.info("User requesting menu info, transitioning to MAIN_MENU")
            return ConversationHSMStates.MAIN_MENU
        
        elif event.name == ConversationHSMEvents.START_ORDER:
            # User immediately wants to order - transition to ORDERING
            logger.info("User wants to start ordering, transitioning to ORDERING")
            return ConversationHSMStates.ORDERING
        
        return None