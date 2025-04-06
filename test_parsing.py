#\!/usr/bin/env python
"""
Test menu parsing and order handling
"""
from app.utils.agent_utils import analyze_user_input
from app.utils.menu_utils import find_menu_item_by_name

# Test orders
test_orders = [
    "I'd like a veggie burger",
    "Can I get a chicken burger?",
    "I want a cheese burger and a coke",
    "Give me some chicken tenders",
    "I'll have a Hawaiian pizza",
    "Steak frites please"
]

# Test each order
for order_text in test_orders:
    print(f"\nAnalyzing order: '{order_text}'")
    
    # Use the agent to analyze the order
    analysis = analyze_user_input(order_text)
    
    # Check the intent
    print(f"Intent: {analysis.get('intent', 'unknown')}")
    
    # Check if menu items were found
    if 'menu_items' in analysis and analysis['menu_items']:
        print(f"Found {len(analysis['menu_items'])} menu items:")
        for item in analysis['menu_items']:
            print(f"- {item.get('name')}")
    else:
        print("No menu items found")
