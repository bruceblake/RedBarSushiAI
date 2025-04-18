#!/usr/bin/env python3
# test_menu_loading.py
from app.utils.menu_utils import load_menu_data
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s: %(message)s")

# Test menu loading
print("Testing menu loading...")
menu_data = load_menu_data(force_refresh=True)

# Count available items
available_items = [
    item
    for item in menu_data.get("items", [])
    if item.get("name") and item.get("snoozed", False) is False
]

print(f"Menu data loaded with {len(menu_data.get('items', []))} total items")
print(f"Available items (not snoozed): {len(available_items)}")

# Print sample available items
print("\nSample available items:")
for item in available_items[:5]:
    print(f"- {item.get('name')} (Price: ${item.get('price', 0):.2f})")

# Check for issues
if not available_items:
    print("\nWARNING: No available items found. The menu would show as unavailable.")
else:
    print("\nCheck passed: Available items found in the menu.")
