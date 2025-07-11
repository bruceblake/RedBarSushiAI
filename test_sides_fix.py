#!/usr/bin/env python3
"""
Test script to verify that the frontline agent properly follows through 
when customer asks about categories like "sides".
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
from app.agents.cart_async import AsyncCartAgent
from app.db_async import async_session_factory

async def test_sides_request():
    """Test that agent properly handles 'tell me about the sides' request."""
    
    print("🧪 Testing sides request handling...")
    
    # Create database session
    db = async_session_factory()
    
    try:
        # Create agents
        frontline_agent = AsyncFrontlineVoiceAgentAI()
        menu_agent = AsyncMenuAgentEnhanced(db=db)
        cart_agent = AsyncCartAgent(db=db)
        
        # Set up specialist delegation
        frontline_agent.specialists = {
            "menu": menu_agent,
            "cart": cart_agent
        }
        
        # Test the specific request that was failing
        test_input = "Yeah, tell me about the sides."
        
        print(f"📝 Testing input: '{test_input}'")
        
        # Process the request
        response = await frontline_agent.process_voice_input(
            test_input,
            context={
                "session_id": "test_session",
                "hsm_state": "ACTIVE.MAIN_MENU",
                "voice_mode": "test"
            }
        )
        
        print(f"🤖 Response: {response.get('text', 'No text response')}")
        
        # Check if tools were called
        tool_results = response.get('tool_results', [])
        print(f"🔧 Tools called: {len(tool_results)}")
        
        for i, tool_result in enumerate(tool_results):
            tool_name = tool_result.get('tool', 'unknown')
            print(f"   {i+1}. {tool_name}")
            
            # If it's get_items_by_category, show some results
            if tool_name == 'get_items_by_category':
                result = tool_result.get('result', {})
                items = result.get('items', [])
                print(f"      → Found {len(items)} side items")
                for item in items[:3]:  # Show first 3
                    print(f"        - {item.get('name', 'Unknown')} (${item.get('price', 0)})")
        
        # Check if both expected tools were called
        tools_called = [tr.get('tool') for tr in tool_results]
        expected_tools = ['get_menu_categories', 'get_items_by_category']
        
        success = all(tool in tools_called for tool in expected_tools)
        
        if success:
            print("✅ SUCCESS: Agent properly called both get_menu_categories AND get_items_by_category")
        else:
            print("❌ FAILURE: Agent did not call the expected tools")
            print(f"   Expected: {expected_tools}")
            print(f"   Actually called: {tools_called}")
        
        return success
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        await db.close()

async def main():
    """Run the test."""
    print("🧪 Testing Frontline Agent Category Response Fix")
    print("=" * 50)
    
    success = await test_sides_request()
    
    print("=" * 50)
    if success:
        print("🎉 Test PASSED: Agent correctly handles category requests")
    else:
        print("💥 Test FAILED: Agent still has issues")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)