#!/usr/bin/env python3
"""
Test order cancellation with proper state progression.
"""

import asyncio
import httpx
import json

async def test_proper_cancellation_flow():
    """Test cancellation after properly getting to ordering state."""
    print("🧪 Testing Order Cancellation with Proper State Flow\n")
    
    async with httpx.AsyncClient() as client:
        call_sid = "proper_cancellation_test"
        
        try:
            # 1. Start conversation - should go to GREETING
            print("1️⃣ Starting conversation...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "Hi", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   State: GREETING -> Response: {response.json().get('message', '')[:60]}...")
            
            # 2. Provide name - should go to MAIN_MENU
            print("2️⃣ Providing customer name...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "My name is Taylor", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   State: MAIN_MENU -> Response: {response.json().get('message', '')[:60]}...")
            
            # 3. Start ordering - should go to ORDERING state
            print("3️⃣ Starting to order...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "I want to order a chicken burger", "call_sid": call_sid},
                                       timeout=10.0)
            print(f"   State: ORDERING -> Response: {response.json().get('message', '')[:60]}...")
            
            # 4. NOW try to cancel while in ORDERING state
            print("4️⃣ Attempting to cancel order from ORDERING state...")
            response = await client.post("http://localhost:8080/order/take_order",
                                       json={"speech_result": "Actually, cancel my order", "call_sid": call_sid},
                                       timeout=10.0)
            
            result = response.json().get('message', '')
            print(f"   Response: {result[:100]}...")
            
            # 5. Analyze result
            if response.status_code == 200:
                # Check for cancellation keywords
                cancellation_keywords = ['cancel', 'confirm', 'sure', 'remove', 'delete', 'clear']
                if any(keyword in result.lower() for keyword in cancellation_keywords):
                    print("\n✅ SUCCESS: Order cancellation is working!")
                    print(f"   System properly handled cancellation from ORDERING state")
                    print(f"   Response indicates cancellation flow: {result[:150]}...")
                    return True
                elif "issue processing" in result.lower():
                    print("\n❌ FAIL: Still getting the generic error message")
                    print(f"   Response: {result}")
                    return False
                else:
                    print("\n🤔 UNEXPECTED: Got a different response")
                    print(f"   Response: {result}")
                    print(f"   This might still be an issue, but response is different from generic error")
                    return False
            else:
                print(f"\n❌ FAIL: HTTP error {response.status_code}")
                return False
                
        except Exception as e:
            print(f"\n💥 ERROR: Exception during test: {e}")
            return False

async def main():
    """Run the proper cancellation test."""
    success = await test_proper_cancellation_flow()
    
    if success:
        print("\n🎉 Order Cancellation Vulnerability FIXED!")
        print("   Users can now properly cancel their orders from the ORDERING state.")
    else:
        print("\n⚠️  Order cancellation still needs investigation.")
        print("   The issue might be more complex than initially thought.")

if __name__ == "__main__":
    asyncio.run(main())