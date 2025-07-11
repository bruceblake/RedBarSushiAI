#!/usr/bin/env python3
"""
Test the order processing fix.
"""

import asyncio
import httpx
import time

async def test_order_fix():
    """Test if order processing is now working."""
    
    call_sid = f"order_fix_test_{int(time.time())}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧪 Testing Order Processing Fix")
        print("=" * 50)
        
        # Step 1: Provide name
        print("\n1. Providing name...")
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is Sarah", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"   ✅ Name response: {result1.get('message', '')[:80]}...")
        
        # Step 2: Order an item
        print("\n2. Ordering a cheeseburger...")
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a cheeseburger", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            message = result2.get('message', '')
            print(f"   📝 Order response: {message}")
            
            # Check if item was actually added
            if "added" in message.lower() and "cheeseburger" in message.lower():
                print(f"   ✅ SUCCESS: Cheeseburger was added to cart!")
                
                # Check for price
                if "$" in message and "0.00" not in message:
                    print(f"   ✅ SUCCESS: Price is displayed correctly!")
                else:
                    print(f"   ⚠️ WARNING: Price may not be displayed correctly")
                    
            else:
                print(f"   ❌ ISSUE: Cheeseburger was not added to cart")
                print(f"   🔍 Debug: Response suggests: {message[:100]}...")
        
        # Step 3: Check cart contents
        print("\n3. Checking cart contents...")
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's in my cart?", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            message = result3.get('message', '')
            print(f"   📝 Cart response: {message}")
            
            if "cheeseburger" in message.lower():
                print(f"   ✅ SUCCESS: Cart remembers the cheeseburger!")
            else:
                print(f"   ❌ ISSUE: Cart doesn't remember the order")

if __name__ == "__main__":
    asyncio.run(test_order_fix())