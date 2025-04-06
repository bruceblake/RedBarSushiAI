"""
Order utility functions for handling orders.
This module provides utility functions for order processing and validation.
Ensures orders sent to Deliverect contain only valid menu items with proper reference handlers.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from flask import session

# Import menu utilities for order validation
from app.utils.menu_utils import find_menu_item_by_name, load_menu_data

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
    negatives = ["no", "nope", "nah", "not correct", "that's wrong", "incorrect"]
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
    for item in order_items:
        quantity = item.get("quantity", 1)
        name = item.get("name", "unknown item")
        modifiers = item.get("modifier", [])
        
        if not modifiers:
            description.append(f"- {quantity} {name}")
        else:
            mods = ", ".join([f"{mod.get('quantity', 1)} {mod.get('name','')}" for mod in modifiers])
            description.append(f"- {quantity} {name} with {mods}")
            
    return "\n".join(description)

def calculate_bill_amount(order_items: List[Dict[str, Any]], tax_rate: float = 0.0) -> float:
    """Calculate the total bill amount for the order."""
    subtotal = 0.0
    
    for item in order_items:
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
    
    # Load the current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Get all valid menu items by reference handler for quick lookup
    valid_menu_items = {item.get("reference_handler"): item for item in menu_data.get("items", []) 
                     if item.get("reference_handler") and 
                        item.get("available", True) and 
                        not item.get("snoozed", False)}
    
    # Process each item in the order
    for item in order_items:
        # If it already has a reference handler, check it directly
        if "reference_handler" in item and item["reference_handler"]:
            if item["reference_handler"] in valid_menu_items:
                # Item exists and is available
                logger.info(f"[ORDER-VALIDATE] Item has valid reference handler: {item.get('name')}")
                valid_items.append(item)
            else:
                # Item doesn't exist or isn't available
                logger.warning(f"[ORDER-VALIDATE] Item with reference '{item.get('reference_handler')}' not found in menu or unavailable: {item.get('name')}")
        
        # Otherwise look it up by name
        elif "name" in item and item["name"]:
            menu_item = find_menu_item_by_name(item["name"])
            if menu_item and menu_item.get("reference_handler"):
                # Found a match - fill in the reference handler
                item["reference_handler"] = menu_item["reference_handler"]
                item["price"] = menu_item.get("price", 0.0)
                logger.info(f"[ORDER-VALIDATE] Found item by name: {item['name']} → {item['reference_handler']}")
                valid_items.append(item)
            else:
                # No match found
                logger.warning(f"[ORDER-VALIDATE] Item not found in menu: {item.get('name')}")
        else:
            logger.warning(f"[ORDER-VALIDATE] Item has no name or reference handler, skipping")
    
    # Log validation results
    if len(valid_items) < len(order_items):
        logger.warning(f"[ORDER-VALIDATE] Removed {len(order_items) - len(valid_items)} invalid items from order")
    
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
    
    # Return the validated order
    return valid_items_with_modifiers
