#!/usr/bin/env python3
"""
Debug FSM greeting loop issue.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.fsm.core import ConversationState, ConversationEvent, AsyncConversationFSM
from app.utils.intent_detector_async import intent_detector

async def simulate_conversation():
    """Simulate a conversation to debug FSM transitions."""
    
    # Create FSM instance
    fsm = AsyncConversationFSM("TEST_CALL_123")
    
    print("=== FSM State Transition Test ===")
    print(f"Initial state: {fsm.current_state.name}")
    
    # Start conversation
    await fsm.trigger(ConversationEvent.START_CONVERSATION)
    print(f"After START_CONVERSATION: {fsm.current_state.name}")
    
    # Simulate user saying their name
    test_responses = [
        "John",
        "My name is Sarah",
        "I'm Mike",
        "Call me Lisa"
    ]
    
    for response in test_responses:
        print(f"\n--- Testing response: '{response}' ---")
        
        # Update transcript
        fsm.update_context({"transcript": response})
        
        # Process transcript
        await fsm.process_transcript(response)
        
        # Check state
        print(f"Current state after processing: {fsm.current_state.name}")
        print(f"Customer name in context: {fsm.context.get('customer_name', 'Not set')}")
        
        # If we're in MAIN_MENU, test ordering
        if fsm.current_state == ConversationState.MAIN_MENU:
            print("\n--- Now in MAIN_MENU, testing order request ---")
            order_request = "I'd like to order some sushi"
            fsm.update_context({"transcript": order_request})
            await fsm.process_transcript(order_request)
            print(f"State after order request: {fsm.current_state.name}")
            break

async def test_intent_detection_flow():
    """Test the intent detection for common greeting responses."""
    
    print("\n\n=== Intent Detection Test ===")
    
    test_cases = [
        ("John", ConversationState.GREETING),
        ("My name is Sarah", ConversationState.GREETING),
        ("I don't want to give my name", ConversationState.GREETING),
        ("What?", ConversationState.GREETING),
        ("I'd like to order", ConversationState.MAIN_MENU),
        ("What's on the menu?", ConversationState.MAIN_MENU),
    ]
    
    for transcript, state in test_cases:
        event = await intent_detector.detect_intent(transcript, state, {})
        print(f"State: {state.name:15} | Input: '{transcript:30}' | Event: {event.name if event else 'None'}")

async def main():
    """Run all tests."""
    await simulate_conversation()
    await test_intent_detection_flow()

if __name__ == "__main__":
    asyncio.run(main())