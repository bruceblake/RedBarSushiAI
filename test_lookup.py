#\!/usr/bin/env python
"""
Simple script to test looking up menu items by name
"""
from app.utils.menu_utils import find_menu_item_by_name, load_menu_data

# Load the menu
print("Loading menu data...")
menu_data = load_menu_data(force_refresh=True)
print(f"Menu has {len(menu_data.get('items', []))} items:")
for item in menu_data.get('items', []):
    print(f"- {item.get('name')} => {item.get('reference_handler')}")

print("\nName variants in menu:")
for variant, name in menu_data.get('name_variants', {}).items():
    print(f"- '{variant}' => '{name}'")

# Test different search terms
test_terms = [
    "Veggie Burger",
    "veggie burger", 
    "Veggie",
    "burger",
    "Chicken Burger",
    "chicken",
    "Cheeseburger",
    "cheese"
]

print("\nTesting item lookup:")
for term in test_terms:
    print(f"\nLooking up: '{term}'")
    item = find_menu_item_by_name(term)
    if item:
        print(f"FOUND: {item.get('name')} => {item.get('reference_handler')}")
    else:
        print(f"NOT FOUND: '{term}'")
