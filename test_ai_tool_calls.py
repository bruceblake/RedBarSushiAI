#!/usr/bin/env python3
"""
Test AI tool calling specifically.
"""

import asyncio
import httpx
import time
import uuid

async def test_ai_tool_calls():
    """Test AI tool calling behavior."""
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("🤖 AI TOOL CALLING TEST")
        print("=" * 60)
        
        # Set up a simple menu for testing
        simple_menu = [{
            "channelLinkId": "test_restaurant_123",
            "menuId": "ai_test_001",
            "categories": [
                {
                    "_id": "cat_test",
                    "name": "Test Items",
                    "description": "Test menu items",
                    "subProducts": ["prod_burger", "prod_pizza"]
                }
            ],
            "products": {
                "prod_burger": {
                    "_id": "prod_burger",
                    "name": "Test Burger",
                    "description": "A test burger",
                    "price": 1000,  # $10.00
                    "plu": "TEST-BURGER-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                },
                "prod_pizza": {
                    "_id": "prod_pizza",
                    "name": "Test Pizza",
                    "description": "A test pizza",
                    "price": 1500,  # $15.00
                    "plu": "TEST-PIZZA-001",
                    "productType": 1,
                    "visible": True,
                    "snoozed": False,
                    "subProducts": []
                }
            },
            "modifierGroups": {},
            "modifiers": {}
        }]
        
        # Upload test menu
        await client.post(
            "http://localhost:8080/api/deliverect/menu/update",
            json=simple_menu
        )
        await asyncio.sleep(2)
        
        # Test 1: Menu categories request (should trigger tool calls)
        print("\n🍽️ TEST 1: Menu Categories Request")
        call_sid = f"ai_tool_test_{uuid.uuid4().hex[:8]}"
        
        # Setup session
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Alex", "call_sid": call_sid}
        )
        
        # Request categories (should use get_menu_categories tool)
        response1 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What categories do you have?", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            message = result1.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            # Check if specific menu items are mentioned (indicating successful tool call)
            if "test items" in message.lower():
                print("   ✅ PASS: Categories tool call successful")
            else:
                print("   ❌ FAIL: Categories tool call not working")
        
        # Test 2: Specific item lookup (should trigger lookup_menu_item tool)
        print("\n🍕 TEST 2: Specific Item Lookup")
        call_sid2 = f"ai_lookup_test_{uuid.uuid4().hex[:8]}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Ben", "call_sid": call_sid2}
        )
        
        response2 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Do you have pizza?", "call_sid": call_sid2}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            message = result2.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "test pizza" in message.lower() or "pizza" in message.lower():
                print("   ✅ PASS: Item lookup tool call successful")
            else:
                print("   ❌ FAIL: Item lookup tool call not working")
        
        # Test 3: Add to cart (should trigger add_to_cart tool)
        print("\n🛒 TEST 3: Add to Cart")
        call_sid3 = f"ai_cart_test_{uuid.uuid4().hex[:8]}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm Charlie", "call_sid": call_sid3}
        )
        
        response3 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "I want a test burger", "call_sid": call_sid3}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            message = result3.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "added" in message.lower() and ("burger" in message.lower() or "test burger" in message.lower()):
                print("   ✅ PASS: Add to cart tool call successful")
                
                # Check for price display
                if "$10" in message or "10.00" in message:
                    print("   ✅ BONUS: Price displayed correctly")
                else:
                    print("   ⚠️ PARTIAL: Price not displayed")
            else:
                print("   ❌ FAIL: Add to cart tool call not working")
        
        # Test 4: Cart summary (should trigger get_cart_summary tool)
        print("\n📦 TEST 4: Cart Summary")
        response4 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "What's in my cart?", "call_sid": call_sid3}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            message = result4.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            if "burger" in message.lower() or "cart" in message.lower():
                print("   ✅ PASS: Cart summary tool call successful")
            else:
                print("   ❌ FAIL: Cart summary tool call not working")
        
        # Test 5: Force tool usage with explicit instructions
        print("\n🎯 TEST 5: Explicit Tool Instructions")
        call_sid5 = f"ai_explicit_test_{uuid.uuid4().hex[:8]}"
        
        await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Hi, I'm David", "call_sid": call_sid5}
        )
        
        response5 = await client.post(
            "http://localhost:8080/order/take_order",
            json={"speech_result": "Show me ALL the items you have", "call_sid": call_sid5}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            message = result5.get('message', '')
            print(f"   📝 Response: {message[:100]}...")
            
            # Count how many test items are mentioned
            item_mentions = sum([
                "test burger" in message.lower(),
                "test pizza" in message.lower(),
                "test items" in message.lower()
            ])
            
            if item_mentions >= 2:
                print(f"   ✅ PASS: Comprehensive menu display ({item_mentions} items)")
            else:
                print(f"   ❌ FAIL: Incomplete menu display ({item_mentions} items)")
        
        print(f"\n🎉 AI TOOL CALLING TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_ai_tool_calls())