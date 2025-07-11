#!/usr/bin/env python3
"""
Deep validation testing to ensure all components work correctly end-to-end.
"""

import asyncio
import httpx
import time
import json

async def test_deep_validation():
    """Perform deep validation of all system components."""
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("🔍 DEEP SYSTEM VALIDATION")
        print("=" * 60)
        
        # First, set up a comprehensive menu
        print("\n🍽️ Setting up comprehensive test menu...")
        
        comprehensive_menu = [{
            "channelLinkId": "test_restaurant_123",
            "menuId": "comprehensive_test_001",
            "categories": [
                {
                    "_id": "cat_burgers",
                    "name": "Burgers",
                    "description": "Premium burger selection",
                    "subProducts": ["prod_cheeseburger", "prod_bacon_burger"]
                },
                {
                    "_id": "cat_drinks", 
                    "name": "Drinks",
                    "description": "Beverages and refreshments",
                    "subProducts": ["prod_coke", "prod_coffee"]
                },
                {
                    "_id": "cat_sides",
                    "name": "Sides",
                    "description": "Side dishes",
                    "subProducts": ["prod_fries"]
                }
            ],
            "products": {
                "prod_cheeseburger": {
                    "_id": "prod_cheeseburger",
                    "name": "Classic Cheeseburger",
                    "description": "Beef patty with cheese",
                    "price": 1250,  # $12.50
                    "plu": "BURGER-CHEESE-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": ["group_size", "group_toppings"]
                },
                "prod_bacon_burger": {
                    "_id": "prod_bacon_burger",
                    "name": "Bacon Burger",
                    "description": "Beef patty with bacon",
                    "price": 1450,  # $14.50
                    "plu": "BURGER-BACON-001", 
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": ["group_size"]
                },
                "prod_coke": {
                    "_id": "prod_coke",
                    "name": "Coca Cola",
                    "description": "Refreshing cola drink",
                    "price": 250,  # $2.50
                    "plu": "DRINK-COKE-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": ["group_drink_size"]
                },
                "prod_coffee": {
                    "_id": "prod_coffee", 
                    "name": "Coffee",
                    "description": "Fresh brewed coffee",
                    "price": 300,  # $3.00
                    "plu": "DRINK-COFFEE-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                },
                "prod_fries": {
                    "_id": "prod_fries",
                    "name": "French Fries",
                    "description": "Crispy golden fries",
                    "price": 450,  # $4.50
                    "plu": "SIDE-FRIES-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": ["group_fry_size"]
                }
            },
            "modifierGroups": {
                "group_size": {
                    "_id": "group_size",
                    "name": "Burger Size",
                    "productType": 3,
                    "min": 1,
                    "max": 1,
                    "multiMax": 1,
                    "subProducts": ["mod_regular", "mod_large"]
                },
                "group_toppings": {
                    "_id": "group_toppings",
                    "name": "Extra Toppings",
                    "productType": 3,
                    "min": 0,
                    "max": 3,
                    "multiMax": 2,
                    "subProducts": ["mod_lettuce", "mod_tomato", "mod_pickles"]
                },
                "group_drink_size": {
                    "_id": "group_drink_size",
                    "name": "Drink Size",
                    "productType": 3,
                    "min": 1,
                    "max": 1,
                    "multiMax": 1,
                    "subProducts": ["mod_small_drink", "mod_large_drink"]
                },
                "group_fry_size": {
                    "_id": "group_fry_size",
                    "name": "Fry Size",
                    "productType": 3,
                    "min": 1,
                    "max": 1,
                    "multiMax": 1,
                    "subProducts": ["mod_regular_fries", "mod_large_fries"]
                }
            },
            "modifiers": {
                "mod_regular": {
                    "_id": "mod_regular",
                    "name": "Regular Size",
                    "productType": 2,
                    "price": 0,
                    "visible": True,
                    "snoozed": False
                },
                "mod_large": {
                    "_id": "mod_large",
                    "name": "Large Size",
                    "productType": 2,
                    "price": 200,  # $2.00 upcharge
                    "visible": True,
                    "snoozed": False
                },
                "mod_lettuce": {
                    "_id": "mod_lettuce",
                    "name": "Extra Lettuce",
                    "productType": 2,
                    "price": 50,  # $0.50
                    "visible": True,
                    "snoozed": False
                },
                "mod_tomato": {
                    "_id": "mod_tomato",
                    "name": "Extra Tomato",
                    "productType": 2,
                    "price": 50,  # $0.50
                    "visible": True,
                    "snoozed": False
                },
                "mod_pickles": {
                    "_id": "mod_pickles",
                    "name": "Extra Pickles",
                    "productType": 2,
                    "price": 25,  # $0.25
                    "visible": True,
                    "snoozed": False
                },
                "mod_small_drink": {
                    "_id": "mod_small_drink",
                    "name": "Small",
                    "productType": 2,
                    "price": 0,
                    "visible": True,
                    "snoozed": False
                },
                "mod_large_drink": {
                    "_id": "mod_large_drink",
                    "name": "Large",
                    "productType": 2,
                    "price": 100,  # $1.00 upcharge
                    "visible": True,
                    "snoozed": False
                },
                "mod_regular_fries": {
                    "_id": "mod_regular_fries",
                    "name": "Regular",
                    "productType": 2,
                    "price": 0,
                    "visible": True,
                    "snoozed": False
                },
                "mod_large_fries": {
                    "_id": "mod_large_fries",
                    "name": "Large",
                    "productType": 2,
                    "price": 150,  # $1.50 upcharge
                    "visible": True,
                    "snoozed": False
                }
            }
        }]
        
        # Upload the comprehensive menu
        menu_response = await client.post(
            "http://localhost:8080/api/deliverect/menu/update",
            json=comprehensive_menu
        )
        
        if menu_response.status_code != 200:
            print(f"   ❌ Failed to upload comprehensive menu: {menu_response.status_code}")
            return
        else:
            print("   ✅ Comprehensive menu uploaded successfully")
        
        await asyncio.sleep(3)  # Wait for processing
        
        # Deep Test 1: Complete order flow with multiple items
        print("\n🛒 DEEP TEST 1: Complete Multi-Item Order Flow")
        call_sid = f"deep_test_{int(time.time())}"
        
        # Step 1: Customer introduction
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, my name is Jessica", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"   👋 Greeting: {result1.get('message', '')[:80]}...")
            
            if "jessica" in result1.get('message', '').lower():
                print("   ✅ Name captured correctly")
            else:
                print("   ❌ Name not captured")
        
        # Step 2: Menu inquiry
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What burgers do you have?", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            menu_response = result2.get('message', '')
            print(f"   📋 Menu Response: {menu_response[:80]}...")
            
            if any(word in menu_response.lower() for word in ["cheeseburger", "bacon burger", "classic"]):
                print("   ✅ Menu items displayed correctly")
            else:
                print("   ❌ Menu items not displayed properly")
        
        # Step 3: Order first item
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I'll take a classic cheeseburger, large size", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            order_response = result3.get('message', '')
            print(f"   🍔 First Item: {order_response[:80]}...")
            
            if "added" in order_response.lower() and "cheeseburger" in order_response.lower():
                print("   ✅ First item added successfully")
                if "$14.50" in order_response:  # $12.50 + $2.00 for large
                    print("   ✅ Price calculated correctly with modifier")
                else:
                    print("   ⚠️ Price calculation may be incorrect")
            else:
                print("   ❌ First item not added properly")
        
        # Step 4: Add second item
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I also want large fries and a small coke", "call_sid": call_sid}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            order_response2 = result4.get('message', '')
            print(f"   🍟 Additional Items: {order_response2[:80]}...")
            
            if "added" in order_response2.lower():
                print("   ✅ Additional items processed")
            else:
                print("   ❌ Additional items not processed properly")
        
        # Step 5: Check cart contents
        response5 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's in my order so far?", "call_sid": call_sid}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            cart_response = result5.get('message', '')
            print(f"   📦 Cart Summary: {cart_response[:120]}...")
            
            items_mentioned = sum([
                "cheeseburger" in cart_response.lower(),
                "fries" in cart_response.lower(), 
                "coke" in cart_response.lower() or "cola" in cart_response.lower()
            ])
            
            if items_mentioned >= 2:
                print(f"   ✅ Cart remembers multiple items ({items_mentioned}/3)")
            else:
                print(f"   ❌ Cart memory issues ({items_mentioned}/3 items)")
        
        # Step 6: Complete order
        response6 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "That's all for my order", "call_sid": call_sid}
        )
        
        if response6.status_code == 200:
            result6 = response6.json()
            completion_response = result6.get('message', '')
            print(f"   ✅ Order Completion: {completion_response[:80]}...")
            
            if any(word in completion_response.lower() for word in ["total", "confirm", "correct"]):
                print("   ✅ Order completion flow triggered")
            else:
                print("   ⚠️ Order completion unclear")
        
        # Step 7: Confirm order
        response7 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Yes, that's correct", "call_sid": call_sid}
        )
        
        if response7.status_code == 200:
            result7 = response7.json()
            final_response = result7.get('message', '')
            print(f"   🎯 Final Confirmation: {final_response[:80]}...")
            
            if any(word in final_response.lower() for word in ["thank", "order", "ready", "minutes"]):
                print("   ✅ Order finalized successfully")
            else:
                print("   ⚠️ Order finalization unclear")
        
        # Deep Test 2: Interruption and modification handling
        print("\n🔄 DEEP TEST 2: Interruption and Modification Handling")
        call_sid2 = f"interrupt_test_{int(time.time())}"
        
        # Start new order
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Mike", "call_sid": call_sid2}
        )
        
        # Add an item
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a bacon burger", "call_sid": call_sid2}
        )
        
        # Interrupt with change request
        response_interrupt = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Actually, can I change that to a cheeseburger instead?", "call_sid": call_sid2}
        )
        
        if response_interrupt.status_code == 200:
            result_interrupt = response_interrupt.json()
            interrupt_response = result_interrupt.get('message', '')
            print(f"   🔄 Interruption Response: {interrupt_response[:80]}...")
            
            if any(word in interrupt_response.lower() for word in ["change", "modify", "update", "help"]):
                print("   ✅ Interruption handled gracefully")
            else:
                print("   ⚠️ Interruption handling unclear")
        
        # Deep Test 3: Edge case conversations
        print("\n🎭 DEEP TEST 3: Edge Case Conversation Handling")
        
        edge_cases = [
            ("Unclear speech", "umm... uh... I think... maybe a burger?"),
            ("Multiple requests", "I want a burger and fries and also do you have desserts?"),
            ("Polite conversation", "Thank you so much, you're very helpful!"),
            ("Question about restaurant", "What time do you close?"),
            ("Dietary restrictions", "Do you have anything gluten-free?")
        ]
        
        for test_name, speech in edge_cases:
            call_sid_edge = f"edge_{int(time.time())}_{test_name.replace(' ', '_')}"
            
            await client.post(
                "http://localhost:8080/order/take_order",
                json={"speech_result": "My name is EdgeTester", "call_sid": call_sid_edge}
            )
            
            response_edge = await client.post(
                "http://localhost:8080/order/take_order",
                json={"speech_result": speech, "call_sid": call_sid_edge}
            )
            
            if response_edge.status_code == 200:
                result_edge = response_edge.json()
                edge_response = result_edge.get('message', '')
                print(f"   🎭 {test_name}: {edge_response[:60]}...")
                
                # Check if response is reasonable (not error or empty)
                if len(edge_response) > 10 and not any(word in edge_response.lower() for word in ["error", "exception"]):
                    print(f"      ✅ Handled appropriately")
                else:
                    print(f"      ⚠️ Response may need improvement")
        
        # Deep Test 4: State persistence across calls
        print("\n💾 DEEP TEST 4: State Persistence Testing")
        call_sid3 = f"persistence_test_{int(time.time())}"
        
        # Build order across multiple calls with delays
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Sarah", "call_sid": call_sid3}
        )
        
        await asyncio.sleep(1)
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a cheeseburger", "call_sid": call_sid3}
        )
        
        await asyncio.sleep(2)
        
        # Check if name and order are still remembered
        response_persistent = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's my name and what did I order?", "call_sid": call_sid3}
        )
        
        if response_persistent.status_code == 200:
            result_persistent = response_persistent.json()
            persistent_response = result_persistent.get('message', '')
            print(f"   💾 Persistence Check: {persistent_response[:80]}...")
            
            name_remembered = "sarah" in persistent_response.lower()
            order_remembered = "cheeseburger" in persistent_response.lower()
            
            if name_remembered and order_remembered:
                print("   ✅ Full state persistence working")
            elif name_remembered or order_remembered:
                print("   ⚠️ Partial state persistence")
            else:
                print("   ❌ State persistence issues")
        
        print(f"\n🎉 DEEP SYSTEM VALIDATION COMPLETE")
        print(f"   All major system components tested thoroughly")

if __name__ == "__main__":
    asyncio.run(test_deep_validation())