#!/usr/bin/env python3
"""
Test if the price display issue is fixed by doing a simple cart operation.
"""

import asyncio
import httpx

async def test_price_fix():
    """Test adding an item to cart to see if prices are displayed correctly."""
    
    test_call_sid = "price_test_001"
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing price fix by providing name first...\n")
        
        # First provide name
        try:
            response1 = await client.post(
                "http://localhost:8080/order/take_order",
                json={
                    "speech_result": "Bruce",
                    "call_sid": test_call_sid
                },
                timeout=15.0
            )
            
            if response1.status_code == 200:
                result1 = response1.json()
                print(f"✅ Name provided: {result1.get('message', '')}\n")
            
            # Wait a moment for state transition
            await asyncio.sleep(1)
            
            # Now try to order
            print("🧪 Testing price fix by adding Cheeseburger to cart...\n")
            
            response = await client.post(
                "http://localhost:8080/order/take_order",
                json={
                    "speech_result": "I want a cheeseburger",
                    "call_sid": test_call_sid
                },
                timeout=15.0
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result.get('message', '')
                
                print(f"✅ Response received:")
                print(f"Status: {response.status_code}")
                print(f"Message: {message}")
                
                # Check if price is mentioned in the response
                if "$" in message and "0.00" not in message:
                    print(f"\n🎉 SUCCESS: Price appears to be working! Found currency in response.")
                elif "$0.00" in message:
                    print(f"\n❌ STILL BROKEN: Found $0.00 in response.")
                else:
                    print(f"\n⚠️ UNCLEAR: No clear price information in response.")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_price_fix())