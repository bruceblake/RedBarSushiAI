"""
Order utility functions for handling orders.
This module provides utility functions for order processing and validation.
Ensures orders sent to Deliverect contain only valid menu items with proper reference handlers.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from flask import session
from Levenshtein import distance as levenshtein_distance

# Import menu utilities for order validation
from app.utils.menu_utils import (
    find_menu_item_by_name,
    load_menu_data,
    is_item_snoozed_timebased,
)
from app.utils.menu_matcher import find_menu_item_ai
from app.utils.snooze_validator import is_item_available, validate_items_availability

logger = logging.getLogger(__name__)

# Menu search and matching functions


def find_menu_item(
    item_name: str, threshold: int = 35, context: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """
    Find a menu item based on the given name, using AI matching if needed.
    Only returns available items (not snoozed or unavailable).

    Args:
        item_name: Name of the item to find
        threshold: Maximum Levenshtein distance for fuzzy matching (used as fallback)
        context: Additional context about the order/conversation for AI matching

    Returns:
        Tuple of (menu_item, distance) if found, (None, None) otherwise
    """
    if not item_name:
        return None, None

    # Clean up the name for comparison
    cleaned_name = item_name.lower().strip()

    # Load menu data
    menu_data = load_menu_data()

    # First try direct name match to avoid unnecessary API calls
    for item in menu_data.get("items", []):
        if (
            item.get("name", "").lower() == cleaned_name
            and item.get("available", True)
            and not item.get("snoozed", False)
        ):
            logger.info(f"[FIND-ITEM] Found exact match: {cleaned_name}")
            return item, 0

    # Try AI matching
    ai_match = find_menu_item_ai(item_name, check_availability=True, context=context)
    if ai_match:
        logger.info(f"[FIND-ITEM] Found AI match: {cleaned_name} -> {ai_match.get('name')}")
        return ai_match, 10  # Use a standard distance for AI matches
    
    # As a fallback, try fuzzy matching if AI matching fails
    # This is especially useful if there are API issues or rate limiting
    best_match = None
    best_distance = float("inf")

    for item in menu_data.get("items", []):
        if not item.get("available", True) or item.get("snoozed", False):
            continue

        menu_item_name = item.get("name", "").lower()
        if not menu_item_name:
            continue

        # Calculate Levenshtein distance
        dist = levenshtein_distance(cleaned_name, menu_item_name)

        # Update best match if this distance is smaller
        if dist < best_distance and dist <= threshold:
            best_match = item
            best_distance = dist

    if best_match:
        logger.info(
            f"[FIND-ITEM] Found fuzzy match (fallback): {cleaned_name} -> {best_match['name']} (distance: {best_distance})"
        )
        return best_match, best_distance

    logger.warning(f"[FIND-ITEM] No match found for: {cleaned_name}")
    return None, None


def find_menu_item_any_status(
    item_name: str, threshold: int = 35, context: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """
    Find a menu item based on the given name, regardless of availability status.

    Args:
        item_name: Name of the item to find
        threshold: Maximum Levenshtein distance for fuzzy matching (used as fallback)
        context: Additional context about the order/conversation for AI matching

    Returns:
        Tuple of (menu_item, distance) if found, (None, None) otherwise
    """
    if not item_name:
        return None, None

    # Clean up the name for comparison
    cleaned_name = item_name.lower().strip()

    # Load menu data
    menu_data = load_menu_data()

    # First try direct name match to avoid unnecessary API calls
    for item in menu_data.get("items", []):
        if item.get("name", "").lower() == cleaned_name:
            logger.info(f"[FIND-ITEM-ANY] Found exact match: {cleaned_name}")
            return item, 0

    # Try AI matching without availability check
    ai_match = find_menu_item_ai(item_name, check_availability=False, context=context)
    if ai_match:
        logger.info(f"[FIND-ITEM-ANY] Found AI match: {cleaned_name} -> {ai_match.get('name')}")
        return ai_match, 10  # Use a standard distance for AI matches
    
    # As a fallback, try fuzzy matching if AI matching fails
    best_match = None
    best_distance = float("inf")

    for item in menu_data.get("items", []):
        menu_item_name = item.get("name", "").lower()
        if not menu_item_name:
            continue

        # Calculate Levenshtein distance
        dist = levenshtein_distance(cleaned_name, menu_item_name)

        # Update best match if this distance is smaller
        if dist < best_distance and dist <= threshold:
            best_match = item
            best_distance = dist

    if best_match:
        logger.info(
            f"[FIND-ITEM-ANY] Found fuzzy match (fallback): {cleaned_name} -> {best_match['name']} (distance: {best_distance})"
        )
        return best_match, best_distance 

    logger.warning(f"[FIND-ITEM-ANY] No match found for: {cleaned_name}")
    return None, None


# Simple helper functions for voice interactions


def user_said_yes(text: str) -> bool:
    """Check if user's input is affirmative."""
    if not text:
        return False

    text = text.lower().strip()

    # Simple pattern matching for yes responses
    affirmatives = [
        "yes",
        "yeah",
        "yep",
        "correct",
        "right",
        "confirm",
        "confirmed",
        "okay",
        "ok",
        "good",
        "sure",
        "exactly",
    ]
    return any(word in text for word in affirmatives)


