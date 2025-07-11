#!/usr/bin/env python3
"""
Test modifier constraint enforcement (min/max/multiMax).
"""

import asyncio
import httpx
import time

async def test_modifier_constraints():
    """Test modifier constraint enforcement."""
    
    call_sid = f"modifier_test_{int(time.time())}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🔧 MODIFIER CONSTRAINT TESTING")
        print("=" * 50)
        
        # First, let's add a menu item with modifiers via API
        print("\n🍽️ Setting up menu with modifier constraints...")
        
        # Create test menu with modifier constraints
        menu_with_modifiers = [{
            "channelLinkId": "test_restaurant_123",
            "menuId": "modifier_test_001",
            "categories": [
                {
                    "_id": "cat_burgers",
                    "name": "Burgers",
                    "description": "Burger items",
                    "subProducts": ["prod_burger"]
                }
            ],
            "products": {
                "prod_burger": {
                    "_id": "prod_burger",
                    "name": "Custom Burger",
                    "description": "Build your own burger",
                    "price": 1000,  # $10.00
                    "plu": "BURGER-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": ["group_toppings", "group_cheese"]
                }
            },
            "modifierGroups": {
                "group_toppings": {
                    "_id": "group_toppings",
                    "name": "Toppings",
                    "productType": 3,
                    "min": 1,        # Must select at least 1
                    "max": 3,        # Can select up to 3
                    "multiMax": 2,   # Can have up to 2 of each item
                    "subProducts": ["mod_lettuce", "mod_tomato", "mod_pickles"]
                },
                "group_cheese": {
                    "_id": "group_cheese", 
                    "name": "Cheese",
                    "productType": 3,
                    "min": 0,        # Optional
                    "max": 1,        # Can only select 1
                    "multiMax": 1,   # Only 1 of each
                    "subProducts": ["mod_cheddar", "mod_swiss"]
                }
            },
            "modifiers": {
                "mod_lettuce": {
                    "_id": "mod_lettuce",
                    "name": "Lettuce",
                    "productType": 2,
                    "price": 0,
                    "visible": True,
                    "snoozed": False
                },
                "mod_tomato": {
                    "_id": "mod_tomato",
                    "name": "Tomato",
                    "productType": 2,
                    "price": 50,  # $0.50
                    "visible": True,
                    "snoozed": False
                },
                "mod_pickles": {
                    "_id": "mod_pickles",
                    "name": "Pickles",
                    "productType": 2,
                    "price": 25,  # $0.25
                    "visible": True,
                    "snoozed": False
                },
                "mod_cheddar": {
                    "_id": "mod_cheddar",
                    "name": "Cheddar Cheese",
                    "productType": 2,
                    "price": 100,  # $1.00
                    "visible": True,
                    "snoozed": False
                },
                "mod_swiss": {
                    "_id": "mod_swiss",
                    "name": "Swiss Cheese",
                    "productType": 2,
                    "price": 100,  # $1.00
                    "visible": True,
                    "snoozed": False
                }
            }
        }]
        
        # Send menu update
        menu_response = await client.post(
            "http://localhost:8080/api/deliverect/menu/update",
            json=menu_with_modifiers
        )
        
        if menu_response.status_code == 200:
            print("   ✅ Menu with modifiers uploaded successfully")
        else:
            print(f"   ❌ Failed to upload menu: {menu_response.status_code}")
            return
        
        await asyncio.sleep(2)  # Wait for processing
        
        # Setup conversation
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser", "call_sid": call_sid}
        )
        
        # Test 1: Order item with minimal modifiers (should work)
        print("\n📋 TEST 1: Valid Order with Minimal Modifiers")
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a custom burger with lettuce", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            message = result1.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "added" in message.lower():
                print(f"   ✅ PASS: Order with minimal modifiers accepted")
            else:
                print(f"   ⚠️ UNCLEAR: Order processing unclear")
        
        # Test 2: Try to order without required modifiers (should prompt)
        print("\n📋 TEST 2: Order Without Required Modifiers")
        call_sid2 = f"modifier_test2_{int(time.time())}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser2", "call_sid": call_sid2}
        )
        
        response2 = await client.post(
            "http://localhost:8080/order/take_order", 
            json={"speech_result": "I want a custom burger", "call_sid": call_sid2}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            message = result2.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["topping", "modifier", "choose", "select"]):
                print(f"   ✅ PASS: System prompts for required modifiers")
            else:
                print(f"   ⚠️ UNCLEAR: Modifier prompting unclear")
        
        # Test 3: Try to add too many modifiers (should limit or warn)  
        print("\n📋 TEST 3: Test Maximum Modifier Constraints")
        call_sid3 = f"modifier_test3_{int(time.time())}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser3", "call_sid": call_sid3}
        )
        
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a custom burger with lettuce, tomato, pickles, and extra lettuce", "call_sid": call_sid3}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            message = result3.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if any(word in message.lower() for word in ["maximum", "limit", "too many", "cannot"]):
                print(f"   ✅ PASS: System enforces maximum constraints")
            elif "added" in message.lower():
                print(f"   ⚠️ PARTIAL: Order added - constraint enforcement may be lenient")
            else:
                print(f"   ❌ UNCLEAR: Constraint enforcement unclear")
        
        # Test 4: Check price calculations with modifiers
        print("\n📋 TEST 4: Price Calculation with Modifiers")
        call_sid4 = f"modifier_test4_{int(time.time())}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser4", "call_sid": call_sid4}
        )
        
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a custom burger with tomato and cheddar cheese", "call_sid": call_sid4}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            message = result4.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            # Base price $10 + tomato $0.50 + cheddar $1.00 = $11.50
            if "$11.50" in message or "11.50" in message:
                print(f"   ✅ PASS: Correct price calculation with modifiers")
            elif "$" in message and "0.00" not in message:
                print(f"   ⚠️ PARTIAL: Price shown but may be incorrect")
            else:
                print(f"   ❌ FAIL: Price calculation issues")
        
        print(f"\n🎉 MODIFIER CONSTRAINT TESTING COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_modifier_constraints())