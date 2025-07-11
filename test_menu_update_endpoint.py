#!/usr/bin/env python3
"""
Test the menu update endpoint to ensure it works correctly.
"""

import asyncio
import httpx
import json
import time

async def test_menu_update_endpoint():
    """Test the menu update API endpoint."""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("🍽️ MENU UPDATE ENDPOINT TESTING")
        print("=" * 50)
        
        # Test 1: Check current menu first
        print("\n📋 TEST 1: Check Current Menu")
        call_sid = f"menu_test_{int(time.time())}"
        
        # Setup conversation and check current menu
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser", "call_sid": call_sid}
        )
        
        response = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What do you have?", "call_sid": call_sid}
        )
        
        if response.status_code == 200:
            result = response.json()
            current_menu = result.get('message', '')
            print(f"   📝 Current menu includes: {current_menu[:100]}...")
            print(f"   ✅ PASS: Can retrieve current menu")
        
        # Test 2: Send new menu via API endpoint
        print("\n🔄 TEST 2: Send New Menu Update")
        
        # Create a test menu update payload
        new_menu_data = [{
            "channelLinkId": "test_restaurant_123",
            "menuId": "menu_test_001",
            "categories": [
                {
                    "_id": "cat_001",
                    "name": "Test Category",
                    "description": "Test items for API testing",
                    "subProducts": ["prod_001", "prod_002"]
                }
            ],
            "products": {
                "prod_001": {
                    "_id": "prod_001",
                    "name": "API Test Burger",
                    "description": "A test burger added via API",
                    "price": 1200,  # $12.00
                    "plu": "API-TEST-001",
                    "posCategoryIds": ["cat_001"],
                    "productType": 1,  # Required: 1 = product
                    "visible": True,
                    "snoozed": False
                },
                "prod_002": {
                    "_id": "prod_002", 
                    "name": "API Test Pizza",
                    "description": "A test pizza added via API",
                    "price": 1500,  # $15.00
                    "plu": "API-TEST-002", 
                    "posCategoryIds": ["cat_001"],
                    "productType": 1,  # Required: 1 = product
                    "visible": True,
                    "snoozed": False
                }
            },
            "modifierGroups": {},
            "modifiers": {}
        }]
        
        try:
            menu_response = await client.post(
                "http://localhost:8080/api/deliverect/menu/update",
                json=new_menu_data
            )
            
            if menu_response.status_code == 200:
                menu_result = menu_response.json()
                print(f"   📝 Menu update response: {menu_result}")
                print(f"   ✅ PASS: Menu update endpoint accepts data")
            else:
                print(f"   ❌ FAIL: Menu update failed with status {menu_response.status_code}")
                print(f"   📝 Error: {menu_response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ FAIL: Menu update endpoint error: {e}")
            return
        
        # Test 3: Verify new menu is active
        print("\n🔍 TEST 3: Verify New Menu is Active")
        
        # Wait a moment for the update to process
        await asyncio.sleep(2)
        
        # Create new conversation to test updated menu
        new_call_sid = f"menu_test_verify_{int(time.time())}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "My name is TestUser2", "call_sid": new_call_sid}
        )
        
        verify_response = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What do you have?", "call_sid": new_call_sid}
        )
        
        if verify_response.status_code == 200:
            verify_result = verify_response.json()
            updated_menu = verify_result.get('message', '')
            print(f"   📝 Updated menu includes: {updated_menu[:100]}...")
            
            if "api test" in updated_menu.lower() or "test category" in updated_menu.lower():
                print(f"   ✅ PASS: New menu items are active!")
            else:
                print(f"   ⚠️ UNCLEAR: May not have updated completely")
        
        # Test 4: Order from new menu
        print("\n🛒 TEST 4: Order from New Menu")
        
        order_response = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want an API test burger", "call_sid": new_call_sid}
        )
        
        if order_response.status_code == 200:
            order_result = order_response.json()
            order_message = order_result.get('message', '')
            print(f"   📝 Order response: {order_message[:100]}...")
            
            if "api test burger" in order_message.lower() and "added" in order_message.lower():
                print(f"   ✅ PASS: Can order from updated menu!")
                
                # Check for correct price
                if "$12.00" in order_message:
                    print(f"   ✅ PASS: Prices updated correctly!")
                else:
                    print(f"   ⚠️ WARNING: Price may not be correct")
            else:
                print(f"   ❌ FAIL: Cannot order from updated menu")
        
        print(f"\n🎉 MENU UPDATE ENDPOINT TESTING COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_menu_update_endpoint())