def user_said_no(text: str) -> bool:
    """Check if user's input is negative."""
    if not text:
        return False

    text = text.lower().strip()

    # Simple pattern matching for no responses
    negatives = [
        "no",
        "nope",
        "nah",
        "not correct",
        "that's wrong",
        "incorrect",
        "need to make changes",
        "needs changes",
        "change",
        "changes",
    ]
    return any(word in text for word in negatives)


def dtmf_yes_no(dtmf: str) -> str:
    """Convert DTMF input to yes/no."""
    if dtmf == "1":
        return "yes"
    elif dtmf == "2":
        return "no"
    return None


def build_order_description(order_items: List[Dict[str, Any]]) -> str:
    """Build a text description of the order with grouped items."""
    description = []

    # Separate available and unavailable items
    available_items = []
    unavailable_items = []

    for item in order_items:
        # Check if item is marked as unavailable or has a specific unavailability flag
        if (
            item.get("not_available")
            or "(not on menu)" in str(item.get("name", ""))
            or "(unavailable)" in str(item.get("name", ""))
        ):
            unavailable_items.append(item)
        else:
            available_items.append(item)

    # Group available items by name and modifiers
    grouped_items = {}
    for item in available_items:
        name = item.get("name", "unknown item")
        quantity = item.get("quantity", 1)
        modifiers = item.get("modifier", [])

        # Create a key that includes the name and modifiers
        if modifiers:
            # Sort modifiers to ensure consistent grouping
            sorted_mods = sorted(modifiers, key=lambda x: x.get("name", ""))
            mod_key = tuple(
                [(mod.get("name", ""), mod.get("quantity", 1)) for mod in sorted_mods]
            )
            key = (name, mod_key)
        else:
            key = (name, ())

        # Add to the grouped items
        if key in grouped_items:
            grouped_items[key] += quantity
        else:
            grouped_items[key] = quantity

    # Format grouped items
    for (name, mod_key), total_quantity in grouped_items.items():
        if not mod_key:  # No modifiers
            description.append(f"- {total_quantity} {name}")
        else:
            mod_strs = []
            for mod_name, mod_quantity in mod_key:
                if mod_quantity > 1:
                    mod_strs.append(f"{mod_quantity} {mod_name}")
                else:
                    mod_strs.append(mod_name)

            mods_text = ", ".join(mod_strs)
            description.append(f"- {total_quantity} {name} with {mods_text}")

    # Add unavailable items with clear indication
    if unavailable_items:
        description.append("\nUnavailable items:")
        for item in unavailable_items:
            name = item.get("name", "unknown item")
            reason = item.get("reason", "Currently unavailable")
            description.append(f"- {name} - {reason}")

    return "\n".join(description)


