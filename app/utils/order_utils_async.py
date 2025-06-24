"""
Order utility functions for handling orders (async version).
This module provides async utility functions for order processing and validation.
Ensures orders sent to Deliverect contain only valid menu items with proper reference handlers.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

# Import async menu utilities for order validation
from app.utils.menu_utils_db_async import (
    load_menu_data,  # Using async version
)
from app.utils.menu_matcher_cache_async import AsyncMenuMatcher
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher, get_cached_async_menu_matcher
from app.utils.snooze_validator import is_item_available, validate_items_availability  # These don't do DB operations

logger = logging.getLogger(__name__)

# Menu search and matching functions


async def find_menu_item_async(
    db: AsyncSession,
    item_name: str, 
    threshold: int = 35, 
    context: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """
    Find a menu item by name using various matching strategies (async version).
    
    Args:
        db: AsyncSession for database access
        item_name: Item name to search for
        threshold: Levenshtein distance threshold for fuzzy matching
        context: Optional context for AI matching
        
    Returns:
        Tuple of (matched_item, confidence_score)
    """
    logger.info(f"Looking for menu item: {item_name}")
    
    # Try to get an exact match first
    menu_matcher = await get_cached_async_menu_matcher(db)
    item_result, score = await menu_matcher.match_item(item_name)
    
    if item_result:
        logger.info(f"Found match for '{item_name}': {item_result.get('name')} with score {score}")
        return item_result, score
    else:
        logger.warning(f"No match found for '{item_name}'")
        return None, None


async def build_order_description_async(order_items: List[Dict[str, Any]]) -> str:
    """
    Build a human-readable description of an order (async version).
    
    Args:
        order_items: List of order items with modifiers
        
    Returns:
        Human-readable description of the order
    """
    if not order_items:
        return "Empty order"
    
    descriptions = []
    for item in order_items:
        quantity = item.get("quantity", 1)
        name = item.get("name", "Unknown item")
        
        # Build modifier description
        modifier_descriptions = []
        if "modifiers" in item and item["modifiers"]:
            for modifier in item["modifiers"]:
                mod_name = modifier.get("name", "Unknown modifier")
                mod_quantity = modifier.get("quantity", 1)
                
                if mod_quantity > 1:
                    modifier_descriptions.append(f"{mod_quantity}x {mod_name}")
                else:
                    modifier_descriptions.append(mod_name)
        
        # Add item description
        if modifier_descriptions:
            if quantity > 1:
                descriptions.append(f"{quantity}x {name} with {', '.join(modifier_descriptions)}")
            else:
                descriptions.append(f"{name} with {', '.join(modifier_descriptions)}")
        else:
            if quantity > 1:
                descriptions.append(f"{quantity}x {name}")
            else:
                descriptions.append(name)
    
    return ", ".join(descriptions)


async def calculate_bill_amount_async(order_items: List[Dict[str, Any]]) -> float:
    """
    Calculate the total bill amount for an order (async version).
    
    Args:
        order_items: List of order items with modifiers
        
    Returns:
        Total bill amount
    """
    total = 0.0
    
    for item in order_items:
        # Get item price and quantity
        item_price = float(item.get("price", 0))
        quantity = int(item.get("quantity", 1))
        
        # Add item price
        total += item_price * quantity
        
        # Add modifier prices
        if "modifiers" in item and item["modifiers"]:
            for modifier in item["modifiers"]:
                modifier_price = float(modifier.get("price_change", 0))
                modifier_quantity = int(modifier.get("quantity", 1))
                
                # Add modifier price
                total += modifier_price * modifier_quantity * quantity
    
    return round(total, 2)


async def mark_unavailable_items_async(
    db: AsyncSession,
    order_items: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Mark unavailable items in an order and return a list of unavailable items (async version).
    
    Args:
        db: AsyncSession for database access
        order_items: List of order items to check
        
    Returns:
        Tuple of (updated_order_items, unavailable_item_names)
    """
    # Load the full menu data
    menu_data = await load_menu_data(db)
    
    # List to store unavailable items
    unavailable_items = []
    updated_items = []
    
    for item in order_items:
        # Get the menu item data
        plu = item.get("plu")
        name = item.get("name")
        
        # Skip if no PLU (shouldn't happen in normal flow)
        if not plu:
            logger.warning(f"Item missing PLU: {name}")
            updated_items.append(item)
            continue
        
        # Find the menu item by PLU
        menu_item = None
        for menu_item_data in menu_data.get("items", []):
            if menu_item_data.get("plu") == plu:
                menu_item = menu_item_data
                break
        
        # Check if item is available
        if not menu_item or not is_item_available(menu_item):
            unavailable_items.append(name)
            item["available"] = False
        else:
            item["available"] = True
        
        # Check modifiers if any
        if "modifiers" in item and item["modifiers"]:
            unavailable_modifiers = []
            
            for modifier in item["modifiers"]:
                modifier_plu = modifier.get("plu")
                modifier_name = modifier.get("name")
                
                # Skip if no PLU
                if not modifier_plu:
                    continue
                
                # Find the modifier
                menu_modifier = None
                for mod_data in menu_data.get("modifiers", []):
                    if mod_data.get("plu") == modifier_plu:
                        menu_modifier = mod_data
                        break
                
                # Check if modifier is available
                if not menu_modifier or not is_item_available(menu_modifier):
                    unavailable_modifiers.append(modifier_name)
                    modifier["available"] = False
                else:
                    modifier["available"] = True
            
            # If any modifiers are unavailable, mark the whole item
            if unavailable_modifiers:
                modifier_list = ", ".join(unavailable_modifiers)
                unavailable_items.append(f"{name} with {modifier_list}")
                item["available"] = False
        
        updated_items.append(item)
    
    return updated_items, unavailable_items


