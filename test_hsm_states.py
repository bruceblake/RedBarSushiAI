#!/usr/bin/env python3
"""
Test HSM state transitions across all conversation states.
"""

import asyncio
import httpx
import time

async def test_hsm_states():
    """Test all HSM state transitions."""
    
    call_sid = f"hsm_test_{int(time.time())}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🔄 HSM STATE TRANSITION TESTING")
        print("=" * 50)
        
        # State 1: INITIAL/GREETING
        print("\n🚀 STATE 1: INITIAL/GREETING")
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            message = result1.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if any(word in message.lower() for word in ["name", "hi", "hello"]):
                print(f"   ✅ PASS: System is in GREETING state")
            else:
                print(f"   ❌ FAIL: Not in proper GREETING state")
        
        # State 2: NAME CAPTURE → MAIN_MENU
        print("\n👤 STATE 2: NAME CAPTURE → MAIN_MENU")
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is Alex", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            message = result2.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if "alex" in message.lower() and any(word in message.lower() for word in ["order", "would you like"]):
                print(f"   ✅ PASS: Transitioned to MAIN_MENU state")
            else:
                print(f"   ❌ FAIL: Did not transition properly")
        
        # State 3: ORDERING
        print("\n🛒 STATE 3: ORDERING")
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a cheeseburger", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            message = result3.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if "added" in message.lower() and "cheeseburger" in message.lower():
                print(f"   ✅ PASS: Successfully processed order in ORDERING state")
            else:
                print(f"   ❌ FAIL: Order not processed correctly")
        
        # State 4: ORDER COMPLETION → VALIDATION
        print("\n✅ STATE 4: ORDER COMPLETION → VALIDATION")
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "That's all", "call_sid": call_sid}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            message = result4.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if any(word in message.lower() for word in ["total", "correct", "confirm", "order"]):
                print(f"   ✅ PASS: Transitioned to VALIDATION state")
            else:
                print(f"   ⚠️ UNCLEAR: May not have transitioned to validation")
        
        # State 5: CONFIRMATION
        print("\n🎯 STATE 5: CONFIRMATION")
        response5 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Yes, that's correct", "call_sid": call_sid}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            message = result5.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if any(word in message.lower() for word in ["thank", "order", "ready", "minutes"]):
                print(f"   ✅ PASS: Order confirmed and completed")
            else:
                print(f"   ⚠️ UNCLEAR: Order may not be fully confirmed")
        
        # State 6: INTERRUPTION HANDLING
        print("\n🔄 STATE 6: INTERRUPTION HANDLING")
        response6 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Actually, can I change my order?", "call_sid": call_sid}
        )
        
        if response6.status_code == 200:
            result6 = response6.json()
            message = result6.get('message', '')
            print(f"   📝 Response: {message[:80]}...")
            
            if any(word in message.lower() for word in ["change", "modify", "what would you like", "help"]):
                print(f"   ✅ PASS: Interruption handled gracefully")
            else:
                print(f"   ⚠️ UNCLEAR: Interruption handling unclear")
        
        print(f"\n🎉 HSM STATE TESTING COMPLETE")
        print(f"   All major state transitions tested")

if __name__ == "__main__":
    asyncio.run(test_hsm_states())