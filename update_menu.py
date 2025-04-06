#\!/usr/bin/env python
"""
Script to update the menu file with a comprehensive set of items for the restaurant
"""
import json
import os
from app.utils.menu_utils import write_menu_file, load_menu_data

# Create a proper menu with items
menu = {
    "items": [
        {
            "name": "Veggie Burger",
            "available": True,
            "reference_handler": "VEG-001",
            "price": 9.99,
            "category": "Burgers"
        },
        {
            "name": "Chicken Burger",
            "available": True,
            "reference_handler": "CHKN-001",
            "price": 10.99,
            "category": "Burgers"
        },
        {
            "name": "Cheeseburger",
            "available": True,
            "reference_handler": "CHEESE-001",
            "price": 8.99,
            "category": "Burgers"
        },
        {
            "name": "Delicious Steak Frites",
            "available": True,
            "reference_handler": "STK-01",
            "price": 14.99,
            "category": "Entrees"
        },
        {
            "name": "Hawaiian Pizza",
            "available": True,
            "reference_handler": "PIZZA-001",
            "price": 12.99,
            "category": "Pizzas"
        },
        {
            "name": "Chicken Tenders",
            "available": True,
            "reference_handler": "CHKN-TENDERS",
            "price": 9.99,
            "category": "Appetizers"
        },
        {
            "name": "Coca Cola",
            "available": True,
            "reference_handler": "DRINK-001",
            "price": 2.99,
            "category": "Drinks"
        },
        {
            "name": "Diet Coke",
            "available": True,
            "reference_handler": "DRINK-002",
            "price": 2.99,
            "category": "Drinks"
        }
    ],
    "modifiers": [],
    "modifierGroups": [],
    "name_variants": {
        "veggie": "Veggie Burger",
        "veggie burger": "Veggie Burger",
        "chicken burger": "Chicken Burger",
        "chicken": "Chicken Burger",
        "cheeseburger": "Cheeseburger",
        "cheese burger": "Cheeseburger",
        "cheese": "Cheeseburger",
        "steak": "Delicious Steak Frites",
        "steak frites": "Delicious Steak Frites",
        "frites": "Delicious Steak Frites",
        "hawaiian": "Hawaiian Pizza",
        "hawaiian pizza": "Hawaiian Pizza",
        "pizza": "Hawaiian Pizza",
        "tenders": "Chicken Tenders",
        "chicken tenders": "Chicken Tenders",
        "coca cola": "Coca Cola",
        "coke": "Coca Cola",
        "diet coke": "Diet Coke"
    }
}

# Force update the menu file in the root directory
root_menu_path = os.path.join(os.getcwd(), 'menu_data.json')
print(f"Writing menu to: {root_menu_path}")
success = write_menu_file(menu)

if success:
    print("Menu updated successfully\!")
    # Check if the file exists
    if os.path.exists(root_menu_path):
        print(f"Menu file confirmed at: {root_menu_path}")
    else:
        print(f"Warning: Menu file not found at: {root_menu_path}")
else:
    print("Failed to update menu")

# Load the menu to verify
loaded_menu = load_menu_data(force_refresh=True)
print(f"\nLoaded menu has {len(loaded_menu.get('items', []))} items:")
for item in loaded_menu.get('items', []):
    print(f"- {item.get('name')} => {item.get('reference_handler')}")
