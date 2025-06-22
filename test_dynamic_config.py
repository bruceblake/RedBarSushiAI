"""
Test that the system works with dynamic restaurant configuration
"""
import asyncio
import os
import time
from app.utils.agent_orchestration_async import async_agent_orchestrator

async def test_dynamic_config():
    """Test with different restaurant configurations"""
    print("Testing Dynamic Restaurant Configuration...")
    print("=" * 60)
    
    # Test 1: Default configuration
    print("\n1. Testing with default configuration:")
    print(f"   RESTAURANT_NAME: {os.environ.get('RESTAURANT_NAME', 'Restaurant')}")
    print(f"   RESTAURANT_GREETING_NAME: {os.environ.get('RESTAURANT_GREETING_NAME', 'assistant')}")
    
    # Initialize
    await async_agent_orchestrator.initialize()
    call_sid = f"TEST_DEFAULT_{int(time.time())}"
    
    # Test greeting
    response = await async_agent_orchestrator.process_voice_input(
        call_sid, "", {"first_interaction": True}
    )
    print(f"   Greeting: {response['text']}")
    assert "Restaurant" in response['text'] or os.environ.get('RESTAURANT_NAME', 'Restaurant') in response['text']
    
    # Test 2: Custom restaurant
    print("\n2. Testing with custom restaurant configuration:")
    os.environ['RESTAURANT_NAME'] = 'Pizza Palace'
    os.environ['RESTAURANT_TYPE'] = 'pizza'
    os.environ['RESTAURANT_GREETING_NAME'] = 'Mario'
    
    # Reload config
    from importlib import reload
    import app.config
    reload(app.config)
    
    # Re-initialize agents
    async_agent_orchestrator.frontline_agent = None
    await async_agent_orchestrator.initialize()
    
    call_sid2 = f"TEST_CUSTOM_{int(time.time())}"
    response = await async_agent_orchestrator.process_voice_input(
        call_sid2, "", {"first_interaction": True}
    )
    print(f"   Greeting: {response['text']}")
    
    # Should include custom restaurant name
    assert "Pizza Palace" in response['text'] or "Mario" in response['text'], f"Custom config not applied: {response['text']}"
    
    # Test 3: Name recognition still works
    print("\n3. Testing name recognition with custom config:")
    response = await async_agent_orchestrator.process_voice_input(
        call_sid2, "Hi, I'm Jennifer"
    )
    print(f"   Response: {response['text']}")
    assert "Jennifer" in response['text']
    
    # Test 4: Menu agent works generically
    print("\n4. Testing menu queries work generically:")
    response = await async_agent_orchestrator.process_voice_input(
        call_sid2, "What's on the menu?"
    )
    print(f"   Response: {response['text']}")
    # Should not have sushi-specific references
    assert "sushi" not in response['text'].lower() or os.environ.get('RESTAURANT_TYPE') == 'sushi'
    
    print("\n✅ All dynamic configuration tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_dynamic_config())