#!/usr/bin/env python3
"""Test script for name recognition in the frontline agent."""

import asyncio
import logging
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI

# Configure logging to see all the critical logs
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_name_recognition():
    """Test various name input formats."""
    agent = AsyncFrontlineVoiceAgentAI()
    
    # Test cases
    test_inputs = [
        "Bruce",
        "My name is Sarah",
        "I'm John",
        "This is Mike",
        "It's David",
        "bruce",  # lowercase
        "Hi, I'm Jennifer",
        "Hello, my name is Robert"
    ]
    
    print("=" * 80)
    print("TESTING NAME RECOGNITION")
    print("=" * 80)
    
    for test_input in test_inputs:
        print(f"\n\nTEST INPUT: '{test_input}'")
        print("-" * 40)
        
        # Reset agent state for each test
        agent.conversation_state = "GREETING"
        agent.context["customer_name"] = None
        
        # Process the input
        response = await agent.process_voice_input(test_input, {})
        
        print(f"\nRESULT:")
        print(f"  Customer name set: {agent.context.get('customer_name')}")
        print(f"  Agent state: {agent.conversation_state}")
        print(f"  Response text: {response.get('text', '')[:100]}...")
        print(f"  Tool calls made: {len(response.get('tool_calls', []))}")
        print(f"  Actions: {response.get('actions', [])}")

if __name__ == "__main__":
    asyncio.run(test_name_recognition())