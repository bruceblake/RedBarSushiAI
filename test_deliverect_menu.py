#!/usr/bin/env python3
"""
Test script for Deliverect menu webhook integration.

This script helps test the menu webhook endpoint and provides
a sample menu payload for testing.
"""

import asyncio
import httpx
import json
from datetime import datetime
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Sample Deliverect menu payload based on their API documentation
SAMPLE_DELIVERECT_MENU = {
    "menu": {
        "categories": [
            {
                "id": "cat_001",
                "name": "Appetizers",
                "description": "Start your meal with our delicious appetizers",
                "posId": "APP001"
            },
            {
                "id": "cat_002", 
                "name": "Sushi Rolls",
                "description": "Fresh sushi rolls made to order",
                "posId": "SUSHI001"
            },
            {
                "id": "cat_003",
                "name": "Beverages",
                "description": "Refreshing drinks",
                "posId": "BEV001"
            }
        ],
        "products": [
            # Appetizers
            {
                "id": "item_001",
                "name": "Edamame",
                "description": "Steamed soybeans with sea salt",
                "price": 600,  # $6.00 in cents
                "plu": "1001",
                "imageUrl": "https://example.com/edamame.jpg",
                "isAvailable": True,
                "category": "cat_001",
                "modifierGroups": []
            },
            {
                "id": "item_002",
                "name": "Miso Soup",
                "description": "Traditional Japanese soybean soup",
                "price": 500,  # $5.00
                "plu": "1002",
                "isAvailable": True,
                "category": "cat_001",
                "modifierGroups": []
            },
            # Sushi Rolls
            {
                "id": "item_003",
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
                        "plu": "MG001",
                        "modifiers": [
                            {
                                "id": "mod_001",
                                "name": "Regular (8 pieces)",
                                "price": 0,
                                "plu": "MOD001",
                                "isAvailable": True
                            },
                            {
                                "id": "mod_002",
                                "name": "Large (12 pieces)",
                                "price": 400,  # +$4.00
                                "plu": "MOD002",
                                "isAvailable": True
                            }
                        ]
                    },
                    {
                        "id": "mg_002",
                        "name": "Add-ons",
                        "min": 0,
                        "max": 3,
                        "plu": "MG002",
                        "modifiers": [
                            {
                                "id": "mod_003",
                                "name": "Extra Avocado",
                                "price": 200,  # +$2.00
                                "plu": "MOD003",
                                "isAvailable": True
                            },
                            {
                                "id": "mod_004",
                                "name": "Spicy Mayo",
                                "price": 100,  # +$1.00
                                "plu": "MOD004",
                                "isAvailable": True
                            },
                            {
                                "id": "mod_005",
                                "name": "Tempura Flakes",
                                "price": 150,  # +$1.50
                                "plu": "MOD005",
                                "isAvailable": True
                            }
                        ]
                    }
                ]
            },
            {
                "id": "item_004",
                "name": "Spicy Tuna Roll",
                "description": "Fresh tuna with spicy mayo",
                "price": 1400,  # $14.00
                "plu": "2002",
                "isAvailable": True,
                "category": "cat_002",
                "modifierGroups": [
                    {
                        "id": "mg_001",
                        "name": "Size",
                        "min": 1,
                        "max": 1,
                        "plu": "MG001",
                        "modifiers": [
                            {
                                "id": "mod_001",
                                "name": "Regular (8 pieces)",
                                "price": 0,
                                "plu": "MOD001",
                                "isAvailable": True
                            },
                            {
                                "id": "mod_002",
                                "name": "Large (12 pieces)",
                                "price": 400,
                                "plu": "MOD002",
                                "isAvailable": True
                            }
                        ]
                    }
                ]
            },
            # Beverages
            {
                "id": "item_005",
                "name": "Green Tea",
                "description": "Hot Japanese green tea",
                "price": 300,  # $3.00
                "plu": "3001",
                "isAvailable": True,
                "category": "cat_003",
                "modifierGroups": []
            },
            {
                "id": "item_006",
                "name": "Sake",
                "description": "Premium Japanese rice wine",
                "price": 800,  # $8.00
                "plu": "3002",
                "isAvailable": True,
                "category": "cat_003",
                "modifierGroups": [
                    {
                        "id": "mg_003",
                        "name": "Temperature",
                        "min": 1,
                        "max": 1,
                        "plu": "MG003",
                        "modifiers": [
                            {
                                "id": "mod_006",
                                "name": "Hot",
                                "price": 0,
                                "plu": "MOD006",
                                "isAvailable": True
                            },
                            {
                                "id": "mod_007",
                                "name": "Cold",
                                "price": 0,
                                "plu": "MOD007",
                                "isAvailable": True
                            }
                        ]
                    }
                ]
            }
        ]
    },
    "accountId": "test_account_001",
    "channelLinkId": "redbarsushi_test_channel",
    "menuId": "menu_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
    "locationId": "location_001"
}


