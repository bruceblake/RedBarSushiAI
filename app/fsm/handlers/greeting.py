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
        
        # Generate a greeting message if there's a frontline agent
        if context.get("frontline_agent"):
            agent = context["frontline_agent"]
            greeting = await agent.process_voice_input("", {"first_interaction": True})
            
            # Store the greeting in the context
            context["greeting_response"] = greeting
    
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
            # Extract the user's name if possible
            if "transcript" in context:
                # Simple name extraction (would be more sophisticated in production)
                name_indicators = ["my name is", "i'm", "i am", "call me", "this is"]
                transcript = context["transcript"].lower()
                
                for indicator in name_indicators:
                    if indicator in transcript:
                        start_idx = transcript.find(indicator) + len(indicator)
                        name_part = transcript[start_idx:].strip()
                        
                        # Extract first word as name
                        if name_part:
                            words = name_part.split()
                            if words:
                                context["customer_name"] = words[0]
                                break
            
            # Transition to MAIN_MENU
            return ConversationState.MAIN_MENU
        
        return None