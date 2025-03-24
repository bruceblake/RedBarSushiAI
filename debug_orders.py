#!/usr/bin/env python
"""
Debug script for order pricing issues
"""

import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_order_process():
    """Debug the order prices"""
    try:
        # Get the menu data directly from file
        file_path = os.path.join(os.getcwd(), 'menu_data.json')
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
        
        # Setup for simulation
        items_to_test = [
            "Veggie Burger",
            "Cheeseburger",
            "French Fries"
        ]
        
        for item_name in items_to_test:
            print(f"\n===== Testing for {item_name} =====")
            
            # Find the item in menu data
            menu_item = None
            for item in menu_data.get("items", []):
                if item.get("name", "").lower() == item_name.lower():
                    menu_item = item
                    break
            
            if not menu_item:
                print(f"Item '{item_name}' not found in menu data")
                continue
                
            print(f"Menu item price: ${menu_item.get('price')}")
            
            # Create an order item with this menu item
            order_item = {
                "name": menu_item.get("name"),
                "reference_handler": menu_item.get("reference_handler", ""),
                "modifier": [],
                "quantity": 1,
                "price": menu_item.get("price")
            }
            
            print(f"Order item price: ${order_item.get('price')}")
            
            # Simulate the price calculation step
            base_price = order_item.get("price", 0.0) or 0.0
            print(f"Base price after 'or 0.0': ${base_price}")
            
            # Our fixed calculation
            price_value = order_item.get("price")
            if price_value is None:
                fixed_price = 0.0
            else:
                try:
                    fixed_price = float(price_value)
                except (ValueError, TypeError):
                    fixed_price = 0.0
                    
            print(f"Fixed price: ${fixed_price}")
            
            # Try different price values to see behavior
            test_values = [None, 0, 0.0, 7.5, "7.5", ""]
            print("\nTesting different price values:")
            for val in test_values:
                print(f"  Value: {val}, Type: {type(val)}")
                
                # Original calculation
                old_calc = val or 0.0
                print(f"    Old calculation: {old_calc}")
                
                # New calculation
                if val is None:
                    new_calc = 0.0
                else:
                    try:
                        new_calc = float(val) if val != "" else 0.0
                    except (ValueError, TypeError):
                        new_calc = 0.0
                print(f"    New calculation: {new_calc}")
                
    except Exception as e:
        logger.error(f"Error in debug: {str(e)}")

if __name__ == "__main__":
    debug_order_process()