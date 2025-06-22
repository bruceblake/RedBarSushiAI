"""
Minimal performance test for voice flow
"""
import asyncio
import time
import logging

# Set up minimal logging
logging.basicConfig(level=logging.WARNING)

# Import after logging setup
from app.utils.agent_orchestration_async import async_agent_orchestrator

async def test_response_time(call_sid: str, input_text: str, context=None):
    """Test single response time"""
    start = time.time()
    response = await async_agent_orchestrator.process_voice_input(call_sid, input_text, context)
    duration = time.time() - start
    return duration, response.get("text", "")

async def main():
    print("🚀 RedBarSushiAI Minimal Performance Test")
    print("=" * 50)
    
    # Initialize orchestrator
    await async_agent_orchestrator.initialize()
    print("✅ Orchestrator initialized")
    
    call_sid = f"PERF_TEST_{int(time.time())}"
    
    # Test 1: Initial greeting (should be fast)
    print("\n1. Initial greeting:")
    duration, text = await test_response_time(call_sid, "", {"first_interaction": True})
    print(f"   Time: {duration:.2f}s")
    print(f"   Response: {text[:60]}...")
    
    # Test 2: Name recognition
    print("\n2. Name recognition:")
    duration, text = await test_response_time(call_sid, "Bruce")
    print(f"   Time: {duration:.2f}s")
    print(f"   Response: {text[:60]}...")
    
    # Test 3: Start ordering
    print("\n3. Start ordering:")
    duration, text = await test_response_time(call_sid, "I want to order")
    print(f"   Time: {duration:.2f}s")
    print(f"   Response: {text[:60]}...")
    
    # Test 4: Add item
    print("\n4. Add item:")
    duration, text = await test_response_time(call_sid, "Two california rolls")
    print(f"   Time: {duration:.2f}s")
    print(f"   Response: {text[:60]}...")
    
    print("\n✅ Test complete")

if __name__ == "__main__":
    asyncio.run(main())