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
            # Extract the user's name from transcript
            transcript = context.get("transcript", "").strip()
            
            if transcript:
                # For now, use the entire response as the name if it's reasonably short
                # The LLM already detected this is a name response
                if len(transcript.split()) <= 3:  # Likely just a name
                    context["customer_name"] = transcript
                    logger.info(f"Extracted customer name: {transcript}")
                else:
                    # Try to extract name from longer responses
                    name_indicators = ["my name is", "i'm", "i am", "call me", "this is"]
                    transcript_lower = transcript.lower()
                    
                    for indicator in name_indicators:
                        if indicator in transcript_lower:
                            start_idx = transcript_lower.find(indicator) + len(indicator)
                            name_part = transcript[start_idx:].strip()
                            
                            # Extract first word or two as name
                            if name_part:
                                words = name_part.split()
                                if words:
                                    context["customer_name"] = " ".join(words[:2])
                                    logger.info(f"Extracted customer name: {context['customer_name']}")
                                    break
                    
                    # If no name extracted, use a default
                    if "customer_name" not in context:
                        context["customer_name"] = "friend"
                        logger.info("Could not extract name, using 'friend'")
            
            # Always transition to MAIN_MENU after name event
            logger.info(f"Transitioning from GREETING to MAIN_MENU with customer name: {context.get('customer_name', 'Not set')}")
            return ConversationState.MAIN_MENU
        
        return None