#!/usr/bin/env python3
"""
Test the LLM-based intent detection system.
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.intent_detector_async import intent_detector
from app.fsm.core import ConversationState, ConversationEvent

async def test_intent_detection():
    """Test various intents in different states."""
    
    test_cases = [
        # (state, transcript, expected_event_name)
        (ConversationState.GREETING, "My name is John", "USER_PROVIDES_NAME"),
        (ConversationState.GREETING, "John Smith", "USER_PROVIDES_NAME"),
        (ConversationState.GREETING, "I don't want to tell you", "USER_PROVIDES_NAME"),
        
        (ConversationState.MAIN_MENU, "I'd like to order some sushi", "START_ORDER"),
        (ConversationState.MAIN_MENU, "What kind of rolls do you have?", "REQUEST_MENU_INFO"),
        (ConversationState.MAIN_MENU, "Can I get two California rolls", "START_ORDER"),
        (ConversationState.MAIN_MENU, "Are you open right now?", "REQUEST_MENU_INFO"),
        (ConversationState.MAIN_MENU, "I need to speak to a manager", "REQUEST_ESCALATION"),
        
        (ConversationState.ORDERING, "Add a spicy tuna roll", None),  # No event, handled by cart
        (ConversationState.ORDERING, "That's all for now", "COMPLETE_ORDER"),
        (ConversationState.ORDERING, "I'm done ordering", "COMPLETE_ORDER"),
        (ConversationState.ORDERING, "Actually, cancel everything", "CANCEL_ORDER"),
        
        (ConversationState.CONFIRMATION, "Yes, that's correct", "CONFIRM_ORDER"),
        (ConversationState.CONFIRMATION, "No, I need to change something", "REJECT_ORDER"),
        (ConversationState.CONFIRMATION, "Actually can I add one more item", "REJECT_ORDER"),
    ]
    
    print("Testing LLM Intent Detection")
    print("=" * 60)
    
    for state, transcript, expected in test_cases:
        try:
            event = await intent_detector.detect_intent(
                transcript=transcript,
                current_state=state,
                context={}
            )
            
            event_name = event.name if event else None
            status = "✓" if event_name == expected else "✗"
            
            print(f"{status} State: {state.name:15} | Input: '{transcript[:40]:40}' | Expected: {expected or 'None':20} | Got: {event_name or 'None'}")
            
        except Exception as e:
            print(f"✗ Error testing '{transcript}': {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_intent_detection())