# app/utils/menu_utils.py
import json
import os
import time
import datetime
import logging
from flask import current_app, session
from app.config import MENU_FILE_PATH

MENU_CACHE_DURATION = 10

logger = logging.getLogger(__name__)
_last_load_time = 0
_cached_data = None


def write_menu_file(all_items_data):
    """
    Write menu data to file. In test environment, uses the file path from app config.
    In production, uses the path from module-level config.
    """
    try:
        # Try to get file path from current app context for tests
        try:
            file_path = current_app.config.get('MENU_FILE_PATH', MENU_FILE_PATH)
        except:
            # If not in app context, fall back to module config
            file_path = MENU_FILE_PATH
            
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        with open(file_path, "w") as f:
            json.dump(all_items_data, f)
        logger.info(f"Menu data written to {file_path}.")
    except Exception as e:
        logger.error(f"Error writing menu data file: {e}")


def parse_utc_timestamp(ts_str):
    if not ts_str:
        return None
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1]
    try:
        return datetime.datetime.fromisoformat(ts_str).replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def is_item_snoozed_timebased(item_obj):
    s_start_str = item_obj.get("snoozeStart")
    s_end_str = item_obj.get("snoozeEnd")
    if not s_start_str or not s_end_str:
        return False
    start = parse_utc_timestamp(s_start_str)
    end = parse_utc_timestamp(s_end_str)
    if not (start and end):
        return False
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return (start <= now_utc <= end)


def is_item_currently_available_by_schedule(item_obj):
    all_blocks = item_obj.get("availabilities", [])
    if not all_blocks:
        return True
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    day_of_week = now_utc.isoweekday()
    now_time = now_utc.time()
    found_match = False
    for block in all_blocks:
        block_dow = block.get("dayOfWeek")
        start_str = block.get("startTime", "00:00")
        end_str = block.get("endTime", "23:59")
        if block_dow != day_of_week:
            continue
        try:
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
        except Exception as e:
            logger.error(f"Error parsing block time: {e}")
            continue
        start_t = datetime.time(hour=start_hour, minute=start_min)
        end_t = datetime.time(hour=end_hour, minute=end_min)
        if start_t <= now_time <= end_t:
            found_match = True
            break
    if not found_match:
        logger.info("No matching day/time => item is unavailable right now.")
    return found_match


def load_menu_data(force_refresh=False, location_id=None):
    """
    Load menu data from file or cache. Handles both test and production environments.
    
    Args:
        force_refresh: Force a reload from disk instead of using cache
        location_id: Optional location ID to load location-specific menu
        
    Returns:
        dict: Menu data structure
    """
    global _last_load_time, _cached_data
    
    # Try to get location from session if not provided
    if not location_id:
        try:
            location_id = session.get('location_id')
        except RuntimeError:
            # Not in request context
            pass
    
    # If location-specific, generate a cache key
    cache_key = f"menu_{location_id}" if location_id else "menu_default"
    
    # Initialize cache dict if needed
    if _cached_data is None:
        _cached_data = {}
        
    if force_refresh and cache_key in _cached_data:
        del _cached_data[cache_key]
        
    # Check if data is in cache and not expired
    if isinstance(_last_load_time, dict) and cache_key in _cached_data and cache_key in _last_load_time:
        if time.time() - _last_load_time[cache_key] < MENU_CACHE_DURATION:
            return _cached_data[cache_key]
    
    # Initialize timestamps dict if needed
    if not isinstance(_last_load_time, dict):
        _last_load_time = {}
    
    # Try to get file path from current app context for tests
    try:
        if location_id:
            # Location-specific menu file
            base_path = current_app.config.get('MENU_FILE_PATH', MENU_FILE_PATH)
            directory = os.path.dirname(base_path)
            filename = os.path.basename(base_path)
            file_path = os.path.join(directory, f"{location_id}_{filename}")
        else:
            file_path = current_app.config.get('MENU_FILE_PATH', MENU_FILE_PATH)
    except:
        # If not in app context, fall back to module config
        if location_id:
            directory = os.path.dirname(MENU_FILE_PATH)
            filename = os.path.basename(MENU_FILE_PATH)
            file_path = os.path.join(directory, f"{location_id}_{filename}")
        else:
            file_path = MENU_FILE_PATH
    
    if not os.path.exists(file_path):
        logger.info(f"No menu file found at {file_path}, returning empty.")
        empty_data = {"items": [], "modifiers": [], "modifierGroups": []}
        _cached_data[cache_key] = empty_data
        _last_load_time[cache_key] = time.time()
        return empty_data
        
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        # Update each item with its availability
        for it in data.get("items", []):
            snoozed = is_item_snoozed_timebased(it)
            schedule_ok = is_item_currently_available_by_schedule(it)
            it["snoozed"] = snoozed
            it["scheduleAvailable"] = schedule_ok
            it["available"] = (not snoozed) and schedule_ok
        
        # Process availability for modifiers too
        for mod in data.get("modifiers", []):
            snoozed = is_item_snoozed_timebased(mod)
            schedule_ok = is_item_currently_available_by_schedule(mod)
            mod["snoozed"] = snoozed
            mod["scheduleAvailable"] = schedule_ok
            mod["available"] = (not snoozed) and schedule_ok
            
        _cached_data[cache_key] = data
        _last_load_time[cache_key] = time.time()
        return data
    except Exception as e:
        logger.error(f"Error reading menu data file: {e}")
        empty_data = {"items": [], "modifiers": [], "modifierGroups": []}
        _cached_data[cache_key] = empty_data
        _last_load_time[cache_key] = time.time()
        return empty_data


