"""
Order utility functions for handling orders.
This module provides utility functions for order processing and validation.
Ensures orders sent to Deliverect contain only valid menu items with proper reference handlers.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from flask import session

# Import menu utilities for order validation
from app.utils.menu_utils import find_menu_item_by_name, load_menu_data, is_item_snoozed_timebased
from app.utils.snooze_validator import is_item_available, validate_items_availability

logger = logging.getLogger(__name__)

# Simple helper functions for voice interactions

def user_said_yes(text: str) -> bool:
    """Check if user's input is affirmative."""
    if not text:
        return False
        
    text = text.lower().strip()
    
    # Simple pattern matching for yes responses
    affirmatives = ["yes", "yeah", "yep", "correct", "right", "confirm", 
                    "confirmed", "okay", "ok", "good", "sure", "exactly"]
    return any(word in text for word in affirmatives)

def user_said_no(text: str) -> bool:
    """Check if user's input is negative."""
    if not text:
        return False
        
    text = text.lower().strip()
    
    # Simple pattern matching for no responses
    negatives = ["no", "nope", "nah", "not correct", "that's wrong", "incorrect", 
                "need to make changes", "needs changes", "change", "changes"]
    return any(word in text for word in negatives)

def dtmf_yes_no(dtmf: str) -> str:
    """Convert DTMF input to yes/no."""
    if dtmf == "1":
        return "yes"
    elif dtmf == "2":
        return "no"
    return None

def build_order_description(order_items: List[Dict[str, Any]]) -> str:
    """Build a text description of the order."""
    description = []
    
    # Separate available and unavailable items
    available_items = []
    unavailable_items = []
    
    for item in order_items:
        # Check if item is marked as unavailable or has a specific unavailability flag
        if item.get("not_available") or "(not on menu)" in str(item.get("name", "")) or "(unavailable)" in str(item.get("name", "")):
            unavailable_items.append(item)
        else:
            available_items.append(item)
    
    # Process available items first
    for item in available_items:
        quantity = item.get("quantity", 1)
        name = item.get("name", "unknown item")
        modifiers = item.get("modifier", [])
        
        if not modifiers:
            # Format with quantity × item name
            description.append(f"- {quantity}× {name}")
        else:
            mods = ", ".join([f"{mod.get('quantity', 1)}× {mod.get('name','')}" for mod in modifiers])
            description.append(f"- {quantity}× {name} with {mods}")
    
    # Add unavailable items with clear indication
    if unavailable_items:
        description.append("\nUnavailable items:")
        for item in unavailable_items:
            name = item.get("name", "unknown item")
            reason = item.get("reason", "Currently unavailable")
            description.append(f"- {name} - {reason}")
            
    return "\n".join(description)

