#!/usr/bin/env python
"""
Debugging script to check how menu items are found and processed
"""

import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('menu_debug')

def debug_menu_item(item_name):
    """Debug a specific menu item's data"""
    try:
        # Load the menu data
        with open('menu_data.json', 'r') as f:
            menu_data = json.load(f)
            
        # Find the item by name
        exact_match = None
        fuzzy_matches = []
        
        logger.info(f"Searching for menu item: {item_name}")
        
        for item in menu_data.get('items', []):
            if item.get('name', '').lower() == item_name.lower():
                exact_match = item
                break
            elif item_name.lower() in item.get('name', '').lower():
                fuzzy_matches.append(item)
                
        # Print exact match if found
        if exact_match:
            logger.info("Exact match found:")
            logger.info(f"Name: {exact_match.get('name')}")
            logger.info(f"Price: {exact_match.get('price')}")
            logger.info(f"Reference Handler: {exact_match.get('reference_handler')}")
            logger.info(f"ID: {exact_match.get('id')}")
            logger.info(f"Available: {exact_match.get('available')}")
            
            # Debug how order processing would use this
            # Simulate the logic from app/routes/order.py
            order_item = {
                "name": exact_match.get("name"),
                "reference_handler": exact_match.get("reference_handler", ""),
                "modifier": [],
                "quantity": 1,
                "price": exact_match.get("price", 0.0)
            }
            
            logger.info("Simulated order item:")
            logger.info(f"Order Item Price: {order_item.get('price')}")
            
            # Simulate calculate_bill_amount logic
            base_price = order_item.get("price", 0.0) or 0.0
            quantity = order_item.get("quantity", 1)
            item_total = base_price * quantity
            
            logger.info(f"Order calculation - base_price: {base_price}")
            logger.info(f"Order calculation - after 'or 0.0': {base_price}")
            logger.info(f"Order calculation - quantity: {quantity}")
            logger.info(f"Order calculation - item_total: {item_total}")
            
        elif fuzzy_matches:
            logger.info(f"No exact match, but found {len(fuzzy_matches)} fuzzy matches:")
            for idx, item in enumerate(fuzzy_matches):
                logger.info(f"Fuzzy match {idx+1}:")
                logger.info(f"Name: {item.get('name')}")
                logger.info(f"Price: {item.get('price')}")
        else:
            logger.info("No matches found.")
            
    except Exception as e:
        logger.error(f"Error debugging menu item: {e}")
        
def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python debug_menu_items.py <item_name>")
        return
        
    item_name = sys.argv[1]
    debug_menu_item(item_name)
    
if __name__ == "__main__":
    main()