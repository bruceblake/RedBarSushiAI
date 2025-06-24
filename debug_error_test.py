#!/usr/bin/env python3
"""Debug the error handling test to see what response is returned."""

import asyncio
from unittest.mock import AsyncMock
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from sqlalchemy.ext.asyncio import AsyncSession

async def test_error_handling():
    """Test error handling to see actual response."""
    orchestrator = AsyncAgentOrchestrator()
    mock_db = AsyncMock(spec=AsyncSession)
    await orchestrator.initialize(db=mock_db)
    
    session_id = "test_errors"
    await orchestrator.start_new_conversation(session_id, {"test": True})
    
    # Mock agent to raise error
    orchestrator.frontline_agent.process_voice_input = AsyncMock(
        side_effect=Exception("Agent processing failed")
    )
    
    response = await orchestrator.process_voice_input(session_id, "Show menu")
    
    print(f"\nResponse received: {response}")
    print(f"\nResponse keys: {response.keys()}")
    print(f"\nResponse text: {response.get('text', 'NO TEXT')}")
    print(f"\n'error' in response: {'error' in response}")
    print(f"\n'Error' in response text: {'Error' in response.get('text', '')}")
    
    return response

if __name__ == "__main__":
    asyncio.run(test_error_handling())