def mark_unavailable_items(order_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Mark items that don't exist on the menu or are unavailable.
    
    Args:
        order_items: List of order items to evaluate
        
    Returns:
        Tuple: (available_items, unavailable_items)
    """
    available_items = []
    unavailable_items = []
    
    for item in order_items:
        # Skip items already marked as unavailable
        if item.get("not_available") or "(not on menu)" in str(item.get("name", "")) or "(unavailable)" in str(item.get("name", "")):
            unavailable_items.append(item)
            continue
            
        # Check if item exists in menu
        name = item.get("name", "")
        menu_item = find_menu_item_by_name(name)
        
        if not menu_item:
            # Item not found in menu
            item["name"] = f"{name} (not on menu)"
            item["not_available"] = True
            item["reason"] = "Item not found on our menu"
            unavailable_items.append(item)
        elif menu_item.get("snoozed", False) or not menu_item.get("available", True):
            # Item exists but is unavailable
            item["name"] = f"{name} (unavailable)"
            item["not_available"] = True
            item["reason"] = "Temporarily unavailable"
            unavailable_items.append(item)
        else:
            # Item is available
            available_items.append(item)
    
    return available_items, unavailable_items

def calculate_bill_amount(order_items: List[Dict[str, Any]], tax_rate: float = 0.0) -> float:
    """Calculate the total bill amount for the order."""
    subtotal = 0.0
    
    # Only include available items in price calculation
    available_items = [item for item in order_items if not item.get("not_available")]
    
    for item in available_items:
        price = item.get("price", 0.0)
        quantity = item.get("quantity", 1)
        item_total = price * quantity
        
        # Add modifier costs
        for mod in item.get("modifier", []):
            mod_price = mod.get("price", 0.0)
            mod_quantity = mod.get("quantity", 1)
            item_total += mod_price * mod_quantity
        
        subtotal += item_total
    
    # Calculate tax
    tax_amount = subtotal * tax_rate if tax_rate > 0 else 0.0
    
    # Calculate total
    total = subtotal + tax_amount
    
    # Store in session
    try:
        session['subtotal'] = round(subtotal, 2)
        session['tax_amount'] = round(tax_amount, 2)
        session['total_price'] = round(total, 2)
    except RuntimeError:
        # Not in request context
        pass
    
    return round(total, 2)
# Order validation functions for Deliverect

def validate_order_items(order_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates that all items in the order exist in the menu and are available.
    
    Args:
        order_items: List of order items
        
    Returns:
        List of valid order items (invalid items are removed)
    """
    valid_items = []
    unavailable_items = []
    
    # Load the current menu with a force refresh to get latest snooze status
    menu_data = load_menu_data(force_refresh=True)
    
    # Get all menu items by reference handler for quick lookup
    all_menu_items = {item.get("reference_handler"): item for item in menu_data.get("items", []) 
                     if item.get("reference_handler")}
    
    # Get only available menu items (not snoozed or unavailable)
    available_menu_items = {}
    for ref, item in all_menu_items.items():
        if is_item_available(item):
            available_menu_items[ref] = item
    
    logger.info(f"[ORDER-VALIDATE] Found {len(available_menu_items)}/{len(all_menu_items)} available menu items")
    
    # Process each item in the order
    for item in order_items:
        # Get name for logging
        item_name = item.get("name", "Unknown item")
        
        # If it already has a reference handler, check it directly
        if "reference_handler" in item and item["reference_handler"]:
            ref = item["reference_handler"]
            
            # First check if it exists at all
            if ref not in all_menu_items:
                logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' with reference '{ref}' not found in menu")
                unavailable_items.append(item_name)
                continue
                
            # Then check if it's available
            if ref in available_menu_items:
                # Item exists and is available
                logger.info(f"[ORDER-VALIDATE] Item '{item_name}' has valid reference handler: {ref}")
                # Ensure we have latest price info
                item["price"] = available_menu_items[ref].get("price", item.get("price", 0.0))
                valid_items.append(item)
            else:
                # Item exists but is not available (snoozed or unavailable)
                menu_item = all_menu_items[ref]
                
                # Give specific reasons for unavailability
                if menu_item.get("snoozed", False):
                    logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is snoozed and unavailable")
                elif is_item_snoozed_timebased(menu_item):
                    logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is time-snoozed and unavailable")
                elif not menu_item.get("available", True):
                    logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is marked as unavailable")
                else:
                    logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is unavailable for an unknown reason")
                
                unavailable_items.append(item_name)
        
        # Otherwise look it up by name
        elif "name" in item and item["name"]:
            # First check if it's available
            menu_item = find_menu_item_by_name(item["name"], check_availability=True)
            if menu_item and menu_item.get("reference_handler"):
                # Found a match that's available - fill in the reference handler
                item["reference_handler"] = menu_item["reference_handler"]
                item["price"] = menu_item.get("price", 0.0)
                logger.info(f"[ORDER-VALIDATE] Found available item: {item_name} → {item['reference_handler']}")
                valid_items.append(item)
            else:
                # Try to find the item regardless of availability
                menu_item = find_menu_item_by_name(item["name"], check_availability=False)
                if menu_item:
                    # Item exists but is unavailable
                    if menu_item.get("reference_handler"):
                        item["reference_handler"] = menu_item["reference_handler"]
                        item["price"] = menu_item.get("price", 0.0)
                    
                    # Give specific reasons for unavailability
                    if menu_item.get("snoozed", False):
                        logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is snoozed and unavailable")
                    elif is_item_snoozed_timebased(menu_item):
                        logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is time-snoozed and unavailable")
                    elif not menu_item.get("available", True):
                        logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is marked as unavailable")
                    else:
                        logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' is unavailable for an unknown reason")
                else:
                    # Item not found in the menu at all
                    logger.warning(f"[ORDER-VALIDATE] Item '{item_name}' not found in menu")
                
                unavailable_items.append(item_name)
        else:
            logger.warning(f"[ORDER-VALIDATE] Item has no name or reference handler, skipping")
    
    # Log validation results
    if valid_items:
        logger.info(f"[ORDER-VALIDATE] Validated {len(valid_items)} items for order")
    else:
        logger.warning("[ORDER-VALIDATE] No valid items in order after validation")
        
    if unavailable_items:
        logger.warning(f"[ORDER-VALIDATE] Unavailable items: {', '.join(unavailable_items)}")
    
    return valid_items

def validate_modifiers(order_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates that all modifiers in the order exist in the menu, are available,
    and have proper reference handlers for Deliverect.
    
    Args:
        order_items: List of order items with modifiers
        
    Returns:
        List of order items with validated modifiers
    """
    # Load the current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Get all valid modifiers by reference handler for quick lookup
    valid_modifiers = {mod.get("reference_handler"): mod for mod in menu_data.get("modifiers", []) 
                     if mod.get("reference_handler") and 
                        mod.get("available", True) and 
                        not mod.get("snoozed", False)}
    
    # Get all valid modifiers by name for lookup
    modifiers_by_name = {mod.get("name", "").lower(): mod for mod in menu_data.get("modifiers", []) 
                       if mod.get("name") and 
                          mod.get("available", True) and 
                          not mod.get("snoozed", False)}
    
    # Process each item's modifiers
    for item in order_items:
        if "modifier" not in item or not isinstance(item["modifier"], list):
            item["modifier"] = []
            continue
            
        valid_modifiers_for_item = []
        
        for mod in item["modifier"]:
            if not isinstance(mod, dict):
                logger.warning(f"[ORDER-VALIDATE] Skipping non-dictionary modifier: {mod}")
                continue
                
            # If it already has a reference handler, check it directly
            if "reference_handler" in mod and mod["reference_handler"]:
                if mod["reference_handler"] in valid_modifiers:
                    # Modifier exists and is available
                    valid_modifiers_for_item.append(mod)
                else:
                    # Modifier doesn't exist or isn't available
                    logger.warning(f"[ORDER-VALIDATE] Modifier with reference '{mod.get('reference_handler')}' not found in menu or unavailable: {mod.get('name')}")
            
            # Otherwise look it up by name
            elif "name" in mod and mod["name"]:
                mod_name = mod["name"].lower()
                if mod_name in modifiers_by_name:
                    # Found a match - fill in the reference handler
                    menu_mod = modifiers_by_name[mod_name]
                    mod["reference_handler"] = menu_mod["reference_handler"]
                    mod["price"] = menu_mod.get("price", 0.0)
                    logger.info(f"[ORDER-VALIDATE] Found modifier by name: {mod['name']} → {mod['reference_handler']}")
                    valid_modifiers_for_item.append(mod)
                else:
                    # No match found
                    logger.warning(f"[ORDER-VALIDATE] Modifier not found in menu: {mod.get('name')}")
            else:
                logger.warning(f"[ORDER-VALIDATE] Modifier has no name or reference handler, skipping")
        
        # Update the item with valid modifiers
        if len(valid_modifiers_for_item) < len(item["modifier"]):
            logger.warning(f"[ORDER-VALIDATE] Removed {len(item['modifier']) - len(valid_modifiers_for_item)} invalid modifiers from item {item.get('name')}")
        
        item["modifier"] = valid_modifiers_for_item
    
    return order_items

def prepare_order_for_deliverect(order_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepares the order for Deliverect by validating items and modifiers.
    
    Args:
        order_items: List of order items
        
    Returns:
        List of validated order items ready for Deliverect
    """
    # Step 1: Validate items exist in menu and are available
    valid_items = validate_order_items(order_items)
    
    # Step 2: Validate modifiers exist and are available
    valid_items_with_modifiers = validate_modifiers(valid_items)
    
    # Step 3: Perform comprehensive availability validation using snooze_validator
    from app.utils.snooze_validator import validate_items_availability
    fully_validated_items = validate_items_availability(valid_items_with_modifiers)
    
    # Log any items that were filtered out in the final validation
    if len(fully_validated_items) < len(valid_items_with_modifiers):
        removed_items = [item.get("name", "Unknown") for item in valid_items_with_modifiers 
                        if item not in fully_validated_items]
        logger.warning(f"[ORDER-VALIDATE-FINAL] Items removed in final availability check: {', '.join(removed_items)}")
        
    # Step 4: Ensure all items have reference handlers before returning
    for item in fully_validated_items:
        if not item.get("reference_handler"):
            # Try to find it again by name as a last resort
            menu_item = find_menu_item_by_name(item.get("name", ""))
            if menu_item and menu_item.get("reference_handler"):
                item["reference_handler"] = menu_item["reference_handler"]
                item["price"] = menu_item.get("price", 0.0)
                logger.info(f"[ORDER-VALIDATE-FINAL] Found missing reference handler for {item.get('name')}")
            else:
                # If we still can't find a reference handler, log it and remove the item
                logger.warning(f"[ORDER-VALIDATE-FINAL] Item {item.get('name')} has no reference handler, removing from order")
                fully_validated_items.remove(item)
    
    # Return the fully validated order
    return fully_validated_items
