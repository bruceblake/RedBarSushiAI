"""
Simplified test script
"""
import json

# Create a sample menu data structure
sample_menu = {
    "items": [
        {
            "name": "Category 1",
            "reference_handler": "CAT1",
            "is_category": True,
            "price": 0.0
        },
        {
            "name": "Category 2",
            "reference_handler": "CAT2",
            "is_category": True,
            "price": 0.0
        },
        {
            "name": "Item 1",
            "reference_handler": "ITEM1",
            "parentId": "CAT1",
            "price": 9.99
        },
        {
            "name": "Item 2",
            "reference_handler": "ITEM2",
            "parentId": "CAT1",
            "price": 8.99
        },
        {
            "name": "Item 3",
            "reference_handler": "ITEM3",
            "parentId": "CAT2",
            "price": 7.99
        }
    ]
}

print("Testing category filtering:")

# Filter out category items
categories = [item for item in sample_menu["items"] if item.get("is_category", False)]
regular_items = [item for item in sample_menu["items"] if not item.get("is_category", False)]

print(f"Categories: {[c['name'] for c in categories]}")
print(f"Regular items: {[i['name'] for i in regular_items]}")

# Build category map
category_map = {}
for cat in categories:
    ref = cat.get("reference_handler", "")
    if ref:
        category_map[ref] = cat["name"]

print(f"Category map: {category_map}")

# Group items by category
items_by_category = {}
for item in regular_items:
    parent_id = item.get("parentId", "")
    category_name = category_map.get(parent_id, "Uncategorized")
    
    if category_name not in items_by_category:
        items_by_category[category_name] = []
    items_by_category[category_name].append(item["name"])

print(f"Items by category: {items_by_category}")

print("\nTest completed successfully!")