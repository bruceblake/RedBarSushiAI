#!/usr/bin/env python3
"""
Test script for Deliverect integration with proper channel registration.

This script simulates the Deliverect channel registration flow and
helps test the menu webhook endpoint.
"""

import asyncio
import httpx
import json
from datetime import datetime
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_channel_registration(base_url: str = "http://localhost:8000"):
    """Test the Deliverect channel registration endpoint."""
    
    async with httpx.AsyncClient() as client:
        try:
            print("\n🚀 Testing Deliverect Channel Registration")
            print("=" * 80)
            
            # Simulate Deliverect calling our registration endpoint
            registration_payload = {
                "status": "register",
                "channelLocationId": "redbarsushi-loc-001",
                "channelLinkId": "redbarsushi-channel-001",
                "locationId": "deliverect-loc-001",
                "channelLinkName": "Red Bar Sushi AI"
            }
            
            print(f"\n📝 Sending registration request to {base_url}/api/deliverect/register")
            print(f"Payload: {json.dumps(registration_payload, indent=2)}")
            
            response = await client.post(
                f"{base_url}/api/deliverect/register",
                json=registration_payload,
                timeout=30.0
            )
            
            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📝 Response Body: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("\n✅ Channel registration successful!")
                webhook_urls = response.json()
                
                print("\n📋 Registered Webhook URLs:")
                for key, url in webhook_urls.items():
                    print(f"  - {key}: {url}")
                
                return webhook_urls
            else:
                print(f"\n❌ Channel registration failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"\n❌ Error testing registration: {str(e)}")
            return None


async def test_menu_update(base_url: str = "http://localhost:8000", menu_update_url: str = None):
    """Test the menu update webhook."""
    
    # Sample Deliverect menu payload
    menu_payload = {
        "menu": {
            "categories": [
                {
                    "id": "cat_001",
                    "name": "Appetizers",
                    "description": "Start your meal with our delicious appetizers"
                },
                {
                    "id": "cat_002", 
                    "name": "Sushi Rolls",
                    "description": "Fresh sushi rolls made to order"
                }
            ],
            "products": [
                {
                    "id": "item_001",
                    "name": "Edamame",
                    "description": "Steamed soybeans with sea salt",
                    "price": 600,  # $6.00 in cents
                    "plu": "1001",
                    "isAvailable": True,
                    "category": "cat_001",
                    "modifierGroups": []
                },
                {
                    "id": "item_002",
                    "name": "California Roll",
                    "description": "Crab, avocado, and cucumber",
                    "price": 1200,  # $12.00
                    "plu": "2001",
                    "isAvailable": True,
                    "category": "cat_002",
                    "modifierGroups": [
                        {
                            "id": "mg_001",
                            "name": "Size",
                            "min": 1,
                            "max": 1,
                            "modifiers": [
                                {
                                    "id": "mod_001",
                                    "name": "Regular (8 pieces)",
                                    "price": 0,
                                    "plu": "MOD001"
                                },
                                {
                                    "id": "mod_002",
                                    "name": "Large (12 pieces)",
                                    "price": 400,  # +$4.00
                                    "plu": "MOD002"
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "accountId": "test_account_001",
        "channelLinkId": "redbarsushi-channel-001",
        "menuId": "menu_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        "locationId": "deliverect-loc-001"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Use provided URL or default
            url = menu_update_url or f"{base_url}/api/deliverect/menu/update"
            
            print(f"\n🍱 Testing Menu Update Webhook")
            print("=" * 80)
            print(f"📍 Endpoint: {url}")
            
            response = await client.post(
                url,
                json=menu_payload,
                timeout=30.0
            )
            
            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📝 Response Body: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200 and response.json().get("status") == "ONLINE":
                print("\n✅ Menu update successful!")
                
                # Verify items were stored
                print("\n🔍 Verifying menu items...")
                items_response = await client.get(f"{base_url}/api/menu/items")
                
                if items_response.status_code == 200:
                    items = items_response.json()
                    print(f"📦 Found {len(items)} menu items in database")
                    
            else:
                print(f"\n❌ Menu update failed")
                
        except Exception as e:
            print(f"\n❌ Error testing menu update: {str(e)}")


async def simulate_deliverect_flow(base_url: str = "http://localhost:8000"):
    """Simulate the complete Deliverect integration flow."""
    
    print("🍣 Red Bar Sushi - Deliverect Integration Test")
    print("=" * 80)
    
    # Step 1: Test channel registration
    webhook_urls = await test_channel_registration(base_url)
    
    if webhook_urls:
        # Step 2: Test menu update using the registered URL
        menu_update_url = webhook_urls.get("menuUpdateURL")
        if menu_update_url:
            await asyncio.sleep(2)  # Small delay
            await test_menu_update(base_url, menu_update_url)
    
    print("\n" + "=" * 80)
    print("🎯 Integration Test Complete!")
    
    if webhook_urls:
        print("\n📌 Next Steps:")
        print("1. Configure these webhook URLs in your Deliverect dashboard:")
        for key, url in webhook_urls.items():
            print(f"   - {key}: {url}")
        print("\n2. If testing locally, use ngrok to expose your server:")
        print("   ngrok http 8000")
        print("   Then update PUBLIC_WEBHOOK_URL in your environment")
        print("\n3. Make changes in Deliverect to trigger webhook calls")


async def main():
    """Main entry point."""
    
    # Check if server is running
    try:
        response = httpx.get("http://localhost:8000/health", timeout=2.0)
        print("✅ API server is running")
    except:
        print("❌ API server is not running. Please start it with: ./start_docker.sh")
        return
    
    await simulate_deliverect_flow()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Deliverect integration")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--register-only", action="store_true", help="Only test registration")
    parser.add_argument("--menu-only", action="store_true", help="Only test menu update")
    
    args = parser.parse_args()
    
    if args.register_only:
        asyncio.run(test_channel_registration(args.base_url))
    elif args.menu_only:
        asyncio.run(test_menu_update(args.base_url))
    else:
        asyncio.run(main())