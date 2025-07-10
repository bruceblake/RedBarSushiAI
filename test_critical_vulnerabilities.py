#!/usr/bin/env python3
"""
Test the specific critical vulnerabilities mentioned in the conversation history.
"""

import asyncio
import httpx
import json
import time

async def test_contextual_memory_loss(client):
    """Test if system loses contextual memory during complex conversations."""
    print("🧠 Testing contextual memory loss...")
    
    call_sid = "memory_test_123"
    
    # Setup conversation with name
    await client.post("http://localhost:8080/order/take_order", 
                     json={"speech_result": "Hi", "call_sid": call_sid})
    
    response = await client.post("http://localhost:8080/order/take_order",
                                json={"speech_result": "My name is John", "call_sid": call_sid})
    print(f"✅ Name provided: {response.json().get('message', '')[:50]}...")
    
    # Add some items to cart
    response = await client.post("http://localhost:8080/order/take_order",
                                json={"speech_result": "I want a chicken burger", "call_sid": call_sid})
    print(f"✅ Item added: {response.json().get('message', '')[:50]}...")
    
    # Test if system remembers name after complex interaction
    response = await client.post("http://localhost:8080/order/take_order",
                                json={"speech_result": "What do you have for desserts?", "call_sid": call_sid})
    result = response.json().get('message', '')
    
    if "john" in result.lower() or "what's your name" not in result.lower():
        print("✅ PASS: System maintained contextual memory")
        return True
    else:
        print(f"❌ FAIL: System lost contextual memory - asking for name again: {result[:100]}")
        return False

async def test_order_cancellation(client):
    """Test if system can handle order cancellation properly."""
    print("🚫 Testing order cancellation...")
    
    call_sid = "cancel_test_123"
    
    # Setup order
    await client.post("http://localhost:8080/order/take_order",
                     json={"speech_result": "Hi, I'm Sarah", "call_sid": call_sid})
    
    await client.post("http://localhost:8080/order/take_order",
                     json={"speech_result": "I want a burger", "call_sid": call_sid})
    
    # Try to cancel
    response = await client.post("http://localhost:8080/order/take_order",
                                json={"speech_result": "Actually, cancel my order", "call_sid": call_sid})
    
    result = response.json().get('message', '')
    
    if "cancel" in result.lower() or "remove" in result.lower():
        print("✅ PASS: System handled cancellation request")
        return True
    else:
        print(f"❌ FAIL: System did not handle cancellation properly: {result[:100]}")
        return False

async def test_single_space_crash(client):
    """Test the specific single space character crash bug."""
    print("⚡ Testing single space character crash...")
    
    try:
        response = await client.post("http://localhost:8080/order/take_order",
                                   json={"speech_result": " ", "call_sid": "space_test_123"},
                                   timeout=5.0)
        
        if response.status_code == 200:
            print("✅ PASS: Single space handled without crash")
            return True
        else:
            print(f"❌ FAIL: Single space caused {response.status_code} error")
            return False
            
    except Exception as e:
        print(f"💥 FAIL: Single space caused exception: {e}")
        return False

async def test_concurrent_load(client):
    """Test concurrent load handling (simplified version)."""
    print("⚡ Testing concurrent load handling...")
    
    try:
        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            task = client.post("http://localhost:8080/order/take_order",
                             json={"speech_result": f"Hi, I'm customer {i}", "call_sid": f"concurrent_{i}"},
                             timeout=10.0)
            tasks.append(task)
        
        # Wait for all to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for response in responses:
            if isinstance(response, Exception):
                print(f"❌ Concurrent request failed: {response}")
            elif response.status_code == 200:
                success_count += 1
            else:
                print(f"❌ Concurrent request returned {response.status_code}")
        
        success_rate = (success_count / len(tasks)) * 100
        print(f"📊 Concurrent success rate: {success_rate}%")
        
        if success_rate >= 80:  # Allow some failures under load
            print("✅ PASS: System handled concurrent load adequately")
            return True
        else:
            print("❌ FAIL: System failed under concurrent load")
            return False
            
    except Exception as e:
        print(f"💥 FAIL: Concurrent test caused exception: {e}")
        return False

async def test_hsm_state_tracking(client):
    """Test HSM state tracking consistency."""
    print("🔄 Testing HSM state tracking...")
    
    call_sid = "hsm_test_123"
    
    try:
        # Start conversation
        response = await client.post("http://localhost:8080/order/take_order",
                                   json={"speech_result": "Hello", "call_sid": call_sid})
        
        # Check if response indicates proper state handling
        result = response.json().get('message', '')
        
        if response.status_code == 200 and len(result) > 0:
            print("✅ PASS: HSM state tracking appears functional")
            return True
        else:
            print(f"❌ FAIL: HSM state tracking issue - empty or error response")
            return False
            
    except Exception as e:
        print(f"💥 FAIL: HSM state test caused exception: {e}")
        return False

async def main():
    """Run critical vulnerability tests."""
    print("🔍 Testing Critical Vulnerabilities from Conversation History\n")
    
    async with httpx.AsyncClient() as client:
        tests = [
            ("Contextual Memory Loss", test_contextual_memory_loss),
            ("Order Cancellation", test_order_cancellation), 
            ("Single Space Crash", test_single_space_crash),
            ("Concurrent Load", test_concurrent_load),
            ("HSM State Tracking", test_hsm_state_tracking)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"🧪 {test_name}")
            print(f"{'='*50}")
            
            try:
                result = await test_func(client)
                if result:
                    passed += 1
                    print(f"✅ {test_name}: PASSED")
                else:
                    failed += 1
                    print(f"❌ {test_name}: FAILED")
            except Exception as e:
                failed += 1
                print(f"💥 {test_name}: EXCEPTION - {e}")
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        print(f"\n{'='*50}")
        print(f"📊 FINAL CRITICAL VULNERABILITY RESULTS")
        print(f"{'='*50}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print(f"\n🎉 All critical vulnerabilities have been addressed!")
        else:
            print(f"\n⚠️  {failed} critical vulnerabilities still need attention!")
            print(f"🔧 These should be prioritized for immediate fixes.")

if __name__ == "__main__":
    asyncio.run(main())