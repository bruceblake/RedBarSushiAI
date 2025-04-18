#!/usr/bin/env python3
import json
import requests
import sys

# Simple test script to verify list-based menu updates

# Define server URL
BASE_URL = "http://localhost:5000"

# Sample menu items in list format
MENU_ITEMS = [
    {
        "name": "California Roll",
        "price": 9.95,
        "description": "Crab, avocado and cucumber roll",
        "available": True,
    },
    {
        "name": "Spicy Tuna Roll",
        "price": 11.95,
        "description": "Spicy tuna roll with cucumber",
        "available": True,
    },
    {
        "name": "Edamame",
        "price": 5.95,
        "description": "Steamed soybeans with sea salt",
        "available": True,
    },
]


def main():
    """Test the menu update endpoint with a list of items"""
    print("Testing menu update with list format...")

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
            print("\nSUCCESS: Menu update accepted!")
        else:
            print("\nFAILED: Menu update rejected.")
            sys.exit(1)

    except Exception as e:
        print(f"Error sending request: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