async def test_menu_webhook(base_url: str = "http://localhost:8000"):
    """Test the Deliverect menu webhook endpoint."""
    
    async with httpx.AsyncClient() as client:
        try:
            # Test the webhook endpoint
            print(f"\n🚀 Testing Deliverect menu webhook at {base_url}/api/menu/webhook/deliverect/menu")
            print("-" * 80)
            
            response = await client.post(
                f"{base_url}/api/menu/webhook/deliverect/menu",
                json=SAMPLE_DELIVERECT_MENU,
                timeout=30.0
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📝 Response Body: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("\n✅ Menu webhook test successful!")
                
                # Now test retrieving the menu items
                print("\n🔍 Verifying menu items were stored...")
                items_response = await client.get(f"{base_url}/api/menu/items")
                
                if items_response.status_code == 200:
                    items = items_response.json()
                    print(f"📦 Found {len(items)} menu items in database")
                    for item in items[:3]:  # Show first 3 items
                        print(f"  - {item.get('name')} (PLU: {item.get('plu')})")
                        
                # Test categories
                categories_response = await client.get(f"{base_url}/api/menu/categories")
                if categories_response.status_code == 200:
                    categories = categories_response.json()
                    print(f"\n📂 Found {len(categories)} categories in database")
                    for category in categories:
                        print(f"  - {category.get('name')}")
                        
            else:
                print(f"\n❌ Menu webhook test failed: {response.text}")
                
        except Exception as e:
            print(f"\n❌ Error testing webhook: {str(e)}")


async def register_webhook(base_url: str = "http://localhost:8000", 
                          public_url: str = None):
    """Register the webhook URL with Deliverect."""
    
    if not public_url:
        print("\n⚠️  To register with Deliverect, you need a public URL.")
        print("   You can use ngrok to create a tunnel:")
        print("   1. Install ngrok: https://ngrok.com/download")
        print("   2. Run: ngrok http 8000")
        print("   3. Use the HTTPS URL provided by ngrok")
        return
        
    webhook_url = f"{public_url}/api/menu/webhook/deliverect/menu"
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"\n📝 Registering webhook URL: {webhook_url}")
            
            response = await client.post(
                f"{base_url}/api/menu/webhook/deliverect/register",
                json={
                    "webhook_url": webhook_url,
                    "channel_link_id": "redbarsushi_test_channel"
                }
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📝 Response Body: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("\n✅ Webhook registration successful!")
                print(f"   Webhook URL: {webhook_url}")
                print("\n📋 Next steps:")
                print("   1. Go to your Deliverect dashboard")
                print("   2. Navigate to Settings > Webhooks")
                print("   3. Add this webhook URL for menu update events")
                print(f"   4. Webhook URL: {webhook_url}")
            else:
                print(f"\n❌ Webhook registration failed: {response.text}")
                
        except Exception as e:
            print(f"\n❌ Error registering webhook: {str(e)}")


async def main():
    """Main test function."""
    
    print("🍣 Red Bar Sushi - Deliverect Menu Integration Test")
    print("=" * 80)
    
    # Check if Docker is running
    try:
        response = httpx.get("http://localhost:8000/health", timeout=2.0)
        print("✅ API server is running")
    except:
        print("❌ API server is not running. Please start it with: ./start_docker.sh")
        return
    
    # Test the webhook
    await test_menu_webhook()
    
    # Optionally register webhook
    print("\n" + "=" * 80)
    print("📌 To register the webhook with Deliverect:")
    print("   1. Make your local server publicly accessible (e.g., using ngrok)")
    print("   2. Run: python test_deliverect_menu.py --register --public-url https://your-ngrok-url.ngrok.io")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Deliverect menu integration")
    parser.add_argument("--register", action="store_true", help="Register webhook with Deliverect")
    parser.add_argument("--public-url", help="Public URL for webhook registration (e.g., from ngrok)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API")
    
    args = parser.parse_args()
    
    if args.register:
        asyncio.run(register_webhook(args.base_url, args.public_url))
    else:
        asyncio.run(main())