def mark_unavailable_items(
    order_items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Mark items that don't exist on the menu or are unavailable.
    Also ensures items have required reference_handlers.

    Args:
        order_items: List of order items to evaluate

    Returns:
        Tuple: (available_items, unavailable_items)
    """
    available_items = []
    unavailable_items = []

    for item in order_items:
        # Skip items already marked as unavailable
        if (
            item.get("not_available")
            or "(not on menu)" in str(item.get("name", ""))
            or "(unavailable)" in str(item.get("name", ""))
        ):
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
            # Item is available - copy reference handler and other essential fields
            if "reference_handler" not in item and menu_item.get("reference_handler"):
                item["reference_handler"] = menu_item["reference_handler"]
                logger.info(f"[MARK-ITEMS] Added reference_handler '{menu_item['reference_handler']}' to item '{name}'")

            if "price" not in item and menu_item.get("price") is not None:
                item["price"] = menu_item["price"]

            # Process modifiers to ensure they have reference handlers
            if "modifier" in item and isinstance(item["modifier"], list):
                for mod in item["modifier"]:
                    if isinstance(mod, dict) and "name" in mod and "reference_handler" not in mod:
                        # Try to find modifier in menu and get its reference handler
                        menu_data = load_menu_data()
                        mod_name_lower = mod["name"].lower()
                        
                        # Look through all menu modifiers
                        found_modifier = None
                        for menu_mod in menu_data.get("modifiers", []):
                            menu_mod_name = menu_mod.get("name", "").lower()
                            if menu_mod_name == mod_name_lower or mod_name_lower in menu_mod_name or menu_mod_name in mod_name_lower:
                                found_modifier = menu_mod
                                break
                        
                        if found_modifier:
                            mod["reference_handler"] = found_modifier["reference_handler"]
                            mod["price"] = found_modifier.get("price", 0.0)
                            logger.info(f"[MARK-ITEMS] Added reference_handler '{found_modifier['reference_handler']}' to modifier '{mod['name']}'")
                        else:
                            # Create a placeholder reference handler
                            mod["reference_handler"] = f"MOD-{mod_name_lower.replace(' ', '-')}"
                            mod["price"] = mod.get("price", 0.0)
                            logger.warning(f"[MARK-ITEMS] Created placeholder reference_handler '{mod['reference_handler']}' for modifier '{mod['name']}'")
            
            available_items.append(item)

    return available_items, unavailable_items


def calculate_bill_amount(
    order_items: List[Dict[str, Any]], tax_rate: float = 0.0
) -> float:
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
        session["subtotal"] = round(subtotal, 2)
        session["tax_amount"] = round(tax_amount, 2)
        session["total_price"] = round(total, 2)
    except RuntimeError:
        # Not in request context
        pass

    return round(total, 2)


# Order modification functions


def apply_modifications(
    current_items: List[Dict[str, Any]], modifications: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Apply modifications (additions, removals, and modifications) to the current order items.

    Args:
        current_items: Current order items
        modifications: Dictionary with 'additions', 'removals', and 'modifications' lists

    Returns:
        List of updated order items
    """
    if not current_items:
        current_items = []

    # Create a copy to avoid modifying the original
    updated_items = current_items.copy()
    
    # Log the incoming modifications for debugging
    logger.info(f"[APPLY-MODS] Applying modifications: {json.dumps(modifications)}")

    # Handle additions
    for addition in modifications.get("additions", []):
        # Make sure modifiers array exists
        if "modifier" not in addition:
            addition["modifier"] = []
        
        # Make sure quantity is set
        if "quantity" not in addition:
            addition["quantity"] = 1
            
        # Add the new item
        logger.info(f"[APPLY-MODS] Adding item: {addition.get('name')} with {len(addition.get('modifier', []))} modifiers")
        updated_items.append(addition)

    # Handle item-specific modifications (adding modifiers to existing items)
    for modification in modifications.get("modifications", []):
        item_name = modification.get("item_name")
        
        if not item_name:
            logger.warning("[APPLY-MODS] Modification missing item_name, skipping")
            continue
            
        # Find the target item
        target_item = None
        for item in updated_items:
            if item.get("name") == item_name:
                target_item = item
                break
                
        if not target_item:
            logger.warning(f"[APPLY-MODS] Item to modify not found: {item_name}, skipping")
            continue
            
        # Ensure the target item has a modifiers array
        if "modifier" not in target_item:
            target_item["modifier"] = []
            
        # Apply the modifiers to the target item
        for mod in modification.get("modifier", []):
            target_item["modifier"].append(mod)
            logger.info(f"[APPLY-MODS] Added modifier {mod.get('name')} to {item_name}")

    # Handle removals
    for removal in modifications.get("removals", []):
        removal_name = removal.get("name")
        removal_quantity = removal.get("quantity", 1)

        if not removal_name:
            logger.warning("[APPLY-MODS] Removal missing name, skipping")
            continue

        # Find the item to remove
        for i, item in enumerate(updated_items):
            if item.get("name") == removal_name:
                if item.get("quantity", 1) <= removal_quantity:
                    # Remove the entire item
                    logger.info(f"[APPLY-MODS] Removing item: {removal_name}")
                    updated_items.pop(i)
                else:
                    # Reduce the quantity
                    item["quantity"] = item.get("quantity", 1) - removal_quantity
                    logger.info(f"[APPLY-MODS] Reducing quantity of {removal_name} to {item['quantity']}")
                break

    return updated_items


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
    all_menu_items = {
        item.get("reference_handler"): item
        for item in menu_data.get("items", [])
        if item.get("reference_handler")
    }

    # Get only available menu items (not snoozed or unavailable)
    available_menu_items = {}
    for ref, item in all_menu_items.items():
        if is_item_available(item):
            available_menu_items[ref] = item

    logger.info(
        f"[ORDER-VALIDATE] Found {len(available_menu_items)}/{len(all_menu_items)} available menu items"
    )

    # Process each item in the order
    for item in order_items:
        # Get name for logging
        item_name = item.get("name", "Unknown item")

        # If it already has a reference handler, check it directly
        if "reference_handler" in item and item["reference_handler"]:
            ref = item["reference_handler"]

            # First check if it exists at all
            if ref not in all_menu_items:
                logger.warning(
                    f"[ORDER-VALIDATE] Item '{item_name}' with reference '{ref}' not found in menu"
                )
                unavailable_items.append(item_name)
                continue

            # Then check if it's available
            if ref in available_menu_items:
                # Item exists and is available
                logger.info(
                    f"[ORDER-VALIDATE] Item '{item_name}' has valid reference handler: {ref}"
                )
                # Ensure we have latest price info
                item["price"] = available_menu_items[ref].get(
                    "price", item.get("price", 0.0)
                )
                valid_items.append(item)
            else:
                # Item exists but is not available (snoozed or unavailable)
                menu_item = all_menu_items[ref]

                # Give specific reasons for unavailability
                if menu_item.get("snoozed", False):
                    logger.warning(
                        f"[ORDER-VALIDATE] Item '{item_name}' is snoozed and unavailable"
                    )
                elif is_item_snoozed_timebased(menu_item):
                    logger.warning(
                        f"[ORDER-VALIDATE] Item '{item_name}' is time-snoozed and unavailable"
                    )
                elif not menu_item.get("available", True):
                    logger.warning(
                        f"[ORDER-VALIDATE] Item '{item_name}' is marked as unavailable"
                    )
                else:
                    logger.warning(
                        f"[ORDER-VALIDATE] Item '{item_name}' is unavailable for an unknown reason"
                    )

                unavailable_items.append(item_name)

        # Otherwise look it up by name
        elif "name" in item and item["name"]:
            # First check if it's available
            menu_item = find_menu_item_by_name(item["name"], check_availability=True)
            if menu_item and menu_item.get("reference_handler"):
                # Found a match that's available - fill in the reference handler
                item["reference_handler"] = menu_item["reference_handler"]
                item["price"] = menu_item.get("price", 0.0)
                logger.info(
                    f"[ORDER-VALIDATE] Found available item: {item_name} → {item['reference_handler']}"
                )
                valid_items.append(item)
            else:
                # Try to find the item regardless of availability
                menu_item = find_menu_item_by_name(
                    item["name"], check_availability=False
                )
                if menu_item:
                    # Item exists but is unavailable
                    if menu_item.get("reference_handler"):
                        item["reference_handler"] = menu_item["reference_handler"]
                        item["price"] = menu_item.get("price", 0.0)

                    # Give specific reasons for unavailability
                    if menu_item.get("snoozed", False):
                        logger.warning(
                            f"[ORDER-VALIDATE] Item '{item_name}' is snoozed and unavailable"
                        )
                    elif is_item_snoozed_timebased(menu_item):
                        logger.warning(
                            f"[ORDER-VALIDATE] Item '{item_name}' is time-snoozed and unavailable"
                        )
                    elif not menu_item.get("available", True):
                        logger.warning(
                            f"[ORDER-VALIDATE] Item '{item_name}' is marked as unavailable"
                        )
                    else:
                        logger.warning(
                            f"[ORDER-VALIDATE] Item '{item_name}' is unavailable for an unknown reason"
                        )
                else:
                    # Item not found in the menu at all
                    logger.warning(
                        f"[ORDER-VALIDATE] Item '{item_name}' not found in menu"
                    )

                unavailable_items.append(item_name)
        else:
            logger.warning(
                "[ORDER-VALIDATE] Item has no name or reference handler, skipping"
            )

    # Log validation results
    if valid_items:
        logger.info(f"[ORDER-VALIDATE] Validated {len(valid_items)} items for order")
    else:
        logger.warning("[ORDER-VALIDATE] No valid items in order after validation")

    if unavailable_items:
        logger.warning(
            f"[ORDER-VALIDATE] Unavailable items: {', '.join(unavailable_items)}"
        )

    return valid_items


def validate_modifiers(order_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates that all modifiers in the order exist in the menu, are available,
    and have proper reference handlers for Deliverect.
    Allows custom modifiers (not in menu) to pass through with placeholder reference handlers.

    Args:
        order_items: List of order items with modifiers

    Returns:
        List of order items with validated modifiers
    """
    # Load the current menu
    menu_data = load_menu_data(force_refresh=True)

    # Get all valid modifiers by reference handler for quick lookup
    valid_modifiers = {
        mod.get("reference_handler"): mod
        for mod in menu_data.get("modifiers", [])
        if mod.get("reference_handler")
        and mod.get("available", True)
        and not mod.get("snoozed", False)
    }

    # Get all valid modifiers by name for lookup
    modifiers_by_name = {
        mod.get("name", "").lower(): mod
        for mod in menu_data.get("modifiers", [])
        if mod.get("name")
        and mod.get("available", True)
        and not mod.get("snoozed", False)
    }

    # Process each item's modifiers
    for item in order_items:
        if "modifier" not in item or not isinstance(item["modifier"], list):
            item["modifier"] = []
            continue

        valid_modifiers_for_item = []

        for mod in item["modifier"]:
            if not isinstance(mod, dict):
                logger.warning(
                    f"[ORDER-VALIDATE] Skipping non-dictionary modifier: {mod}"
                )
                continue

            # If it already has a reference handler, check it directly
            if "reference_handler" in mod and mod["reference_handler"]:
                if mod["reference_handler"] in valid_modifiers:
                    # Modifier exists and is available in the menu
                    logger.info(f"[ORDER-VALIDATE] Found valid menu modifier: {mod.get('name')} with reference {mod['reference_handler']}")
                    valid_modifiers_for_item.append(mod)
                else:
                    # Modifier doesn't exist in menu but has a reference handler
                    # We'll keep it anyway and log a warning, rather than dropping it
                    logger.warning(
                        f"[ORDER-VALIDATE] Modifier with reference '{mod.get('reference_handler')}' not found in menu but keeping it: {mod.get('name')}"
                    )
                    valid_modifiers_for_item.append(mod)

            # Otherwise look it up by name
            elif "name" in mod and mod["name"]:
                mod_name = mod["name"].lower()
                # Try exact match first
                if mod_name in modifiers_by_name:
                    # Found an exact match - fill in the reference handler
                    menu_mod = modifiers_by_name[mod_name]
                    mod["reference_handler"] = menu_mod["reference_handler"]
                    mod["price"] = menu_mod.get("price", 0.0)
                    logger.info(
                        f"[ORDER-VALIDATE] Found exact modifier match by name: {mod['name']} → {mod['reference_handler']}"
                    )
                    valid_modifiers_for_item.append(mod)
                else:
                    # Try fuzzy matching
                    found_match = False
                    for menu_mod_name, menu_mod in modifiers_by_name.items():
                        # Check for partial matches in either direction
                        if mod_name in menu_mod_name or menu_mod_name in mod_name:
                            mod["reference_handler"] = menu_mod["reference_handler"]
                            mod["price"] = menu_mod.get("price", 0.0)
                            logger.info(
                                f"[ORDER-VALIDATE] Found fuzzy modifier match: {mod['name']} ≈ {menu_mod['name']} → {mod['reference_handler']}"
                            )
                            valid_modifiers_for_item.append(mod)
                            found_match = True
                            break
                    
                    if not found_match:
                        # No match found, but create a placeholder reference handler and keep it
                        mod["reference_handler"] = f"MOD-{mod_name.replace(' ', '-')}"
                        mod["price"] = mod.get("price", 0.0)
                        logger.warning(
                            f"[ORDER-VALIDATE] Modifier not found in menu but creating placeholder: {mod.get('name')} → {mod['reference_handler']}"
                        )
                        valid_modifiers_for_item.append(mod)
            else:
                logger.warning(
                    "[ORDER-VALIDATE] Modifier has no name or reference handler, skipping"
                )

        # Update the item with valid modifiers
        if len(valid_modifiers_for_item) < len(item["modifier"]):
            logger.warning(
                f"[ORDER-VALIDATE] {len(item['modifier']) - len(valid_modifiers_for_item)} modifiers could not be processed for item {item.get('name')}"
            )
        
        # Log all the modifiers we're keeping
        if valid_modifiers_for_item:
            logger.info(f"[ORDER-VALIDATE] Keeping {len(valid_modifiers_for_item)} modifiers for {item.get('name')}")
            mod_names = [f"{mod.get('name')}({mod.get('reference_handler')})" for mod in valid_modifiers_for_item]
            logger.info(f"[ORDER-VALIDATE] Modifiers: {', '.join(mod_names)}")

        item["modifier"] = valid_modifiers_for_item

    return order_items


def prepare_order_for_deliverect(
    order_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Prepares the order for Deliverect by validating items and modifiers.

    Args:
        order_items: List of order items

    Returns:
        List of validated order items ready for Deliverect
    """
    # Log initial order items
    if order_items:
        logger.info(f"[ORDER-PREPARE] Preparing {len(order_items)} items for Deliverect")
        for item in order_items:
            mod_count = len(item.get("modifier", []))
            logger.info(f"[ORDER-PREPARE] Initial item: {item.get('name')} with {mod_count} modifiers")
            if mod_count > 0:
                mod_names = [mod.get('name', 'unnamed') for mod in item.get("modifier", [])]
                logger.info(f"[ORDER-PREPARE] Modifiers: {', '.join(mod_names)}")
    
    # Step 1: Validate items exist in menu and are available
    valid_items = validate_order_items(order_items)
    
    # Log items after first validation
    logger.info(f"[ORDER-PREPARE] After item validation: {len(valid_items)} valid items")

    # Step 2: Validate modifiers exist and are available
    valid_items_with_modifiers = validate_modifiers(valid_items)
    
    # Log items after modifier validation
    logger.info(f"[ORDER-PREPARE] After modifier validation: {len(valid_items_with_modifiers)} valid items")
    for item in valid_items_with_modifiers:
        mod_count = len(item.get("modifier", []))
        logger.info(f"[ORDER-PREPARE] Item after modifier validation: {item.get('name')} with {mod_count} modifiers")

    # Step 3: Perform comprehensive availability validation using snooze_validator
    fully_validated_items = validate_items_availability(valid_items_with_modifiers)

    # Log any items that were filtered out in the final validation
    if len(fully_validated_items) < len(valid_items_with_modifiers):
        removed_items = [
            item.get("name", "Unknown")
            for item in valid_items_with_modifiers
            if item not in fully_validated_items
        ]
        logger.warning(
            f"[ORDER-VALIDATE-FINAL] Items removed in final availability check: {', '.join(removed_items)}"
        )

    # Step 4: Ensure all items have reference handlers before returning
    final_items = []
    for item in fully_validated_items:
        if not item.get("reference_handler"):
            # Try to find it again by name as a last resort
            menu_item = find_menu_item_by_name(item.get("name", ""))
            if menu_item and menu_item.get("reference_handler"):
                item["reference_handler"] = menu_item["reference_handler"]
                item["price"] = menu_item.get("price", 0.0)
                logger.info(
                    f"[ORDER-VALIDATE-FINAL] Found missing reference handler for {item.get('name')}"
                )
                final_items.append(item)
            else:
                # If we still can't find a reference handler, create a placeholder and keep it anyway
                item["reference_handler"] = f"ITEM-{item.get('name', '').lower().replace(' ', '-')}"
                logger.warning(
                    f"[ORDER-VALIDATE-FINAL] Created placeholder reference handler for {item.get('name')}: {item['reference_handler']}"
                )
                final_items.append(item)
        else:
            final_items.append(item)

    # Log the final order
    logger.info(f"[ORDER-VALIDATE-FINAL] Final order has {len(final_items)} items")
    for item in final_items:
        mod_count = len(item.get("modifier", []))
        logger.info(f"[ORDER-VALIDATE-FINAL] Final item: {item.get('name')} ({item.get('reference_handler')}) with {mod_count} modifiers")
        if mod_count > 0:
            mod_details = [f"{mod.get('name')}({mod.get('reference_handler')})" for mod in item.get("modifier", [])]
            logger.info(f"[ORDER-VALIDATE-FINAL] Final modifiers: {', '.join(mod_details)}")

    # Return the fully validated order
    return final_items
