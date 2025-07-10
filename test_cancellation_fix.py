#!/usr/bin/env python3
"""
Test the order cancellation fix.
"""

import asyncio
import httpx
import json

async def test_order_cancellation_fix():
    """Test if order cancellation now works properly."""
    print("🧪 Testing Order Cancellation Fix\n")
    
    async with httpx.AsyncClient() as client:
        call_sid = "cancellation_fix_test"
        
        try:
            # 1. Setup conversation
            print("1️⃣ Setting up conversation...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "Hi", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   Response: {response.json().get('message', '')[:60]}...")
            
            # 2. Provide name
            print("2️⃣ Providing customer name...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "My name is Alex", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   Response: {response.json().get('message', '')[:60]}...")
            
            # 3. Add item to cart
            print("3️⃣ Adding item to cart...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "I want a chicken burger", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   Response: {response.json().get('message', '')[:60]}...")
            
            # 4. Try to cancel order
            print("4️⃣ Attempting to cancel order...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "Actually, cancel my order", "call_sid": call_sid},
                                       timeout=10.0)
            
            result = response.json().get('message', '')
            print(f"   Response: {result[:100]}...")
            
            # 5. Analyze result
            if response.status_code == 200:
                if any(keyword in result.lower() for keyword in ['cancel', 'confirm', 'sure', 'remove']):
                    print("\n✅ SUCCESS: Order cancellation is now working!")
                    print(f"   System properly handled cancellation request")
                    print(f"   Response indicates cancellation flow: {result[:150]}...")
                    return True
                elif "issue processing" in result.lower():
                    print("\n❌ FAIL: Still getting the old error message")
                    print(f"   Response: {result}")
                    return False
                else:
                    print("\n⚠️  PARTIAL: Different response, but not clear if cancellation is working")
                    print(f"   Response: {result}")
                    return False
            else:
                print(f"\n❌ FAIL: HTTP error {response.status_code}")
                return False
                
        except Exception as e:
            print(f"\n💥 ERROR: Exception during test: {e}")
            return False

async def main():
    """Run the cancellation fix test."""
    success = await test_order_cancellation_fix()
    
    if success:
        print("\n🎉 Order Cancellation Vulnerability FIXED!")
        print("   Users can now properly cancel their orders during the ordering process.")
    else:
        print("\n⚠️  Order cancellation still needs additional work.")
        print("   The fix may need further debugging or additional changes.")

if __name__ == "__main__":
    asyncio.run(main())