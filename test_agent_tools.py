#!/usr/bin/env python3
"""
Test all AI agent tools to ensure they execute properly.
"""

import asyncio
import httpx
import time

async def test_agent_tools():
    """Test all major AI agent tools."""
    
    call_sid = f"tools_test_{int(time.time())}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🔧 AI AGENT TOOLS TESTING")
        print("=" * 50)
        
        # Setup: Get name first
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is David", "call_sid": call_sid}
        )
        
        # Test 1: Menu Lookup Tools
        print("\n📋 TEST 1: Menu Lookup Tools")
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What burgers do you have?", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            message = result1.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["burger", "cheeseburger", "chicken"]):
                print(f"   ✅ PASS: Menu lookup tools working")
            else:
                print(f"   ❌ FAIL: Menu lookup tools not working properly")
        
        # Test 2: Add to Cart Tools
        print("\n🛒 TEST 2: Add to Cart Tools")
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I'll take a cheeseburger", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            message = result2.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "added" in message.lower() and "cheeseburger" in message.lower():
                print(f"   ✅ PASS: Add to cart tools working")
            else:
                print(f"   ❌ FAIL: Add to cart tools not working")
        
        # Test 3: Cart Summary Tools
        print("\n📦 TEST 3: Cart Summary Tools")
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's in my order?", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            message = result3.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "cheeseburger" in message.lower():
                print(f"   ✅ PASS: Cart summary tools working")
            else:
                print(f"   ⚠️ PARTIAL: Cart summary may have issues")
        
        # Test 4: Menu Categories Tools
        print("\n📂 TEST 4: Menu Categories Tools")
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What categories do you have?", "call_sid": call_sid}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            message = result4.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["categories", "chicken", "pizza", "drinks"]):
                print(f"   ✅ PASS: Menu categories tools working")
            else:
                print(f"   ❌ FAIL: Menu categories tools not working")
        
        # Test 5: Proceed to Checkout Tools
        print("\n✅ TEST 5: Proceed to Checkout Tools")
        response5 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I'm done ordering", "call_sid": call_sid}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            message = result5.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["total", "correct", "confirm"]):
                print(f"   ✅ PASS: Proceed to checkout tools working")
            else:
                print(f"   ⚠️ PARTIAL: Checkout tools may need improvement")
        
        # Test 6: Order Validation Tools
        print("\n🔍 TEST 6: Order Validation Tools")
        response6 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Yes, place my order", "call_sid": call_sid}
        )
        
        if response6.status_code == 200:
            result6 = response6.json()
            message = result6.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["thank", "order", "ready", "minutes"]):
                print(f"   ✅ PASS: Order validation tools working")
            else:
                print(f"   ⚠️ PARTIAL: Order validation may need review")
        
        # Test 7: Customer Info Tools
        print("\n👤 TEST 7: Customer Info Tools")
        response7 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's my name again?", "call_sid": call_sid}
        )
        
        if response7.status_code == 200:
            result7 = response7.json()
            message = result7.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "david" in message.lower():
                print(f"   ✅ PASS: Customer info tools working")
            else:
                print(f"   ❌ FAIL: Customer info tools not retaining data")
        
        print(f"\n🎉 AI AGENT TOOLS TESTING COMPLETE")
        print(f"   Tested 7 major tool categories")

if __name__ == "__main__":
    asyncio.run(test_agent_tools())