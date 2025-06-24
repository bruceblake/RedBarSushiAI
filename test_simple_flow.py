"""
Simple test to verify the AI voice flow is working correctly
"""
import asyncio
import time
from app.utils.agent_orchestration_async import async_agent_orchestrator

async def test_simple_flow():
    """Test a simple conversation flow"""
    print("Testing RedBarSushiAI Voice Flow...")
    
    # Initialize
    await async_agent_orchestrator.initialize()
    
    call_sid = f"SIMPLE_TEST_{int(time.time())}"
    
    # Test 1: Greeting
    print("\n1. Testing greeting...")
    start = time.time()
    response = await async_agent_orchestrator.process_voice_input(
        call_sid, "", {"first_interaction": True}
    )
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Response: {response['text']}")
    print(f"   AI Generated: {response.get('ai_generated', False)}")
    
    # Test 2: Name
    print("\n2. Testing name recognition...")
    start = time.time()
    response = await async_agent_orchestrator.process_voice_input(
        call_sid, "My name is Jennifer"
    )
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Response: {response['text']}")
    print(f"   AI Generated: {response.get('ai_generated', False)}")
    print(f"   Actions: {response.get('actions', [])}")
    
    # Test 3: Order
    print("\n3. Testing order start...")
    start = time.time()
    response = await async_agent_orchestrator.process_voice_input(
        call_sid, "I'd like to place an order"
    )
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Response: {response['text']}")
    print(f"   Agent: {response.get('agent')}")
    
    # Test 4: Add item
    print("\n4. Testing add item...")
    start = time.time()
    response = await async_agent_orchestrator.process_voice_input(
        call_sid, "I want two california rolls"
    )
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Response: {response['text']}")
    print(f"   Agent: {response.get('agent')}")
    
    # Verify no fallback patterns
    assert not response['text'].startswith("[Cart] Processed:")
    assert response.get('ai_generated') or response.get('from_cache')
    
    print("\n✅ All tests passed! System is using AI correctly.")

if __name__ == "__main__":
    asyncio.run(test_simple_flow())