def validate_modifier_constraints(order_items):
    """
    Validates that each item with modifier groups meets min/max constraints.
    
    Args:
        order_items: List of order items with their modifiers
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Load menu data to get modifier group constraints
    menu_data = load_menu_data()
    
    for item in order_items:
        item_name = item.get("name", "")
        # Find the menu item definition
        menu_item = next((i for i in menu_data.get("items", []) if i.get("name") == item_name), None)
        if not menu_item:
            continue
            
        # Get modifier groups for this item
        mod_group_ids = menu_item.get("modifierGroups", [])
        selected_mods = item.get("modifier", [])
        
        # Check each modifier group
        for group_id in mod_group_ids:
            group = next((g for g in menu_data.get("modifierGroups", []) if g.get("id") == group_id), None)
            if not group:
                continue
                
            min_allowed = group.get("minAllowed", 0)
            max_allowed = group.get("maxAllowed", 999)
            
            # Count modifiers from this group
            group_mod_ids = [m.get("id") for m in group.get("modifiers", [])]
            group_mod_names = [m.get("name").lower() for m in group.get("modifiers", [])]
            
            # Match modifiers by ID or name
            selected_from_group = []
            for mod in selected_mods:
                mod_id = mod.get("id")
                mod_name = mod.get("name", "").lower()
                if mod_id in group_mod_ids or mod_name in group_mod_names:
                    selected_from_group.append(mod)
            
            total_qty = sum(m.get("quantity", 1) for m in selected_from_group)
            
            # Validate
            if total_qty < min_allowed:
                return False, f"Item '{item_name}' requires at least {min_allowed} selections from '{group.get('name')}'"
            if total_qty > max_allowed:
                return False, f"Item '{item_name}' allows at most {max_allowed} selections from '{group.get('name')}'"
    
    return True, ""


def process_meal_deal(meal_deal, selections):
    """
    Process a meal deal with customer selections.
    
    Args:
        meal_deal: The meal deal product
        selections: Customer selections for each component
        
    Returns:
        dict: Structured order item with all components
    """
    result = {
        "name": meal_deal.get("name"),
        "quantity": 1,
        "price": meal_deal.get("price", 0.0),
        "reference_handler": meal_deal.get("reference_handler", ""),
        "childItems": []
    }
    
    # Process each child product with its selection
    for child_product in meal_deal.get("childProducts", []):
        child_id = child_product.get("id")
        if child_id in selections:
            selection = selections[child_id]
            child_item = {
                "name": selection.get("name", child_product.get("name")),
                "quantity": 1,
                "modifier": selection.get("modifier", [])
            }
            result["childItems"].append(child_item)
    
    return result


def build_nested_modifiers(modifier, menu_data):
    """
    Recursively build nested modifiers structure.
    
    Args:
        modifier: The modifier to process
        menu_data: Complete menu data for reference
        
    Returns:
        dict: Processed modifier with nested modifiers
    """
    result = {
        "name": modifier.get("name"),
        "quantity": modifier.get("quantity", 1),
        "price": modifier.get("price", 0.0),
        "subModifiers": []
    }
    
    # Find this modifier's definition
    mod_def = next((m for m in menu_data.get("modifiers", []) if m.get("id") == modifier.get("id")), None)
    if not mod_def:
        return result
        
    # Process child modifiers
    for sub_mod in modifier.get("modifiers", []):
        result["subModifiers"].append(build_nested_modifiers(sub_mod, menu_data))
        
    return result


def process_deliverect_menu(deliverect_menu, location_id=None):
    """
    Convert Deliverect menu format to our internal format.
    
    Args:
        deliverect_menu: The menu data from Deliverect
        location_id: Optional location ID for location-specific settings
        
    Returns:
        dict: Processed menu in our format
    """
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Process categories and products
    for category in deliverect_menu.get("categories", []):
        cat_id = category.get("id")
        cat_name = category.get("name")
        cat_sequence = category.get("sequence", 0)
        
        # Process products in this category
        for product in category.get("products", []):
            prod = {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": product.get("price", 0.0) / 100,  # Convert from cents
                "reference_handler": product.get("plu", ""),
                "description": product.get("description", ""),
                "imageUrl": product.get("imageUrl", ""),
                "available": product.get("available", True),
                "category": cat_name,
                "categoryId": cat_id,
                "sequence": product.get("sequence", 0),
                "categorySequence": cat_sequence
            }
            
            # Process availability
            if "availability" in product:
                prod["availabilities"] = convert_availability(product.get("availability", []))
                
            # Process PLUs for different locations
            if location_id:
                for location in product.get("locations", []):
                    if location.get("id") == location_id:
                        prod["reference_handler"] = location.get("plu", prod["reference_handler"])
                        prod["price"] = location.get("price", prod["price"]) / 100
                        break
                    
            # Process modifier groups
            mod_groups = []
            for group in product.get("modifierGroups", []):
                mod_groups.append(group.get("id"))
                
                # Add to modifierGroups if not already there
                if not any(g.get("id") == group.get("id") for g in result["modifierGroups"]):
                    result["modifierGroups"].append({
                        "id": group.get("id"),
                        "name": group.get("name"),
                        "minAllowed": group.get("minAmount", 0),
                        "maxAllowed": group.get("maxAmount", 999),
                        "modifiers": []
                    })
                    
                    # Process modifiers in this group
                    group_index = next(i for i, g in enumerate(result["modifierGroups"]) if g.get("id") == group.get("id"))
                    for modifier in group.get("modifiers", []):
                        result["modifierGroups"][group_index]["modifiers"].append({
                            "id": modifier.get("id"),
                            "name": modifier.get("name"),
                            "price": modifier.get("price", 0.0) / 100
                        })
            
            # Process child products (meal deals)
            if "childProducts" in product:
                child_products = []
                for child in product.get("childProducts", []):
                    child_prod = {
                        "id": child.get("id"),
                        "name": child.get("name"),
                        "included": child.get("included", True),
                        "modifierGroups": child.get("modifierGroups", [])
                    }
                    child_products.append(child_prod)
                
                if child_products:
                    prod["childProducts"] = child_products
                    
            # Add modifier groups to product
            if mod_groups:
                prod["modifierGroups"] = mod_groups
                
            result["items"].append(prod)
    
    return result


def convert_availability(availability_data):
    """
    Convert Deliverect availability format to our format.
    
    Args:
        availability_data: Availability data from Deliverect
        
    Returns:
        list: Formatted availability blocks
    """
    result = []
    for day_data in availability_data:
        day = day_data.get("dayOfWeek")
        time_slots = day_data.get("timeSlots", [])
        
        for slot in time_slots:
            start_time = slot.get("startTime", "00:00")
            end_time = slot.get("endTime", "23:59")
            
            result.append({
                "dayOfWeek": day,
                "startTime": start_time,
                "endTime": end_time
            })
    
    return result


def process_product_changes(product_id, changes, location_id=None):
    """
    Process changes to a product from Deliverect.
    
    Args:
        product_id: The ID of the product to update
        changes: Dictionary of changes to apply
        location_id: Optional location ID for location-specific menu
        
    Returns:
        bool: Success status
    """
    # Load current menu
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Find the product
    for item in menu_data.get("items", []):
        if item.get("id") == product_id:
            # Apply changes
            for key, value in changes.items():
                if key == "price":
                    item[key] = value / 100  # Convert from cents
                elif key in ["name", "description", "imageUrl", "sequence"]:
                    item[key] = value
                elif key == "available":
                    item["available"] = value
                    # If making unavailable, add snooze timestamps
                    if not value:
                        now = datetime.datetime.now(datetime.timezone.utc)
                        # Snooze for the next 24 hours by default
                        item["snoozeStart"] = now.isoformat()
                        item["snoozeEnd"] = (now + datetime.timedelta(hours=24)).isoformat()
                    else:
                        # If making available, remove any snooze timestamps
                        if "snoozeStart" in item:
                            del item["snoozeStart"]
                        if "snoozeEnd" in item:
                            del item["snoozeEnd"]
            
            # Save updated menu
            write_menu_file(menu_data)
            return True
            
    return False


def process_modifier_group_changes(group_id, changes):
    """
    Process changes to a modifier group from Deliverect.
    
    Args:
        group_id: The ID of the modifier group to update
        changes: Dictionary of changes to apply
        
    Returns:
        bool: Success status
    """
    # Load current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Find the modifier group
    for group in menu_data.get("modifierGroups", []):
        if group.get("id") == group_id:
            # Apply changes
            for key, value in changes.items():
                if key == "name":
                    group[key] = value
                elif key == "minAmount":
                    group["minAllowed"] = value
                elif key == "maxAmount":
                    group["maxAllowed"] = value
                elif key == "sequence":
                    group["sequence"] = value
            
            # Save updated menu
            write_menu_file(menu_data)
            return True
            
    return False


def process_modifier_changes(modifier_id, changes):
    """
    Process changes to a modifier from Deliverect.
    
    Args:
        modifier_id: The ID of the modifier to update
        changes: Dictionary of changes to apply
        
    Returns:
        bool: Success status
    """
    # Load current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Search through all modifier groups
    for group in menu_data.get("modifierGroups", []):
        for modifier in group.get("modifiers", []):
            if modifier.get("id") == modifier_id:
                # Apply changes
                for key, value in changes.items():
                    if key == "name":
                        modifier[key] = value
                    elif key == "price":
                        modifier[key] = value / 100  # Convert from cents
                    elif key == "sequence":
                        modifier["sequence"] = value
                    elif key == "available":
                        modifier["available"] = value
                        # If making unavailable, add snooze timestamps
                        if not value:
                            now = datetime.datetime.now(datetime.timezone.utc)
                            # Snooze for the next 24 hours by default
                            modifier["snoozeStart"] = now.isoformat()
                            modifier["snoozeEnd"] = (now + datetime.timedelta(hours=24)).isoformat()
                        else:
                            # If making available, remove any snooze timestamps
                            if "snoozeStart" in modifier:
                                del modifier["snoozeStart"]
                            if "snoozeEnd" in modifier:
                                del modifier["snoozeEnd"]
                
                # Save updated menu
                write_menu_file(menu_data)
                return True
            
    return False


def update_menu_ordering(ordering_changes, location_id=None):
    """
    Update the ordering of items or categories in the menu.
    
    Args:
        ordering_changes: Dictionary with new ordering information
        location_id: Optional location ID for location-specific menu
        
    Returns:
        bool: Success status
    """
    # Load current menu
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Apply category ordering
    if "categoryOrder" in ordering_changes:
        category_order = ordering_changes["categoryOrder"]
        # Update category sequence values
        for i, cat_id in enumerate(category_order):
            # Find items in this category and update their categorySequence
            for item in menu_data.get("items", []):
                if item.get("categoryId") == cat_id:
                    item["categorySequence"] = i
        
    # Apply item ordering within categories
    if "itemOrder" in ordering_changes:
        for category_id, items in ordering_changes["itemOrder"].items():
            # Update item sequence values
            for i, item_id in enumerate(items):
                # Find this item and update its sequence
                for item in menu_data.get("items", []):
                    if item.get("id") == item_id and item.get("categoryId") == category_id:
                        item["sequence"] = i
            
    # Save updated menu
    write_menu_file(menu_data)
    return True