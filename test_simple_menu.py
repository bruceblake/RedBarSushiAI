#!/usr/bin/env python3
"""Simple test to debug the menu agent test."""

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
    response = await orchestrator.start_new_conversation(session_id, {"test": True})
    print(f"Start conversation response: {response}")
    
    # Mock the frontline agent
    orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
        "text": "Let me show you our menu. We have delicious sushi rolls...",
        "agent": "FrontlineVoiceAI",
        "handled": True,
        "delegated_to": "menu"
    })
    
    # Ask about menu
    response = await orchestrator.process_voice_input(session_id, "What's on your menu?")
    print(f"Menu query response: {response}")
    
    # Check response
    assert response is not None, "Response is None"
    assert "menu" in response.get("text", "").lower() or response.get("delegated_to") == "menu", f"Response doesn't mention menu: {response}"
    
    print("Test passed!")

if __name__ == "__main__":
    asyncio.run(test_menu())