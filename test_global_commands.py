#!/usr/bin/env python3
"""
Test script for global command detection and handling.

This script demonstrates the global command functionality including:
- "repeat that" - Repeats the last assistant message
- "start over" - Resets the conversation
- "go back" - Returns to the previous state
- "help" - Requests assistance
- "cancel" - Cancels the current action
"""

import asyncio
from app.utils.global_commands import (
    GlobalCommand, GlobalCommandDetector, global_command_detector
)


async def test_command_detection():
    """Test various global command patterns."""
    print("Testing Global Command Detection\n" + "="*50 + "\n")
    
    test_cases = [
        # REPEAT commands
        ("Can you repeat that?", GlobalCommand.REPEAT),
        ("What did you just say?", GlobalCommand.REPEAT),
        ("Say that again please", GlobalCommand.REPEAT),
        ("I didn't catch that", GlobalCommand.REPEAT),
        ("Pardon me", GlobalCommand.REPEAT),
        ("Come again?", GlobalCommand.REPEAT),
        
        # START_OVER commands
        ("Let's start over", GlobalCommand.START_OVER),
        ("Start fresh", GlobalCommand.START_OVER),
        ("Begin again", GlobalCommand.START_OVER),
        ("Reset the order", GlobalCommand.START_OVER),
        ("Cancel everything and start over", GlobalCommand.START_OVER),
        
        # GO_BACK commands
        ("Go back", GlobalCommand.GO_BACK),
        ("Previous step", GlobalCommand.GO_BACK),
        ("Undo that", GlobalCommand.GO_BACK),
        ("Take me back", GlobalCommand.GO_BACK),
        ("Let's go back", GlobalCommand.GO_BACK),
        ("I changed my mind", GlobalCommand.GO_BACK),
        
        # HELP commands
        ("Help me", GlobalCommand.HELP),
        ("What can I do?", GlobalCommand.HELP),
        ("I'm confused", GlobalCommand.HELP),
        ("What are my options?", GlobalCommand.HELP),
        ("I need help", GlobalCommand.HELP),
        
        # CANCEL commands
        ("Cancel", GlobalCommand.CANCEL),
        ("Stop everything", GlobalCommand.CANCEL),
        ("Nevermind", GlobalCommand.CANCEL),
        ("End the call", GlobalCommand.CANCEL),
        ("Goodbye", GlobalCommand.CANCEL),
        
        # Non-commands (should return NONE)
        ("I'd like to order a burger", GlobalCommand.NONE),
        ("What's on the menu?", GlobalCommand.NONE),
        ("Add fries to my order", GlobalCommand.NONE),
    ]
    
    detector = GlobalCommandDetector()
    
    for input_text, expected_command in test_cases:
        command, confidence = detector.detect_command(input_text)
        status = "✓" if command == expected_command else "✗"
        print(f"{status} '{input_text}'")
        print(f"   Expected: {expected_command.value}, Got: {command.value}, Confidence: {confidence:.2f}")
        print()


async def test_context_aware_responses():
    """Test how global commands would work in different conversation states."""
    print("\nTesting Context-Aware Global Command Responses\n" + "="*50 + "\n")
    
    # Simulate different conversation states
    states_and_responses = {
        "ORDERING": {
            "go_back": "Okay, let's go back to your order. What would you like to add or change?",
            "repeat": "<last message would be repeated>",
            "start_over": "Let's start fresh. Red Bar Sushi here. How can I help you today?"
        },
        "MAIN_MENU": {
            "go_back": "Sure, let's go back. Would you like to place an order or do you have questions about our menu?",
            "help": "I can help you place an order, answer questions about our menu, or connect you with our staff."
        },
        "VALIDATION": {
            "go_back": "Okay, let's go back to where we were.",
            "repeat": "<order summary would be repeated>"
        }
    }
    
    for state, responses in states_and_responses.items():
        print(f"In {state} state:")
        for command, response in responses.items():
            print(f"  - '{command}' → \"{response}\"")
        print()


async def test_command_variations():
    """Test how well the detector handles variations and mixed commands."""
    print("\nTesting Command Variations and Edge Cases\n" + "="*50 + "\n")
    
    edge_cases = [
        ("repeat repeat repeat", "Testing repeated words"),
        ("can you help me go back", "Mixed commands (help + go back)"),
        ("I want to cancel and start over", "Multiple commands"),
        ("REPEAT THAT", "All caps"),
        ("r e p e a t", "Spaced letters"),
        ("répéat thât", "Accented characters"),
        ("", "Empty input"),
        ("     ", "Whitespace only"),
    ]
    
    detector = GlobalCommandDetector()
    
    for input_text, description in edge_cases:
        command, confidence = detector.detect_command(input_text)
        print(f"Input: '{input_text}' ({description})")
        print(f"Result: {command.value}, Confidence: {confidence:.2f}\n")


async def main():
    """Run all tests."""
    await test_command_detection()
    await test_context_aware_responses()
    await test_command_variations()
    
    print("\nGlobal Command Implementation Summary\n" + "="*50)
    print("""
Global commands provide a way for users to control the conversation flow
regardless of the current state. The implementation includes:

1. REPEAT - Repeats the last assistant message
2. START_OVER - Resets the entire conversation
3. GO_BACK - Returns to the previous conversation state
4. HELP - Requests assistance (maps to escalation)
5. CANCEL - Cancels the current operation

These commands are detected using pattern matching and are handled
before normal intent detection, ensuring they work in any state.
    """)


if __name__ == "__main__":
    asyncio.run(main()