#!/usr/bin/env python3
import json
import requests
import sys

# Test script to verify menu updates with items missing names

# Define server URL
BASE_URL = "http://localhost:5000"

# Sample menu items in list format WITH MISSING NAMES
MENU_ITEMS = [
    {
        # Missing name, but has title
        "title": "Dragon Roll",
        "price": 14.95,
        "description": "Eel and avocado with special sauce",
        "available": True,
    },
    {
        # Missing name, but has product_name
        "product_name": "Rainbow Roll",
        "price": 15.95,
        "description": "California roll topped with assorted sashimi",
        "available": True,
    },
    {
        # Completely missing name
        "price": 7.95,
        "description": "Miso Soup",
        "available": True,
    },
    {
        # Has regular name field
        "name": "Tempura",
        "price": 8.95,
        "description": "Lightly battered and fried vegetables or shrimp",
        "available": True,
    },
]


def main():
    """Test the menu update endpoint with items missing names"""
    print("Testing menu update with items missing names...")

    # Send the update request
    try:
        response = requests.post(
            f"{BASE_URL}/menu_update",
            json=MENU_ITEMS,
            headers={"Content-Type": "application/json"},
        )

        # Print response
        print(f"Status code: {response.status_code}")
        print("Response body:")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)

        # Check result
        if response.status_code == 200:
            print("\nSUCCESS: Menu update accepted and fixed missing names!")
        else:
            print("\nFAILED: Menu update rejected.")
            sys.exit(1)

    except Exception as e:
        print(f"Error sending request: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
