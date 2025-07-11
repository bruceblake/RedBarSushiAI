#!/usr/bin/env python3
"""
Debug agent initialization and specialist registration.
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.agents.factory_async import async_agent_factory
from app.db_async import get_db

async def test_agent_debug():
    """Test agent initialization and debug specialists."""
    
    print("🔧 AGENT INITIALIZATION DEBUG")
    print("=" * 60)
    
    # Get database session
    async for db in get_db():
        try:
            print(f"\n📂 Step 1: Create voice agent system")
            
            # Create voice agent system
            frontline_agent = await async_agent_factory.create_voice_agent_system(db=db)
            print(f"   ✅ Frontline agent created: {frontline_agent.name}")
            
            # Check if specialists are registered
            print(f"\n🔍 Step 2: Check registered specialists")
            specialists = getattr(frontline_agent, 'specialists', {})
            print(f"   📝 Specialists dict: {specialists}")
            print(f"   📝 Number of specialists: {len(specialists)}")
            
            for role, agent in specialists.items():
                print(f"   ✅ {role}: {agent.name}")
            
            # Test menu specialist directly
            print(f"\n🍽️ Step 3: Test menu specialist")
            if 'menu' in specialists:
                menu_agent = specialists['menu']
                print(f"   📝 Menu agent: {menu_agent.name}")
                print(f"   📝 Menu agent has db: {hasattr(menu_agent, 'db')}")
                
                # Try to call a tool
                try:
                    result = await menu_agent.execute_tool("list_categories", {})
                    print(f"   ✅ Menu tool call successful: {result}")
                except Exception as e:
                    print(f"   ❌ Menu tool call failed: {e}")
            else:
                print(f"   ❌ No menu specialist found")
            
            # Test cart specialist directly  
            print(f"\n🛒 Step 4: Test cart specialist")
            if 'cart' in specialists:
                cart_agent = specialists['cart']
                print(f"   📝 Cart agent: {cart_agent.name}")
                print(f"   📝 Cart agent has db: {hasattr(cart_agent, 'db')}")
                
                # Try to call a tool
                try:
                    result = await cart_agent.execute_tool("get_cart_summary", {})
                    print(f"   ✅ Cart tool call successful: {result}")
                except Exception as e:
                    print(f"   ❌ Cart tool call failed: {e}")
            else:
                print(f"   ❌ No cart specialist found")
            
            # Test frontline agent tool definitions
            print(f"\n🔧 Step 5: Test frontline agent tools")
            tools = getattr(frontline_agent, 'tools', [])
            print(f"   📝 Number of tools defined: {len(tools)}")
            
            for tool in tools[:3]:  # Show first 3 tools
                tool_name = tool.get('function', {}).get('name', 'unknown')
                print(f"   🔨 Tool: {tool_name}")
            
            # Test a simple frontline agent call
            print(f"\n🎯 Step 6: Test frontline agent directly")
            try:
                # Set up context
                frontline_agent.context = {
                    "call_sid": "debug_test_123",
                    "customer_name": None,
                    "cart_items": [],
                    "conversation_history": []
                }
                
                # Test with a simple input
                response = await frontline_agent.process("What do you have?", {})
                print(f"   📝 Response: {response.get('text', '')[:100]}...")
                print(f"   📝 Actions: {response.get('actions', [])}")
                
            except Exception as e:
                print(f"   ❌ Frontline agent test failed: {e}")
                import traceback
                traceback.print_exc()
        
        finally:
            break  # Only process first db session
    
    print(f"\n🎉 AGENT DEBUG COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_agent_debug())