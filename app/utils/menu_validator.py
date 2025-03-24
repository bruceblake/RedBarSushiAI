# app/utils/menu_validator.py
"""
Utility functions for validating and fixing menu data before it's saved.
This ensures consistent PLU and price handling throughout the application.
"""

import logging
import hashlib

logger = logging.getLogger(__name__)

def validate_and_fix_menu_data(menu_data):
    """
    Validates and fixes issues in menu data before it's saved.
    
    Args:
        menu_data: Dict containing menu data with items, modifiers, etc.
        
    Returns:
        dict: Fixed menu data
    """
    # Make sure we have the expected structure
    if not isinstance(menu_data, dict):
        logger.warning("Menu data is not a dictionary, creating empty structure")
        menu_data = {}
        
    # Ensure required keys exist
    if "items" not in menu_data:
        menu_data["items"] = []
    if "modifiers" not in menu_data:
        menu_data["modifiers"] = []
    if "modifierGroups" not in menu_data:
        menu_data["modifierGroups"] = []
    
    # Process items
    fixed_item_count = 0
    for item in menu_data.get("items", []):
        item_id = item.get("id")
        item_name = item.get("name", "unknown")
        
        # Fix missing item ID
        if not item_id:
            # Generate a consistent ID based on name
            new_item_id = f"ITEM-{hashlib.md5(item_name.encode()).hexdigest()[:8]}"
            logger.warning(f"Item '{item_name}' is missing ID, setting to: {new_item_id}")
            item["id"] = new_item_id
            fixed_item_count += 1
        
        # Fix reference handler if missing
        if not item.get("reference_handler"):
            plu = item.get("plu", f"PLU-{item_id}")
            logger.warning(f"Item {item_name} is missing reference_handler, fixing to: {plu}")
            item["reference_handler"] = plu
            fixed_item_count += 1
            
        # Ensure price is valid
        if "price" not in item or item["price"] is None:
            logger.warning(f"Item {item_name} is missing price, setting default")
            item["price"] = 0.01
            fixed_item_count += 1
        elif isinstance(item["price"], (int, float)) and item["price"] <= 0:
            logger.warning(f"Item {item_name} has invalid price {item.get('price')}, fixing")
            item["price"] = 0.01
            fixed_item_count += 1
    
    # Process modifier groups
    fixed_modifier_group_count = 0
    fixed_modifier_count = 0
    seen_group_ids = set()
    
    for group in menu_data.get("modifierGroups", []):
        group_name = group.get("name", "unknown")
        group_id = group.get("id")
        
        # Fix missing group ID
        if not group_id:
            # Generate a consistent ID based on name
            new_group_id = f"MG-{hashlib.md5(group_name.encode()).hexdigest()[:8]}"
            logger.warning(f"Modifier group '{group_name}' is missing ID, setting to: {new_group_id}")
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1
            
        # Handle duplicate group IDs
        if group_id in seen_group_ids:
            # Add a suffix to make it unique
            new_group_id = f"{group_id}-{len(seen_group_ids)}"
            logger.warning(f"Duplicate modifier group ID {group_id}, changing to: {new_group_id}")
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1
            
        seen_group_ids.add(group_id)
        
        # Process modifiers in this group
        for modifier in group.get("modifiers", []):
            mod_id = modifier.get("id")
            mod_name = modifier.get("name", "unknown")
            
            # Fix missing modifier ID
            if not mod_id:
                # Generate a consistent ID based on name and group
                new_mod_id = f"MOD-{hashlib.md5((group_id + mod_name).encode()).hexdigest()[:8]}"
                logger.warning(f"Modifier '{mod_name}' in group '{group_name}' is missing ID, setting to: {new_mod_id}")
                modifier["id"] = new_mod_id
                mod_id = new_mod_id
                fixed_modifier_count += 1
            
            # Fix reference handler if missing
            if not modifier.get("reference_handler"):
                plu = modifier.get("plu", f"PLU-{mod_id}")
                logger.warning(f"Modifier {mod_name} is missing reference_handler, fixing to: {plu}")
                modifier["reference_handler"] = plu
                fixed_modifier_count += 1
                
            # Ensure price is valid
            if "price" not in modifier or modifier["price"] is None:
                logger.warning(f"Modifier {mod_name} is missing price, setting default")
                modifier["price"] = 0.0
                fixed_modifier_count += 1
            elif isinstance(modifier["price"], (int, float)) and modifier["price"] < 0:
                logger.warning(f"Modifier {mod_name} has negative price {modifier.get('price')}, fixing")
                modifier["price"] = 0.0
                fixed_modifier_count += 1
    
    if fixed_item_count > 0 or fixed_modifier_group_count > 0 or fixed_modifier_count > 0:
        logger.info(f"Fixed {fixed_item_count} items, {fixed_modifier_group_count} modifier groups, and {fixed_modifier_count} modifiers")
    
    return menu_data