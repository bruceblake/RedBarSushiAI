"""
Test script to verify menu category filtering
"""
import json
import pprint

def main():
    # Create a sample menu data
    menu_data = {
        "items": [
            {
                "name": "Steak and Burgers",
                "reference_handler": "CAT1",
                "available": True,
                "is_category": True,
                "price": 8.0,
                "description": "Steak and Burger category",
                "snoozed": False
            },
            {
                "name": "Chicken",
                "reference_handler": "CAT2",
                "available": True,
                "is_category": True,
                "price": 6.5,
                "description": "Chicken category",
                "snoozed": False
            },
            {
                "name": "Chicken Burger",
                "reference_handler": "ITEM1",
                "available": True,
                "price": 8.0,
                "parentId": "CAT1",
                "description": "Crispy coated chicken thigh, lettuce, cheese",
                "snoozed": False
            },
            {
                "name": "Cheeseburger",
                "reference_handler": "ITEM2",
                "available": True,
                "price": 8.0,
                "parentId": "CAT1",
                "description": "Beef patty with cheese",
                "snoozed": False
            },
            {
                "name": "Chicken Tenders",
                "reference_handler": "ITEM3",
                "available": True,
                "price": 8.0,
                "parentId": "CAT2",
                "description": "Crispy chicken tenders",
                "snoozed": False
            }
        ]
    }
        
    # Count categories and items
    categories = [item for item in menu_data.get('items', []) if item.get('is_category', False)]
    regular_items = [item for item in menu_data.get('items', []) if not item.get('is_category', False)]
    
    print(f"Found {len(categories)} categories and {len(regular_items)} regular items")
    
    # Print category names
    print("\nCategories:")
    for cat in categories:
        print(f"- {cat['name']} (reference_handler: {cat.get('reference_handler', 'N/A')})")
    
    # Print some regular items
    print("\nSample regular items:")
    for item in regular_items[:5]:
        print(f"- {item['name']} (parentId: {item.get('parentId', 'N/A')})")
    
    # Group items by category
    print("\nItems by category:")
    category_map = {}
    for cat in categories:
        ref = cat.get('reference_handler', '')
        if ref:
            category_map[ref] = cat['name']
    
    items_by_category = {}
    for item in regular_items:
        parent_id = item.get('parentId', '')
        category_name = category_map.get(parent_id, 'Uncategorized')
        
        if category_name not in items_by_category:
            items_by_category[category_name] = []
        items_by_category[category_name].append(item['name'])
    
    for cat_name, items in items_by_category.items():
        print(f"\n{cat_name}:")
        for item in items[:3]:  # Just show first 3 items per category
            print(f"  - {item}")
        if len(items) > 3:
            print(f"  - ... ({len(items) - 3} more items)")

if __name__ == "__main__":
    main()