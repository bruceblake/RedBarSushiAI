"""
Greeting state handler for the conversation FSM.

This module contains the handler for the GREETING state in the FSM.
"""

import logging
from typing import Dict, Any, Optional

from app.fsm.core import AsyncStateHandler, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

class AsyncGreetingHandler(AsyncStateHandler):
    """Handler for the GREETING state."""
    
    def __init__(self):
        """Initialize the greeting handler."""
        super().__init__(ConversationState.GREETING)
    
    async def on_enter(self, context: Dict[str, Any]) -> None:
        """
        Called when entering the GREETING state.
        
        Args:
            context: The conversation context
        """
        await super().on_enter(context)
        
        # Only generate greeting if we haven't already done so
        if not context.get("greeting_sent", False):
            # Generate a greeting message if there's a frontline agent
            if context.get("frontline_agent"):
                agent = context["frontline_agent"]
                greeting = await agent.process_voice_input("", {"first_interaction": True})
                
                # Store the greeting in the context
                context["greeting_response"] = greeting
                context["greeting_sent"] = True
        else:
            logger.info("Greeting already sent, skipping")
    
    async def handle_event(self, event: ConversationEvent, context: Dict[str, Any]) -> Optional[ConversationState]:
        """
        Handle events in the GREETING state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            The next state if a transition should occur, None otherwise
        """
        await super().handle_event(event, context)
        
        if event == ConversationEvent.USER_PROVIDES_NAME:
            # The AI intent detector has already determined this is a name response
            # The agent should extract the name using its AI capabilities
            logger.info(f"USER_PROVIDES_NAME event received. Transcript: '{context.get('transcript', '')}'")
            
            # Transition to MAIN_MENU - the agent will handle name extraction
            logger.info(f"Transitioning from GREETING to MAIN_MENU")
            return ConversationState.MAIN_MENU
        
        return None