async def validate_modifiers_async(
    db: AsyncSession,
    order_items: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Validate that all modifiers in an order meet group constraints (async version).
    
    Args:
        db: AsyncSession for database access
        order_items: List of order items to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    # Load the full menu data
    menu_data = await load_menu_data(db)
    
    # List to store validation errors
    errors = []
    
    # For each item in the order
    for item in order_items:
        item_name = item.get("name", "Unknown item")
        plu = item.get("plu")
        
        # Skip if no PLU
        if not plu:
            continue
        
        # Find the menu item
        menu_item = None
        for mi in menu_data.get("items", []):
            if mi.get("plu") == plu:
                menu_item = mi
                break
        
        if not menu_item:
            continue
        
        # Get all modifier groups for this item
        item_groups = []
        for group in menu_data.get("modifier_groups", []):
            # Check if this group is associated with this item
            if "subProducts" in group and menu_item.get("reference_handler") in group.get("subProducts", []):
                item_groups.append(group)
        
        # Track modifiers by group
        modifiers_by_group = {}
        
        # Analyze modifiers in the order
        for modifier in item.get("modifiers", []):
            mod_plu = modifier.get("plu")
            mod_name = modifier.get("name", "Unknown modifier")
            
            # Find the modifier
            menu_modifier = None
            for mm in menu_data.get("modifiers", []):
                if mm.get("plu") == mod_plu:
                    menu_modifier = mm
                    break
            
            if not menu_modifier:
                continue
            
            # Find which group this modifier belongs to
            for group in item_groups:
                if menu_modifier.get("reference_handler") in group.get("subProducts", []):
                    # Initialize group tracking if not exists
                    group_id = group.get("id")
                    if group_id not in modifiers_by_group:
                        modifiers_by_group[group_id] = {
                            "group": group,
                            "modifiers": [],
                            "count": 0
                        }
                    
                    # Add modifier to the group
                    modifiers_by_group[group_id]["modifiers"].append(modifier)
                    modifiers_by_group[group_id]["count"] += modifier.get("quantity", 1)
        
        # Validate each group's constraints
        for group_id, group_data in modifiers_by_group.items():
            group = group_data["group"]
            count = group_data["count"]
            
            # Check minimum selections
            min_required = group.get("min", 0)
            if count < min_required:
                errors.append(f"Item '{item_name}' requires at least {min_required} selection(s) from '{group.get('name')}'")
            
            # Check maximum selections
            max_allowed = group.get("max")
            if max_allowed is not None and count > max_allowed:
                errors.append(f"Item '{item_name}' allows maximum {max_allowed} selection(s) from '{group.get('name')}'")
        
        # Check for required groups that have no selections
        for group in item_groups:
            group_id = group.get("id")
            min_required = group.get("min", 0)
            
            if min_required > 0 and group_id not in modifiers_by_group:
                errors.append(f"Item '{item_name}' requires at least {min_required} selection(s) from '{group.get('name')}'")
    
    # Return validation result
    is_valid = len(errors) == 0
    return is_valid, errors


async def create_order_with_validation(
    db: AsyncSession,
    call_sid: str,
    order_data: Dict[str, Any]
) -> Tuple[Optional[Any], List[str]]:
    """
    Create an order with validation.
    
    Args:
        db: Database session
        call_sid: Call session ID
        order_data: Order data including items, customer info, etc.
        
    Returns:
        Tuple of (order_object, validation_errors)
    """
    from app.db.crud_order_async import create_order
    from app.models.order_async import Order
    
    validation_errors = []
    
    # Validate required fields
    if not order_data.get("items"):
        validation_errors.append("Order must contain at least one item")
        return None, validation_errors
    
    if not order_data.get("customer_name"):
        validation_errors.append("Customer name is required")
    
    if not order_data.get("customer_phone"):
        validation_errors.append("Customer phone is required")
    
    # Validate items availability
    updated_items, unavailable = await mark_unavailable_items_async(db, order_data["items"])
    if unavailable:
        validation_errors.extend([f"{item} is not available" for item in unavailable])
    
    # Validate modifiers
    is_valid, modifier_errors = await validate_modifiers_async(db, order_data["items"])
    validation_errors.extend(modifier_errors)
    
    # If validation errors, return them
    if validation_errors:
        return None, validation_errors
    
    # Calculate total
    total_amount = await calculate_bill_amount_async(order_data["items"])
    
    # Create order
    try:
        order = await create_order(
            db=db,
            customer_name=order_data["customer_name"],
            customer_phone=order_data["customer_phone"],
            order_type=order_data.get("order_type", "pickup"),
            delivery_address=order_data.get("delivery_address"),
            items=order_data["items"],
            total_price=int(total_amount * 100),  # Convert to cents
            metadata={"call_sid": call_sid}
        )
        
        return order, []
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        validation_errors.append(f"Failed to create order: {str(e)}")
        return None, validation_errors