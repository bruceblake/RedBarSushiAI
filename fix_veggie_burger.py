#!/usr/bin/env python
"""
Quick fix script to ensure veggie burger and other items have correct prices
"""

import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_menu_prices(menu_file_path):
    """Fix the prices in the menu data file"""
    try:
        # Load the menu data
        with open(menu_file_path, 'r') as f:
            menu_data = json.load(f)
            
        # Define correct prices for common items
        correct_prices = {
            "veggie burger": 7.5,
            "cheeseburger": 8.5,
            "chicken burger": 8.0,
            "french fries": 2.0,
            "curly fries": 2.0,
            "seasoned fries": 2.5,
            "coca cola": 4.0,
            "diet coke": 4.0,
            "ginger beer": 4.0
        }
        
        # Track changes
        changes_made = 0
        
        # Update item prices
        for item in menu_data.get("items", []):
            item_name = item.get("name", "").lower()
            current_price = item.get("price")
            
            # Check if this item is in our list of correct prices
            for correct_name, correct_price in correct_prices.items():
                if correct_name in item_name:
                    if current_price != correct_price:
                        logger.info(f"Fixing price for {item.get('name')}: ${current_price} -> ${correct_price}")
                        item["price"] = correct_price
                        changes_made += 1
                    break
                    
            # Ensure all items have a valid price
            if not item.get("price") or item.get("price") <= 0:
                logger.warning(f"Item {item.get('name')} has invalid price: {item.get('price')}, setting to $5.0 default")
                item["price"] = 5.0
                changes_made += 1
        
        # Write the updated menu data back to the file
        if changes_made > 0:
            with open(menu_file_path, 'w') as f:
                json.dump(menu_data, f, indent=2)
            logger.info(f"Menu file updated with {changes_made} price corrections")
        else:
            logger.info("No price corrections needed - all prices are already correct")
            
        return True
    except Exception as e:
        logger.error(f"Error fixing menu prices: {e}")
        return False

if __name__ == "__main__":
    # Get the menu file path
    if len(sys.argv) > 1:
        menu_file = sys.argv[1]
    else:
        menu_file = "menu_data.json"
        
    # Get the absolute path
    if not os.path.isabs(menu_file):
        menu_file = os.path.join(os.getcwd(), menu_file)
        
    if not os.path.exists(menu_file):
        logger.error(f"Menu file not found: {menu_file}")
        sys.exit(1)
        
    logger.info(f"Fixing menu prices in {menu_file}")
    if fix_menu_prices(menu_file):
        logger.info("Price fix completed successfully!")
    else:
        logger.error("Failed to fix menu prices")
        sys.exit(1)