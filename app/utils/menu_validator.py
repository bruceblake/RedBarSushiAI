# app/utils/menu_validator.py
"""
Utility functions for validating and fixing menu data before it's saved.
This ensures consistent PLU and price handling throughout the application.
"""

import logging
import hashlib
from app.utils.helpers import get_common_prices, generate_consistent_reference_id

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
    
    # Load existing menu data for reference ID preservation if possible
    try:
        from app.utils.menu_utils import load_menu_data
        existing_menu = load_menu_data(force_refresh=True)
        existing_items = {item.get("name", "").lower(): item for item in existing_menu.get("items", [])}
    except Exception as e:
        logger.warning(f"Could not load existing menu for reference: {e}")
        existing_items = {}
    
    # Load common prices for fallback
    common_prices = get_common_prices()
    
    # Process items
    fixed_item_count = 0
    for item in menu_data.get("items", []):
        item_id = item.get("id")
        item_name = item.get("name", "unknown")
        item_name_lower = item_name.lower()
        
        # Fix missing item ID
        if not item_id:
            # Generate a consistent ID based on name
            new_item_id = f"ITEM-{hashlib.md5(item_name.encode()).hexdigest()[:8]}"
            logger.warning(f"Item '{item_name}' is missing ID, setting to: {new_item_id}")
            item["id"] = new_item_id
            fixed_item_count += 1
        
        # Fix reference handler if missing - prioritize preserving existing reference handlers
        if not item.get("reference_handler"):
            # Check if it exists in current menu
            if item_name_lower in existing_items and existing_items[item_name_lower].get("reference_handler"):
                # Preserve the existing reference handler
                item["reference_handler"] = existing_items[item_name_lower]["reference_handler"]
                logger.info(f"Preserved existing reference_handler for {item_name}")
            # Check common prices as a fallback
            elif any(key == item_name_lower or key in item_name_lower for key in common_prices.keys()):
                for key, price_info in common_prices.items():
                    if key == item_name_lower or key in item_name_lower:
                        item["reference_handler"] = price_info.get("reference_handler", f"FB-{item_name_lower[:8]}")
                        logger.info(f"Set reference_handler for {item_name} to common price entry: {item['reference_handler']}")
                        break
            # Last resort: generate a new reference handler
            else:
                item["reference_handler"] = generate_consistent_reference_id(item_name)
                logger.warning(f"Item {item_name} is missing reference_handler, setting to: {item['reference_handler']}")
            fixed_item_count += 1
            
        # Ensure price is valid - prioritize preserving existing prices
        if "price" not in item or item["price"] is None or (isinstance(item["price"], (int, float)) and item["price"] <= 0):
            # Check if it exists in current menu
            if item_name_lower in existing_items and existing_items[item_name_lower].get("price"):
                # Preserve the existing price
                item["price"] = existing_items[item_name_lower]["price"]
                logger.info(f"Preserved existing price for {item_name}: {item['price']}")
            # Check common prices as a fallback
            elif any(key == item_name_lower or key in item_name_lower for key in common_prices.keys()):
                for key, price_info in common_prices.items():
                    if key == item_name_lower or key in item_name_lower:
                        item["price"] = price_info.get("price", 7.5)
                        logger.info(f"Set price for {item_name} to common price: {item['price']}")
                        break
            else:
                logger.warning(f"Item {item_name} has missing or invalid price, setting default to 7.5")
                item["price"] = 7.5  # Default price
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
        
        # Get existing modifiers from current menu if possible
        existing_group_modifiers = {}
        try:
            for existing_group in existing_menu.get("modifierGroups", []):
                if existing_group.get("name", "").lower() == group_name.lower() or existing_group.get("id") == group_id:
                    existing_group_modifiers = {
                        mod.get("name", "").lower(): mod 
                        for mod in existing_group.get("modifiers", [])
                    }
                    break
        except Exception:
            pass
            
        # Process modifiers in this group
        for modifier in group.get("modifiers", []):
            mod_id = modifier.get("id")
            mod_name = modifier.get("name", "unknown")
            mod_name_lower = mod_name.lower()
            
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
                # Try to preserve existing handler from current menu
                if mod_name_lower in existing_group_modifiers and existing_group_modifiers[mod_name_lower].get("reference_handler"):
                    modifier["reference_handler"] = existing_group_modifiers[mod_name_lower]["reference_handler"]
                    logger.info(f"Preserved existing reference_handler for modifier {mod_name}")
                else:
                    plu = modifier.get("plu", f"PLU-{mod_id}")
                    logger.warning(f"Modifier {mod_name} is missing reference_handler, fixing to: {plu}")
                    modifier["reference_handler"] = plu
                fixed_modifier_count += 1
                
            # Ensure price is valid
            if "price" not in modifier or modifier["price"] is None:
                # Try to preserve existing price from current menu
                if mod_name_lower in existing_group_modifiers and existing_group_modifiers[mod_name_lower].get("price") is not None:
                    modifier["price"] = existing_group_modifiers[mod_name_lower]["price"]
                    logger.info(f"Preserved existing price for modifier {mod_name}: {modifier['price']}")
                else:
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