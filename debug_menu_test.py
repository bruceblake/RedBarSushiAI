#!/usr/bin/env python3
"""Debug the menu test."""

import asyncio
from unittest.mock import AsyncMock
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator

async def test_menu():
    # Create orchestrator
    orchestrator = AsyncAgentOrchestrator()
    mock_db = AsyncMock()
    await orchestrator.initialize(db=mock_db)
    
    # Start conversation
    session_id = "test_menu"
    await orchestrator.start_new_conversation(session_id, {"test": True})
    
    # Ask about menu
    response = await orchestrator.process_voice_input(session_id, "What's on your menu?")
    print(f"Response: {response}")
    
    # Check what we get
    print(f"Response text: '{response.get('text', '')}'")
    print(f"Response handled: {response.get('handled')}")
    
    response_text = response.get("text", "").lower()
    print(f"Response text lower: '{response_text}'")
    
    # Check for keywords
    keywords = ["menu", "categories", "items", "sushi", "rolls"]
    for word in keywords:
        if word in response_text:
            print(f"Found keyword: {word}")
    
    has_keyword = any(word in response_text for word in keywords)
    print(f"Has keyword: {has_keyword}")

if __name__ == "__main__":
    asyncio.run(test_menu())