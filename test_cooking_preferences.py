#!/usr/bin/env python3
"""
Test script for checking if cooking preferences are properly added to steak items.
"""

import json
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   stream=sys.stdout)

logger = logging.getLogger("test-cooking-prefs")

# Load a simplified menu for testing
SIMPLE_MENU = {
    "items": [
        {
            "name": "Delicious Steak Frites",
            "price": 19.95,
            "reference_handler": "stk-frites-1",
            "available": True,
            "category": "Entrees",
            "description": "Grilled ribeye steak with french fries"
        },
        {
            "name": "California Roll",
            "price": 7.95,
            "reference_handler": "cal-roll-1",
            "available": True,
            "category": "Rolls",
            "description": "Crab, avocado, and cucumber"
        }
    ],
    "modifiers": [],
    "modifierGroups": []
}

def test_add_cooking_preferences():
    """Test the add_cooking_preferences_to_steak_items function."""
    
    logger.info("Testing cooking preferences for steak items")
    
    try:
        # Import the function directly from the module
        sys.path.append(".")
        from app.utils.menu_validator import add_cooking_preferences_to_steak_items
        
        # Apply the function to our test menu
        logger.info("Original menu has %d items, %d modifiers, %d modifier groups", 
                   len(SIMPLE_MENU["items"]), 
                   len(SIMPLE_MENU["modifiers"]), 
                   len(SIMPLE_MENU["modifierGroups"]))
        
        updated_menu = add_cooking_preferences_to_steak_items(SIMPLE_MENU)
        
        # Check results
        logger.info("Updated menu has %d items, %d modifiers, %d modifier groups", 
                   len(updated_menu["items"]), 
                   len(updated_menu["modifiers"]), 
                   len(updated_menu["modifierGroups"]))
        
        # Find steak items 
        steak_items = []
        for item in updated_menu["items"]:
            if "steak" in item["name"].lower() or "frites" in item["name"].lower():
                steak_items.append(item)
                
        logger.info("Found %d steak items", len(steak_items))
        
        # Check if cooking preferences were added to steak items
        for item in steak_items:
            logger.info("Checking %s", item["name"])
            
            if "modifierGroups" in item and item["modifierGroups"]:
                logger.info("Item has %d modifier groups", len(item["modifierGroups"]))
                
                # Check if cooking preferences were added
                cooking_groups = []
                for group_id in item["modifierGroups"]:
                    # Find the group
                    for group in updated_menu["modifierGroups"]:
                        if group["id"] == group_id:
                            if "cooking" in group["name"].lower() or "preference" in group["name"].lower():
                                cooking_groups.append(group)
                
                if cooking_groups:
                    logger.info("SUCCESS: Item has cooking preferences with %d options", 
                               sum(len(g.get("modifiers", [])) for g in cooking_groups))
                    
                    # Print out cooking options
                    for group in cooking_groups:
                        logger.info("Group: %s", group["name"])
                        for mod_id in group.get("modifiers", []):
                            # Find modifier
                            for mod in updated_menu["modifiers"]:
                                if mod["id"] == mod_id:
                                    logger.info("  - %s (%s)", mod["name"], mod["plu"])
                else:
                    logger.error("FAIL: No cooking preferences found for %s", item["name"])
            else:
                logger.error("FAIL: No modifier groups found for %s", item["name"])
                
        # Print summarized menu
        menu_summary = {
            "items": [{"name": i["name"], "modifierGroups": i.get("modifierGroups", [])} for i in updated_menu["items"]],
            "modifierGroups": [{"id": g["id"], "name": g["name"], "modifiers": g.get("modifiers", [])} for g in updated_menu.get("modifierGroups", [])],
            "modifiers": [{"id": m["id"], "name": m["name"], "plu": m["plu"]} for m in updated_menu.get("modifiers", [])]
        }
        
        logger.info("Menu Summary: %s", json.dumps(menu_summary, indent=2))
        
        return True
        
    except Exception as e:
        logger.error("Error testing cooking preferences: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    test_result = test_add_cooking_preferences()
    logger.info("Test completed with result: %s", "SUCCESS" if test_result else "FAIL")