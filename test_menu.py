#\!/usr/bin/env python
"""
Simple script to test writing to the menu file
"""
import json
import os
from app.utils.menu_utils import write_menu_file

# Create a simple test menu
test_menu = {
    "items": [
        {
            "name": "Veggie Burger",
            "available": True,
            "reference_handler": "VEG-001",
            "price": 9.99
        },
        {
            "name": "Chicken Burger",
            "available": True,
            "reference_handler": "CHKN-001",
            "price": 10.99
        },
        {
            "name": "Cheeseburger",
            "available": True,
            "reference_handler": "CHEESE-001",
            "price": 8.99
        }
    ],
    "modifiers": [],
    "modifierGroups": [],
    "name_variants": {
        "veggie": "Veggie Burger",
        "veggie burger": "Veggie Burger",
        "chicken": "Chicken Burger",
        "chicken burger": "Chicken Burger",
        "cheeseburger": "Cheeseburger",
        "cheese": "Cheeseburger",
        "cheese burger": "Cheeseburger"
    }
}

# Try to write the menu file
print("Writing test menu...")
success = write_menu_file(test_menu)
print(f"Menu write success: {success}")

# Check if menu file exists
menu_path = os.path.join(os.getcwd(), 'menu_data.json')
if os.path.exists(menu_path):
    print(f"Menu file exists at: {menu_path}")
    # Check if content matches
    with open(menu_path, 'r') as f:
        menu_data = json.load(f)
        print(f"Menu has {len(menu_data.get('items', []))} items")
        for item in menu_data.get('items', []):
            print(f"- {item.get('name')}")
else:
    print(f"Menu file not found at: {menu_path}")
