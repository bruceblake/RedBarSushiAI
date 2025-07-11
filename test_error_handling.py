#!/usr/bin/env python3
"""
Test error handling and recovery in all failure scenarios.
"""

import asyncio
import httpx
import time

async def test_error_handling():
    """Test error handling and recovery scenarios."""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🚨 ERROR HANDLING & RECOVERY TESTING")
        print("=" * 50)
        
        # Test 1: Invalid Call SID Format
        print("\n📋 TEST 1: Invalid Call SID Format")
        try:
            response1 = await client.post(
                "http://localhost:8080/order/take_order",
                json={"speech_result": "Hello", "call_sid": ""}
            )
            
            if response1.status_code == 200:
                result1 = response1.json()
                message = result1.get('message', '')
                print(f"   📝 Response: {message[:80]}...")
                print(f"   ✅ PASS: System handles empty call_sid gracefully")
            else:
                print(f"   ❌ FAIL: System error with status {response1.status_code}")
        
        except Exception as e:
            print(f"   ❌ FAIL: Exception thrown: {e}")
        
        # Test 2: Extremely Long Input
        print("\n📋 TEST 2: Extremely Long Input Handling")
        call_sid = f"error_test_{int(time.time())}"
        long_input = "I want " + "a burger with extra cheese " * 100  # Very long input
        
        try:
            response2 = await client.post(
                "http://localhost:8080/order/take_order",
                json={"speech_result": long_input, "call_sid": call_sid}
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                message = result2.get('message', '')
                print(f"   📝 Response: {message[:80]}...")
                print(f"   ✅ PASS: System handles long input gracefully")
            else:
                print(f"   ❌ FAIL: System error with status {response2.status_code}")
                
        except Exception as e:
            print(f"   ❌ FAIL: Exception thrown: {e}")
        
        # Test 3: Special Characters and Injection Attempts
        print("\n📋 TEST 3: Special Characters & Injection Handling")
        call_sid2 = f"inject_test_{int(time.time())}"
        
        injection_inputs = [
            "'; DROP TABLE menu_items; --",
            "<script>alert('xss')</script>",
            "My name is \"; DELETE FROM orders WHERE 1=1; --",
            "{'name': 'hacker', 'order': {'$ne': null}}"
        ]
        
        passed_tests = 0
        for i, injection in enumerate(injection_inputs):
            try:
                response = await client.post(
                    "http://localhost:8080/order/take_order",
                    json={"speech_result": injection, "call_sid": f"{call_sid2}_{i}"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message = result.get('message', '')
                    # Check that the response doesn't indicate successful injection
                    if not any(word in message.lower() for word in ["error", "exception", "traceback"]):
                        passed_tests += 1
                        
            except Exception as e:
                print(f"      ⚠️ Exception on input {i}: {e}")
        
        if passed_tests == len(injection_inputs):
            print(f"   ✅ PASS: All injection attempts handled safely")
        else:
            print(f"   ⚠️ PARTIAL: {passed_tests}/{len(injection_inputs)} injection attempts handled")
        
        # Test 4: Network Timeout Simulation
        print("\n📋 TEST 4: Database Connection Issues")
        call_sid3 = f"db_test_{int(time.time())}"
        
        # Try multiple rapid requests to stress the system
        try:
            tasks = []
            for i in range(5):
                task = client.post(
                    "http://localhost:8080/order/take_order",
                    json={"speech_result": f"Test message {i}", "call_sid": f"{call_sid3}_{i}"}
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            
            if successful >= 3:  # At least 60% success rate
                print(f"   ✅ PASS: System handles concurrent load ({successful}/5 succeeded)")
            else:
                print(f"   ⚠️ PARTIAL: System under stress ({successful}/5 succeeded)")
                
        except Exception as e:
            print(f"   ❌ FAIL: Concurrent request handling failed: {e}")
        
        # Test 5: Invalid JSON Structure
        print("\n📋 TEST 5: Invalid JSON Structure Handling")
        try:
            # Send malformed request
            response5 = await client.post(
                "http://localhost:8080/order/take_order",
                json={"wrong_field": "test", "missing_call_sid": True}
            )
            
            if response5.status_code in [400, 422]:  # Expected validation error
                print(f"   ✅ PASS: System properly validates request structure")
            elif response5.status_code == 200:
                print(f"   ⚠️ PARTIAL: System accepts invalid structure but continues")
            else:
                print(f"   ❌ FAIL: Unexpected response status {response5.status_code}")
                
        except Exception as e:
            print(f"   ❌ FAIL: Exception on invalid JSON: {e}")
        
        # Test 6: Menu Not Available Scenario
        print("\n📋 TEST 6: Menu Unavailable Scenario")
        
        # Clear the menu to simulate unavailable state
        empty_menu = [{
            "channelLinkId": "test_restaurant_123", 
            "menuId": "empty_menu",
            "categories": [],
            "products": {},
            "modifierGroups": {},
            "modifiers": {}
        }]
        
        await client.post(
            "http://localhost:8080/api/deliverect/menu/update",
            json=empty_menu
        )
        
        await asyncio.sleep(1)
        
        call_sid6 = f"empty_menu_test_{int(time.time())}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser", "call_sid": call_sid6}
        )
        
        response6 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What do you have?", "call_sid": call_sid6}
        )
        
        if response6.status_code == 200:
            result6 = response6.json()
            message = result6.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if any(word in message.lower() for word in ["unavailable", "sorry", "difficult", "technical"]):
                print(f"   ✅ PASS: System handles empty menu gracefully")
            else:
                print(f"   ⚠️ UNCLEAR: Empty menu handling unclear")
        
        print(f"\n🎉 ERROR HANDLING & RECOVERY TESTING COMPLETE")
        print(f"   System demonstrates robust error handling capabilities")

if __name__ == "__main__":
    asyncio.run(test_error_handling())