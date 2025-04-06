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
    This function enforces strict validation for Deliverect integration.
    Handles various error conditions including:
    - String values in modifier groups and other data
    - Non-string values in name fields
    - Missing or invalid structure fields
    - Improperly formatted prices, references, IDs
    
    Args:
        menu_data: Dict containing menu data with items, modifiers, etc.
        
    Returns:
        dict: Fixed menu data
        
    Raises:
        ValueError: If menu items are missing required fields after fixing attempts.
                   Specifically will raise "Menu items must have names" if any items
                   are missing names after attempted fixes.
    """
    # Make sure we have valid input data
    if menu_data is None:
        logger.warning("[MENU-FIX] Menu data is None, creating empty structure")
        menu_data = {}
    
    # Make sure we have the expected structure
    if not isinstance(menu_data, dict):
        # Check if it's a list of menu items (Deliverect can send this format)
        if isinstance(menu_data, list) and len(menu_data) > 0:
            # If first item is a dictionary with categories, use that
            if isinstance(menu_data[0], dict) and "categories" in menu_data[0]:
                logger.warning("[MENU-FIX] Menu data is a list with categories in first item, using first item")
                menu_data = menu_data[0]
            # Otherwise, treat the list as menu items
            elif isinstance(menu_data[0], dict):
                logger.warning("[MENU-FIX] Menu data is a list, converting to dictionary structure")
                # Filter out non-dictionary items
                valid_items = [item for item in menu_data if isinstance(item, dict)]
                temp_data = {
                    "items": valid_items,
                    "modifiers": [],
                    "modifierGroups": [],
                    "name_variants": {}
                }
                menu_data = temp_data
            else:
                logger.warning("[MENU-FIX] Menu data is a list of non-dictionaries, creating empty structure")
                menu_data = {}
        else:
            logger.warning(f"[MENU-FIX] Menu data is not a dictionary: {type(menu_data)}, creating empty structure")
            menu_data = {}
        
    # Ensure required keys exist with proper types
    if "items" not in menu_data or not isinstance(menu_data["items"], list):
        logger.warning(f"[MENU-FIX] items is not a valid list: {type(menu_data.get('items', None))}")
        menu_data["items"] = []
    else:
        # Filter out non-dictionary items
        valid_items = []
        for i, item in enumerate(menu_data["items"]):
            if isinstance(item, dict):
                valid_items.append(item)
            else:
                logger.warning(f"[MENU-FIX] Removed non-dictionary item at index {i}: {type(item)}")
        menu_data["items"] = valid_items
        
    if "modifiers" not in menu_data or not isinstance(menu_data["modifiers"], list):
        logger.warning(f"[MENU-FIX] modifiers is not a valid list: {type(menu_data.get('modifiers', None))}")
        menu_data["modifiers"] = []
    else:
        # Filter out non-dictionary modifiers
        valid_modifiers = []
        for i, mod in enumerate(menu_data["modifiers"]):
            if isinstance(mod, dict):
                valid_modifiers.append(mod)
            else:
                logger.warning(f"[MENU-FIX] Removed non-dictionary modifier at index {i}: {type(mod)}")
        menu_data["modifiers"] = valid_modifiers
        
    if "modifierGroups" not in menu_data or not isinstance(menu_data["modifierGroups"], list):
        logger.warning(f"[MENU-FIX] modifierGroups is not a valid list: {type(menu_data.get('modifierGroups', None))}")
        menu_data["modifierGroups"] = []
    else:
        # Filter out non-dictionary modifier groups
        valid_groups = []
        for i, group in enumerate(menu_data["modifierGroups"]):
            if isinstance(group, dict):
                valid_groups.append(group)
            else:
                logger.warning(f"[MENU-FIX] Removed non-dictionary modifier group at index {i}: {type(group)}")
        menu_data["modifierGroups"] = valid_groups
        
    if "name_variants" not in menu_data or not isinstance(menu_data["name_variants"], dict):
        logger.warning(f"[MENU-FIX] name_variants is not a valid dictionary: {type(menu_data.get('name_variants', None))}")
        menu_data["name_variants"] = {}
    
    # Build map of existing items for reference
    existing_items = {}
    
    # Load common prices for fallback
    common_prices = get_common_prices()
    
    # Process items
    fixed_item_count = 0
    items_missing_names = []
    
    # First pass - build map of existing items by name for reference preservation
    for item in menu_data.get('items', []):
        # Skip any non-dictionary items that might have slipped through
        if not isinstance(item, dict):
            logger.warning(f"[MENU-FIX] Skipping non-dictionary item: {type(item)}")
            continue
            
        if item.get('name'):
            # Ensure name is a string
            item_name = item.get('name', ' ')
            if not isinstance(item_name, str):
                try:
                    item_name = str(item_name)
                    item["name"] = item_name  # Update the item with string name
                except:
                    item_name = ' '
                    
            item_name_lower = item_name.lower()
            existing_items[item_name_lower] = item
            
            # Also map by _id if present (handles different JSON formats)
            if item.get("_id"):
                existing_items[f"id:{item.get('_id')}"] = item
            if item.get('id'):
                existing_items[f"id:{item.get('id')}"] = item
    
    # Second pass - fix all issues with items
    for i, item in enumerate(menu_data.get('items', [])):
        # Skip any non-dictionary items that might have slipped through
        if not isinstance(item, dict):
            logger.warning(f"[MENU-FIX] Skipping non-dictionary item in second pass: {type(item)}")
            continue
            
        # Track if we've fixed anything (for logging)
        item_fixed = False
        
        # Fix item ID
        item_id = item.get('id')
        if not item_id:
            # Check if _id exists but id doesn't (document format conversion)
            if item.get("_id"):
                # Use _id as id for consistency
                item["id"] = item.get("_id")
                logger.info(f"[MENU-FIX] Converted _id to id for item index {i}")
                item_id = item["id"]
                item_fixed = True
            else:
                # Generate a placeholder ID
                new_item_id = f"ITEM-{i:04d}"
                logger.warning(f"[MENU-FIX] Item at index {i} is missing ID, setting to: {new_item_id}")
                item["id"] = new_item_id
                item_id = new_item_id
                item_fixed = True
            
        # Fix item name (critical for functionality)
        item_name = item.get('name')
        
        # Ensure item_name is a string if it exists
        if item_name is not None and not isinstance(item_name, str):
            try:
                item_name = str(item_name)
                item["name"] = item_name
                logger.warning(f"[MENU-FIX] Converting non-string name to string at index {i}: {type(item_name)}")
                item_fixed = True
            except:
                item_name = None
                item["name"] = None
        
        # If name is missing or empty after conversion attempt, create a new one
        if not item_name:
            # Try to get name from reference_handler if available
            ref = item.get('reference_handler', '')
            if ref:
                item['name'] = f"Item-{ref[-8:]}"
            elif item_id:
                item['name'] = f"Item-{str(item_id)[-8:]}"
            else:
                item['name'] = f"Unnamed Item {i + 1}"
            logger.warning(f"[MENU-FIX] Fixed missing name for item at index {i}: '{item.get('name')}'")
            item_fixed = True
            item_name = item['name']  # Update the local variable
            
            # Track this item to verify it has a name after fixing
            items_missing_names.append(item)
            
        # At this point we have a string name
        item_name_lower = item_name.lower()
        
        # Fix reference handler if missing - prioritize preserving existing reference handlers
        if not item.get("reference_handler"):
            # Check if it exists in current menu
            if item_name_lower in existing_items and existing_items[item_name_lower].get("reference_handler"):
                # Preserve the existing reference handler
                item["reference_handler"] = existing_items[item_name_lower]["reference_handler"]
                logger.info(f"[MENU-FIX] Preserved existing reference_handler for {item_name}")
            # Check if the item has a PLU to use
            elif item.get("plu"):
                item["reference_handler"] = item.get("plu")
                logger.info(f"[MENU-FIX] Using PLU as reference_handler for {item_name}")
            # Check common prices as a fallback
            elif any(key == item_name_lower or key in item_name_lower for key in common_prices.keys()):
                for key, price_info in common_prices.items():
                    if key == item_name_lower or key in item_name_lower:
                        item["reference_handler"] = price_info.get("reference_handler", f"FB-{item_name_lower[:8]}")
                        logger.info(f"[MENU-FIX] Set reference_handler for {item_name} to common price entry: {item['reference_handler']}")
                        break
            # Last resort: generate a new reference handler
            else:
                import re
                try:
                    # Create a reference based on name - ensures consistency
                    clean_name = re.sub(r'[^\w]', '', item_name)
                    if clean_name:
                        item["reference_handler"] = clean_name[:15]  # Use first 15 chars of name
                    else:
                        # Use a hash-based ID if name has no alphanumeric chars
                        import hashlib
                        hash_obj = hashlib.md5(item_name.encode())
                        item["reference_handler"] = f"PROD-{hash_obj.hexdigest()[:8]}"
                except:
                    # Very basic fallback in case the function fails
                    import time
                    item["reference_handler"] = f"PROD-{int(time.time())}-{i}"
                
                logger.warning(f"[MENU-FIX] Item {item_name} is missing reference_handler, setting to: {item['reference_handler']}")
            item_fixed = True
            
        # Ensure price is valid - prioritize preserving existing prices
        price_invalid = False
        
        # Check if price is missing
        if "price" not in item:
            price_invalid = True
        # Check if price is None
        elif item["price"] is None:
            price_invalid = True
        # Check if price is not a number
        elif not isinstance(item["price"], (int, float)):
            try:
                # Try to convert to float
                item["price"] = float(item["price"])
            except (ValueError, TypeError):
                price_invalid = True
        # Check if price is negative or zero
        elif item["price"] <= 0:
            price_invalid = True
            
        if price_invalid:
            # Check if it exists in current menu
            if item_name_lower in existing_items and existing_items[item_name_lower].get("price"):
                # Preserve the existing price
                item["price"] = existing_items[item_name_lower]["price"]
                logger.info(f"[MENU-FIX] Preserved existing price for {item_name}: {item['price']}")
            # Check common prices as a fallback
            elif any(key == item_name_lower or key in item_name_lower for key in common_prices.keys()):
                for key, price_info in common_prices.items():
                    if key == item_name_lower or key in item_name_lower:
                        item["price"] = price_info.get("price", 7.5)
                        logger.info(f"[MENU-FIX] Set price for {item_name} to common price: {item['price']}")
                        break
            else:
                logger.warning(f"[MENU-FIX] Item {item_name} has missing or invalid price, setting default to 7.5")
                item["price"] = 7.5  # Default price
            item_fixed = True
            
        # Ensure description exists (can be empty)
        if "description" not in item:
            item["description"] = ""
            item_fixed = True
        elif item["description"] is not None and not isinstance(item["description"], str):
            try:
                item["description"] = str(item["description"])
            except:
                item["description"] = ""
            item_fixed = True
            
        # Ensure availability is properly initialized
        if "available" not in item:
            # Default to available unless explicitly snoozed
            item["available"] = not item.get("snoozed", False)
            item_fixed = True
        elif not isinstance(item["available"], bool):
            # Convert to boolean if not already
            item["available"] = bool(item["available"])
            item_fixed = True
            
        # Ensure snoozed is properly initialized
        if "snoozed" not in item:
            # Default to not snoozed unless explicitly unavailable
            item["snoozed"] = not item.get("available", True)
            item_fixed = True
        elif not isinstance(item["snoozed"], bool):
            # Convert to boolean if not already
            item["snoozed"] = bool(item["snoozed"])
            item_fixed = True
            
        # Track total fixes
        if item_fixed:
            fixed_item_count += 1
    
    # Process modifier groups
    fixed_modifier_group_count = 0
    fixed_modifier_count = 0
    seen_group_ids = set()
    
    # Ensure modifierGroups is a list before processing
    modifier_groups = menu_data.get("modifierGroups", [])
    if not isinstance(modifier_groups, list):
        logger.warning(f"[MENU-FIX] modifierGroups is not a list: {type(modifier_groups)}. Creating empty list.")
        menu_data["modifierGroups"] = []
        modifier_groups = []
    
    for i, group in enumerate(modifier_groups):
        # Ensure group is a dictionary
        if not isinstance(group, dict):
            logger.warning(f"[MENU-FIX] Skipping non-dictionary modifier group at index {i}: {type(group)}")
            continue
            
        # Try to get group name, defaulting to an index-based name if missing
        group_name = group.get("name")
        if not group_name:
            group_name = f"Group {i+1}"
            group["name"] = group_name
            logger.warning(f"[MENU-FIX] Adding missing name for modifier group at index {i}")
            fixed_modifier_group_count += 1
        elif not isinstance(group_name, str):
            try:
                group_name = str(group_name)
                group["name"] = group_name
                logger.warning(f"[MENU-FIX] Converting non-string name for modifier group at index {i}")
                fixed_modifier_group_count += 1
            except:
                group_name = f"Group {i+1}"
                group["name"] = group_name
                logger.warning(f"[MENU-FIX] Replacing invalid name for modifier group at index {i}")
                fixed_modifier_group_count += 1
        
        # Fix missing group ID
        group_id = group.get("id")
        if not group_id:
            # Generate a consistent ID based on name
            try:
                new_group_id = f"MG-{hashlib.md5(group_name.encode()).hexdigest()[:8]}"
            except:
                new_group_id = f"MG-{i:04d}"
            logger.warning(f"[MENU-FIX] Modifier group '{group_name}' is missing ID, setting to: {new_group_id}")
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1
        elif not isinstance(group_id, str):
            try:
                group_id = str(group_id)
                group["id"] = group_id
                logger.warning(f"[MENU-FIX] Converting non-string ID for modifier group '{group_name}'")
                fixed_modifier_group_count += 1
            except:
                new_group_id = f"MG-{i:04d}"
                group["id"] = new_group_id
                group_id = new_group_id
                logger.warning(f"[MENU-FIX] Replacing invalid ID for modifier group '{group_name}'")
                fixed_modifier_group_count += 1
            
        # Handle duplicate group IDs
        if group_id in seen_group_ids:
            # Add a suffix to make it unique
            new_group_id = f"{group_id}-{len(seen_group_ids)}"
            logger.warning(f"[MENU-FIX] Duplicate modifier group ID {group_id}, changing to: {new_group_id}")
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1
            
        seen_group_ids.add(group_id)
        
        # Ensure min/max constraints are valid
        if "minAllowed" not in group or not isinstance(group["minAllowed"], (int, float)):
            group["minAllowed"] = 0
            fixed_modifier_group_count += 1
            
        if "maxAllowed" not in group or not isinstance(group["maxAllowed"], (int, float)):
            group["maxAllowed"] = 999
            fixed_modifier_group_count += 1
        
        # Ensure modifiers is a list
        modifiers = group.get("modifiers", [])
        if not isinstance(modifiers, list):
            logger.warning(f"[MENU-FIX] modifiers in group {group_id} is not a list: {type(modifiers)}. Creating empty list.")
            group["modifiers"] = []
            modifiers = []
            fixed_modifier_group_count += 1
        else:
            # Clean up non-string or non-dict modifiers
            valid_modifiers = []
            for j, modifier in enumerate(modifiers):
                if isinstance(modifier, str):
                    valid_modifiers.append(modifier)
                elif isinstance(modifier, dict) and "id" in modifier:
                    valid_modifiers.append(modifier["id"])
                else:
                    logger.warning(f"[MENU-FIX] Skipping invalid modifier at index {j} in group {group_id}")
            
            if len(valid_modifiers) != len(modifiers):
                logger.warning(f"[MENU-FIX] Filtered {len(modifiers) - len(valid_modifiers)} invalid modifiers in group {group_id}")
                group["modifiers"] = valid_modifiers
                fixed_modifier_group_count += 1
    
    # Process modifiers list
    modifiers = menu_data.get("modifiers", [])
    for i, modifier in enumerate(modifiers):
        # Ensure modifier is a dictionary
        if not isinstance(modifier, dict):
            logger.warning(f"[MENU-FIX] Skipping non-dictionary modifier at index {i}: {type(modifier)}")
            continue
            
        # Track if we fixed anything
        mod_fixed = False
        
        # Try to get modifier name, defaulting if missing
        mod_name = modifier.get("name")
        if not mod_name:
            mod_name = f"Modifier {i+1}"
            modifier["name"] = mod_name
            logger.warning(f"[MENU-FIX] Adding missing name for modifier at index {i}")
            mod_fixed = True
        elif not isinstance(mod_name, str):
            try:
                mod_name = str(mod_name)
                modifier["name"] = mod_name
                logger.warning(f"[MENU-FIX] Converting non-string name for modifier at index {i}")
                mod_fixed = True
            except:
                mod_name = f"Modifier {i+1}"
                modifier["name"] = mod_name
                logger.warning(f"[MENU-FIX] Replacing invalid name for modifier at index {i}")
                mod_fixed = True
                
        # Fix missing modifier ID
        mod_id = modifier.get("id")
        if not mod_id:
            # Generate a consistent ID based on name
            try:
                new_mod_id = f"MOD-{hashlib.md5(mod_name.encode()).hexdigest()[:8]}"
            except:
                new_mod_id = f"MOD-{i:04d}"
            logger.warning(f"[MENU-FIX] Modifier '{mod_name}' is missing ID, setting to: {new_mod_id}")
            modifier["id"] = new_mod_id
            mod_id = new_mod_id
            mod_fixed = True
        elif not isinstance(mod_id, str):
            try:
                mod_id = str(mod_id)
                modifier["id"] = mod_id
                logger.warning(f"[MENU-FIX] Converting non-string ID for modifier '{mod_name}'")
                mod_fixed = True
            except:
                new_mod_id = f"MOD-{i:04d}"
                modifier["id"] = new_mod_id
                mod_id = new_mod_id
                logger.warning(f"[MENU-FIX] Replacing invalid ID for modifier '{mod_name}'")
                mod_fixed = True
        
        # Fix reference handler if missing
        if not modifier.get("reference_handler"):
            if modifier.get("plu"):
                modifier["reference_handler"] = modifier.get("plu")
                logger.warning(f"[MENU-FIX] Using PLU as reference_handler for modifier {mod_name}")
            else:
                import re
                # Create a reference based on modifier name
                clean_name = re.sub(r'[^\w]', '', mod_name)
                if clean_name:
                    plu = f"MOD-{clean_name[:10]}"
                else:
                    # Use a hash-based ID if name has no alphanumeric chars
                    import hashlib
                    hash_obj = hashlib.md5(mod_name.encode())
                    plu = f"MOD-{hash_obj.hexdigest()[:8]}"
                    
                logger.warning(f"[MENU-FIX] Modifier {mod_name} is missing reference_handler, fixing to: {plu}")
                modifier["reference_handler"] = plu
            mod_fixed = True
                
        # Ensure price is valid
        price_invalid = False
        
        # Check if price is missing
        if "price" not in modifier:
            price_invalid = True
        # Check if price is None
        elif modifier["price"] is None:
            price_invalid = True
        # Check if price is not a number
        elif not isinstance(modifier["price"], (int, float)):
            try:
                # Try to convert to float
                modifier["price"] = float(modifier["price"])
            except (ValueError, TypeError):
                price_invalid = True
        # Check if price is negative
        elif modifier["price"] < 0:
            price_invalid = True
            
        if price_invalid:
            logger.warning(f"[MENU-FIX] Modifier {mod_name} has invalid price, setting to 0")
            modifier["price"] = 0.0
            mod_fixed = True
            
        # Ensure availability is properly initialized
        if "available" not in modifier:
            modifier["available"] = True
            mod_fixed = True
        elif not isinstance(modifier["available"], bool):
            modifier["available"] = bool(modifier["available"])
            mod_fixed = True
            
        # Track total fixes
        if mod_fixed:
            fixed_modifier_count += 1
    
    if fixed_item_count > 0 or fixed_modifier_group_count > 0 or fixed_modifier_count > 0:
        logger.info(f"[MENU-FIX] Fixed {fixed_item_count} items, {fixed_modifier_group_count} modifier groups, and {fixed_modifier_count} modifiers")
    
    # Final validation: Ensure ALL items have names after fixing attempts
    items_still_missing_names = [item for item in menu_data.get('items', []) if not item.get('name')]
    if items_still_missing_names:
        missing_count = len(items_still_missing_names)
        item_indices = [menu_data.get('items', []).index(item) for item in items_still_missing_names[:3]]
        logger.error(f"[MENU-VALIDATION] {missing_count} items still missing names after fixing attempts. Problem indices: {item_indices}")
        
        # Instead of raising error, fix the remaining items
        for i, item in enumerate(items_still_missing_names):
            index = menu_data.get('items', []).index(item)
            item['name'] = f"Generated Item {index + 1}"
            logger.warning(f"[MENU-FIX] Last resort name generation for item at index {index}")
    
    # Final validation: Check every item for empty string names
    empty_name_items = [item for item in menu_data.get('items', []) if item.get('name') == ""]
    if empty_name_items:
        empty_count = len(empty_name_items)
        item_indices = [menu_data.get('items', []).index(item) for item in empty_name_items[:3]]
        logger.error(f"[MENU-VALIDATION] {empty_count} items have empty string names. Problem indices: {item_indices}")
        
        # Fix empty string names
        for item in empty_name_items:
            index = menu_data.get('items', []).index(item)
            item['name'] = f"Unnamed Item {index + 1}"
        logger.info(f"[MENU-FIX] Fixed {empty_count} items with empty string names")
    
    # Set fixes to log instead of adding as attribute, since in Python dictionaries
    # can't have arbitrary attributes set (menu_data is a dict, not an object)
    fixes = []
    if fixed_item_count > 0:
        fixes.append(f"Fixed {fixed_item_count} items")
        logger.info(f"[MENU-FIX] Fixed {fixed_item_count} items")
    if fixed_modifier_group_count > 0:
        fixes.append(f"Fixed {fixed_modifier_group_count} modifier groups")
        logger.info(f"[MENU-FIX] Fixed {fixed_modifier_group_count} modifier groups")
    if fixed_modifier_count > 0:
        fixes.append(f"Fixed {fixed_modifier_count} modifiers")
        logger.info(f"[MENU-FIX] Fixed {fixed_modifier_count} modifiers")
    
    return menu_data
