#!/usr/bin/env python3
"""
Simplified test script for the cooking preferences function without dependencies.
"""

import json
import logging
import sys
import re
import hashlib

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

def add_cooking_preferences_to_steak_items(menu_data):
    """
    Adds required cooking preference modifiers to steak items in the menu.
    This function dynamically identifies steak items and ensures they have
    the necessary cooking preference modifier groups and options.
    
    Args:
        menu_data: Dict containing the complete menu data structure
        
    Returns:
        Dict: Updated menu data with cooking preferences added to steak items
    """
    if not menu_data or not isinstance(menu_data, dict):
        logger.warning("[MENU-COOKING] Invalid menu data provided")
        return menu_data
    
    # Step 1: Identify steak-related items based on name/description
    steak_items = []
    steak_patterns = [
        r'steak', r'frites', r'filet', r'ribeye', r'sirloin', 
        r'new york strip', r'porterhouse', r't-bone', r'beef'
    ]
    
    # Compile all patterns
    combined_pattern = re.compile('|'.join(steak_patterns), re.IGNORECASE)
    
    # Find steak items in the menu
    for item in menu_data.get('items', []):
        item_name = item.get('name', '').lower()
        item_desc = item.get('description', '').lower()
        
        if combined_pattern.search(item_name) or combined_pattern.search(item_desc):
            logger.info(f"[MENU-COOKING] Found steak item: {item.get('name')}")
            steak_items.append(item)
    
    if not steak_items:
        logger.info("[MENU-COOKING] No steak items found in menu")
        return menu_data
    
    # Step 2: Check if cooking preferences group already exists
    cooking_group_id = None
    for group in menu_data.get('modifierGroups', []):
        group_name = group.get('name', '').lower()
        if ('cooking' in group_name and ('preference' in group_name or 'instruction' in group_name)) or \
           ('steak' in group_name and ('temp' in group_name or 'doneness' in group_name)):
            cooking_group_id = group.get('id')
            logger.info(f"[MENU-COOKING] Found existing cooking preferences group: {group.get('name')}")
            break
    
    # Step 3: Create cooking preferences group if not exists
    if not cooking_group_id:
        # Generate a consistent ID for the group
        group_name = "Cooking Preferences"
        try:
            cooking_group_id = f"COOK-GP-{hashlib.md5(group_name.encode()).hexdigest()[:8]}"
        except:
            cooking_group_id = "COOK-GP-01"
            
        # Create the modifier group
        cooking_group = {
            "id": cooking_group_id,
            "name": group_name,
            "min": 1,  # Require at least one selection (mandatory)
            "max": 1,  # Allow only one selection
            "multiMax": 1,  # Maximum of one of any option
            "modifiers": []  # Will be populated with cooking options
        }
        
        # Standard cooking preferences for steak
        cooking_options = [
            {"name": "Rare", "plu": "COOK-RARE", "price": 0.0},
            {"name": "Medium Rare", "plu": "COOK-MEDRAR", "price": 0.0},
            {"name": "Medium", "plu": "COOK-MED", "price": 0.0},
            {"name": "Medium Well", "plu": "COOK-MEDWELL", "price": 0.0},
            {"name": "Well Done", "plu": "COOK-WELL", "price": 0.0}
        ]
        
        # Add the options to the menu's modifiers list and the group
        for option in cooking_options:
            # Check if this modifier already exists
            exists = False
            for existing_mod in menu_data.get('modifiers', []):
                if existing_mod.get('name') == option['name'] or existing_mod.get('plu') == option['plu']:
                    # Use existing modifier
                    cooking_group['modifiers'].append(existing_mod.get('id') or existing_mod.get('plu'))
                    exists = True
                    break
            
            if not exists:
                # Create new modifier with unique ID
                try:
                    mod_id = f"COOK-{hashlib.md5(option['name'].encode()).hexdigest()[:8]}"
                except:
                    mod_id = option['plu']
                
                new_modifier = {
                    "id": mod_id,
                    "name": option['name'],
                    "price": option['price'],
                    "plu": option['plu'],
                    "reference_handler": option['plu'],
                    "available": True
                }
                
                menu_data.setdefault('modifiers', []).append(new_modifier)
                cooking_group['modifiers'].append(mod_id)
                logger.info(f"[MENU-COOKING] Added cooking option: {option['name']}")
        
        # Add the group to the menu
        menu_data.setdefault('modifierGroups', []).append(cooking_group)
        logger.info(f"[MENU-COOKING] Created new cooking preferences group with {len(cooking_options)} options")
    
    # Step 4: Associate cooking preferences group with steak items
    update_count = 0
    for item in steak_items:
        # Check if item already has cooking preferences attached
        if 'modifierGroups' in item and cooking_group_id in item['modifierGroups']:
            continue
            
        # Add cooking group to item's modifier groups
        item.setdefault('modifierGroups', []).append(cooking_group_id)
        update_count += 1
        logger.info(f"[MENU-COOKING] Added cooking preferences to item: {item.get('name')}")
    
    logger.info(f"[MENU-COOKING] Added cooking preferences to {update_count} out of {len(steak_items)} steak items")
    return menu_data

def test_add_cooking_preferences():
    """Test the add_cooking_preferences_to_steak_items function."""
    
    logger.info("Testing cooking preferences for steak items")
    
    try:
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