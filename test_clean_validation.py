#!/usr/bin/env python3
"""
Clean validation test with fresh sessions and proper isolation.
"""

import asyncio
import httpx
import time
import uuid

async def test_clean_validation():
    """Test with clean, isolated sessions."""
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("🧹 CLEAN VALIDATION TESTING")
        print("=" * 60)
        
        # First, set up a simple but complete menu
        print("\n🍽️ Setting up clean test menu...")
        
        clean_menu = [{
            "channelLinkId": "test_restaurant_123",
            "menuId": "clean_test_001",
            "categories": [
                {
                    "_id": "cat_burgers",
                    "name": "Burgers",
                    "description": "Burger selection",
                    "subProducts": ["prod_cheeseburger", "prod_chicken_burger"]
                },
                {
                    "_id": "cat_drinks",
                    "name": "Drinks", 
                    "description": "Beverages",
                    "subProducts": ["prod_soda"]
                }
            ],
            "products": {
                "prod_cheeseburger": {
                    "_id": "prod_cheeseburger",
                    "name": "Cheeseburger",
                    "description": "Classic cheeseburger",
                    "price": 1000,  # $10.00
                    "plu": "BURGER-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                },
                "prod_chicken_burger": {
                    "_id": "prod_chicken_burger",
                    "name": "Chicken Burger",
                    "description": "Grilled chicken burger",
                    "price": 1100,  # $11.00
                    "plu": "BURGER-002",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                },
                "prod_soda": {
                    "_id": "prod_soda",
                    "name": "Soda",
                    "description": "Soft drink",
                    "price": 200,  # $2.00
                    "plu": "DRINK-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                }
            },
            "modifierGroups": {},
            "modifiers": {}
        }]
        
        # Upload clean menu
        menu_response = await client.post(
            "http://localhost:8080/api/deliverect/menu/update",
            json=clean_menu
        )
        
        if menu_response.status_code != 200:
            print(f"   ❌ Failed to upload clean menu: {menu_response.status_code}")
            return
        else:
            print("   ✅ Clean menu uploaded successfully")
        
        await asyncio.sleep(3)  # Wait for processing
        
        # Test 1: Simple clean order flow
        print("\n🛒 TEST 1: Simple Clean Order Flow")
        
        # Use unique call_sid to avoid contamination
        call_sid = f"clean_{uuid.uuid4().hex[:8]}"
        
        # Step 1: Fresh greeting
        print(f"   📞 Using fresh call_sid: {call_sid}")
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hello, my name is Alice", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            greeting = result1.get('message', '')
            print(f"   👋 Greeting: {greeting[:60]}...")
            
            if "alice" in greeting.lower():
                print("   ✅ Name captured correctly")
            else:
                print("   ❌ Name not captured")
        
        # Step 2: Ask for menu
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What do you have?", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            menu_response = result2.get('message', '')
            print(f"   📋 Menu: {menu_response[:60]}...")
            
            # Check if AI actually calls menu tools
            if any(word in menu_response.lower() for word in ["cheeseburger", "chicken burger", "soda", "burgers", "drinks"]):
                print("   ✅ Menu items displayed")
            else:
                print("   ❌ Menu not displayed properly")
        
        # Step 3: Order an item
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I'll take a cheeseburger", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            order_response = result3.get('message', '')
            print(f"   🍔 Order: {order_response[:60]}...")
            
            if "added" in order_response.lower() and "cheeseburger" in order_response.lower():
                print("   ✅ Item added successfully")
                
                # Check for price
                if "$10" in order_response or "10.00" in order_response:
                    print("   ✅ Price displayed correctly")
                else:
                    print("   ⚠️ Price may not be displayed")
            else:
                print("   ❌ Item not added properly")
        
        # Test 2: Check cart persistence in same session
        print("\n📦 TEST 2: Cart Persistence in Same Session")
        
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's in my order?", "call_sid": call_sid}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            cart_response = result4.get('message', '')
            print(f"   📦 Cart: {cart_response[:60]}...")
            
            if "cheeseburger" in cart_response.lower():
                print("   ✅ Cart remembers items")
            else:
                print("   ❌ Cart memory issues")
        
        # Test 3: Complete the order
        print("\n✅ TEST 3: Order Completion")
        
        response5 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "That's all", "call_sid": call_sid}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            completion_response = result5.get('message', '')
            print(f"   ✅ Completion: {completion_response[:60]}...")
            
            if any(word in completion_response.lower() for word in ["total", "confirm", "correct", "order"]):
                print("   ✅ Order completion triggered")
            else:
                print("   ⚠️ Order completion unclear")
        
        # Test 4: Tool usage validation
        print("\n🔧 TEST 4: Tool Usage Validation")
        
        # Start completely fresh session for tool testing
        tool_call_sid = f"tools_{uuid.uuid4().hex[:8]}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Bob", "call_sid": tool_call_sid}
        )
        
        # Test menu lookup tools
        response_tools = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Show me your burger options", "call_sid": tool_call_sid}
        )
        
        if response_tools.status_code == 200:
            result_tools = response_tools.json()
            tools_response = result_tools.get('message', '')
            print(f"   🔧 Tools: {tools_response[:60]}...")
            
            # Check if specific menu items are mentioned (indicating tool usage)
            if "cheeseburger" in tools_response.lower() and "chicken burger" in tools_response.lower():
                print("   ✅ Menu lookup tools working")
            else:
                print("   ❌ Menu lookup tools not working properly")
        
        # Test 5: Session isolation
        print("\n🔒 TEST 5: Session Isolation")
        
        # Create another fresh session
        isolated_call_sid = f"isolated_{uuid.uuid4().hex[:8]}"
        
        response_isolated = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's my name?", "call_sid": isolated_call_sid}
        )
        
        if response_isolated.status_code == 200:
            result_isolated = response_isolated.json()
            isolated_response = result_isolated.get('message', '')
            print(f"   🔒 Isolation: {isolated_response[:60]}...")
            
            # Should not know names from other sessions
            if not any(name in isolated_response.lower() for name in ["alice", "bob"]):
                print("   ✅ Sessions properly isolated")
            else:
                print("   ❌ Session data bleeding between calls")
        
        print(f"\n🎉 CLEAN VALIDATION TESTING COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_clean_validation())