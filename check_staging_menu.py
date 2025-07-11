#!/usr/bin/env python3
"""
Check what's in the staging environment menu and fix matching issues.
"""

import asyncio
import httpx
import time
import uuid

async def check_staging_menu():
    """Check staging environment menu and test ordering."""
    
    # Use your staging environment URL
    base_url = "https://3b93-149-22-84-146.ngrok-free.app"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("🔍 STAGING ENVIRONMENT MENU CHECK")
        print("=" * 60)
        
        call_sid = f"staging_menu_check_{uuid.uuid4().hex[:8]}"
        
        # Step 1: Start conversation to get menu
        print("\n📞 Step 1: Starting conversation...")
        response1 = await client.post(
            f"{base_url}/order/take_order",
            json={"speech_result": "Hi, my name is MenuChecker", "call_sid": call_sid}
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"   ✅ Connected: {result1.get('message', '')[:50]}...")
        
        # Step 2: Ask for ALL menu items
        print("\n📋 Step 2: Getting complete menu...")
        response2 = await client.post(
            f"{base_url}/order/take_order",
            json={"speech_result": "Show me everything you have on the menu", "call_sid": call_sid}
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            menu_response = result2.get('message', '')
            print(f"   📝 Full menu response:")
            print(f"   {menu_response}")
            print()
        
        # Step 3: Ask for specific categories
        print("\n🍔 Step 3: Getting burger items...")
        response3 = await client.post(
            f"{base_url}/order/take_order",
            json={"speech_result": "What burgers do you have?", "call_sid": call_sid}
        )
        
        if response3.status_code == 200:
            result3 = response3.json()
            burger_response = result3.get('message', '')
            print(f"   📝 Burger response:")
            print(f"   {burger_response}")
            print()
        
        # Step 4: Ask for steak items specifically  
        print("\n🥩 Step 4: Getting steak items...")
        response4 = await client.post(
            f"{base_url}/order/take_order",
            json={"speech_result": "What steak dishes do you have?", "call_sid": call_sid}
        )
        
        if response4.status_code == 200:
            result4 = response4.json()
            steak_response = result4.get('message', '')
            print(f"   📝 Steak response:")
            print(f"   {steak_response}")
            print()
        
        # Step 5: Test ordering the exact item that was mentioned
        print("\n🧪 Step 5: Testing exact item ordering...")
        
        # If "Delicious Steak Frites" is what's actually available
        response5 = await client.post(
            f"{base_url}/order/take_order",
            json={"speech_result": "I want the Delicious Steak Frites", "call_sid": call_sid}
        )
        
        if response5.status_code == 200:
            result5 = response5.json()
            exact_order_response = result5.get('message', '')
            print(f"   📝 Exact item order response:")
            print(f"   {exact_order_response}")
            print()
        
        # Step 6: Test what happens with non-existent item
        print("\n❌ Step 6: Testing non-existent item...")
        response6 = await client.post(
            f"{base_url}/order/take_order", 
            json={"speech_result": "I want a unicorn burger", "call_sid": call_sid}
        )
        
        if response6.status_code == 200:
            result6 = response6.json()
            nonexistent_response = result6.get('message', '')
            print(f"   📝 Non-existent item response:")
            print(f"   {nonexistent_response}")
            print()
        
        print("🎉 STAGING MENU CHECK COMPLETE")

if __name__ == "__main__":
    asyncio.run(check_staging_menu())