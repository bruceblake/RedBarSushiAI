#!/usr/bin/env python3
"""
Debug the logger error by tracing exactly where it occurs.
"""

import asyncio
import traceback
import sys

async def debug_logger_error():
    """Debug the logger error in orchestrator."""
    try:
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        
        # Try to trigger the error
        print("Testing orchestrator...")
        
        call_sid = "debug_test"
        
        # Initialize first  
        await async_agent_orchestrator.initialize()
        
        # Now try the problematic call
        response = await async_agent_orchestrator.process_voice_input(
            call_sid,
            "cancel my order",
            {"session_id": call_sid, "voice_mode": "api_call"}
        )
        
        print("SUCCESS: No error occurred")
        print(f"Response: {response.get('text', '')[:100]}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nFull traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_logger_error())