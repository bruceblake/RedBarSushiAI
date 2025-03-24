# app/utils/menu_utils.py
import json
import os
import time
import datetime
import logging
from flask import current_app, session
from app.config import MENU_FILE_PATH
from app.utils.helpers import get_common_prices, generate_consistent_reference_id

MENU_CACHE_DURATION = 10

logger = logging.getLogger(__name__)
_last_load_time = 0
_cached_data = None
_validation_in_progress = False  # Flag to prevent recursion


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


def load_menu_data(force_refresh=False, location_id=None, skip_validation=False):
    """
    Load menu data from file or cache. Handles both test and production environments.
    
    Args:
        force_refresh: Force a reload from disk instead of using cache
        location_id: Optional location ID to load location-specific menu
        skip_validation: Skip menu validation to prevent recursion
        
    Returns:
        dict: Menu data structure
    """
    global _last_load_time, _cached_data, _validation_in_progress
    
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
            file_path = MENU_FILE_PATH
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
        # Check if file has been modified since we last loaded it
        file_mtime = os.path.getmtime(file_path)
        last_load_time = _last_load_time.get(cache_key, 0)
        
        # Force refresh if file has been modified
        if file_mtime > last_load_time:
            logger.info(f"Menu file {file_path} has changed, forcing refresh")
            force_refresh = True
            
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Only validate if not already in a validation process and validation is not skipped
        if not _validation_in_progress and not skip_validation:
            try:
                _validation_in_progress = True
                from app.utils.menu_validator import validate_and_fix_menu_data
                data = validate_and_fix_menu_data(data)
            finally:
                _validation_in_progress = False
            
        # ---- Comprehensive menu item validation and enrichment -----
        for i, item in enumerate(data.get("items", [])):
            # Step 1: Fix missing names - critical for functionality
            if not item.get("name"):
                # Try to get name from reference_handler if available
                ref = item.get("reference_handler", "")
                if ref:
                    item["name"] = f"Item-{ref[-8:]}"
                else:
                    item["name"] = f"Unnamed Item {i+1}"
                logger.warning(f"[MENU-FIX] Fixed missing name for item {i}: '{item.get('name')}'")
            
            # Step 2: Ensure all items have reference handlers - critical for integrations
            if not item.get("reference_handler"):
                # Generate stable reference handler from name
                from app.utils.helpers import generate_consistent_reference_id
                item["reference_handler"] = generate_consistent_reference_id(item.get("name", f"item-{i}"))
                logger.warning(f"[MENU-FIX] Generated reference_handler for '{item.get('name')}': {item['reference_handler']}")
                
            # Step 3: Ensure prices are valid numbers
            if not isinstance(item.get("price"), (int, float)) or item.get("price") is None:
                item["price"] = 0.0  # Default price
                logger.warning(f"[MENU-FIX] Fixed invalid price for '{item.get('name')}', set to {item['price']}")
        # Update each item with its availability - Check availabilities field
        for it in data.get("items", []):
            snoozed = is_item_snoozed_timebased(it)
            schedule_ok = is_item_currently_available_by_schedule(it)
            it["snoozed"] = snoozed
            it["scheduleAvailable"] = schedule_ok
            # For simplicity, consider all items available unless explicitly snoozed
            # This fixes the issue where menu items were falsely considered unavailable
            it["available"] = not snoozed
        
        # Process availability for modifiers too
        for mod in data.get("modifiers", []):
            snoozed = is_item_snoozed_timebased(mod)
            schedule_ok = is_item_currently_available_by_schedule(mod)
            mod["snoozed"] = snoozed
            mod["scheduleAvailable"] = schedule_ok
            # Same simplification for modifiers - available unless snoozed
            mod["available"] = not snoozed
            
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

def verify_and_update_menu_item(item_name, item_data, location_id=None):
    """
    Verifies and updates prices and reference IDs for a menu item.
    
    Args:
        item_name: Name of the menu item
        item_data: Dictionary containing item data (price, reference_handler, etc.)
        location_id: Optional location ID for location-specific data
        
    Returns:
        dict: Updated item data with verified price and reference_handler
    """
    # First try direct match in menu data
    menu_data = load_menu_data(location_id=location_id, skip_validation=True)
    
    updated_data = item_data.copy()
    item_name_lower = item_name.lower()
    
    # Structured, efficient menu item search logging
    menu_items = menu_data.get("items", [])
    logger.info(f"[MENU-SEARCH] Looking for '{item_name_lower}' in {len(menu_items)} items")
    
    # Only log the first few items to avoid log spam
    sample_size = min(5, len(menu_items))
    if sample_size > 0:
        sample_items = [f"'{item.get('name', 'MISSING')}' (${item.get('price', 'N/A')})" 
                       for item in menu_items[:sample_size] if item.get('name')]
        logger.info(f"[MENU-SAMPLE] First {len(sample_items)} valid items: {', '.join(sample_items)}")
    
    # Try exact name match first - skip items with missing names
    menu_item = next((item for item in menu_data.get("items", []) 
                    if item.get("name") and item.get("name", "").lower() == item_name_lower), None)
    
    # If found in menu data, use those values
    if menu_item:
        logger.info(f"[MENU-MATCH] Found exact menu match for '{item_name}'")
        
        # ALWAYS update price from menu regardless of what was provided
        menu_price = menu_item.get("price")
        if menu_price is not None:
            updated_data["price"] = menu_price
            logger.info(f"[MENU-PRICE] Using exact match price: ${menu_price}")
                
        # ALWAYS update reference handler from menu
        menu_ref = menu_item.get("reference_handler")
        if menu_ref:
            updated_data["reference_handler"] = menu_ref
            logger.info(f"[MENU-REF] Using exact match reference_handler: {menu_ref}")
        
        # Also update other important fields if present
        for field in ["id", "description", "imageUrl"]:
            if field in menu_item and menu_item[field]:
                updated_data[field] = menu_item[field]
                
        return updated_data
        
    # Try additional matching strategies in descending order of specificity
    
    # Try case-insensitive exact match
    menu_item = next((item for item in menu_data.get("items", []) 
                if item.get("name") and item.get("name", "").lower() == item_name_lower), None)
    
    if menu_item:
        logger.info(f"[MENU-MATCH] Found case-insensitive match for '{item_name}'")
        updated_data["price"] = menu_item.get("price", 7.5)
        updated_data["reference_handler"] = menu_item.get("reference_handler", "")
        return updated_data
    
    # Try matching with title case
    capitalized_name = item_name.title()
    menu_item = next((item for item in menu_data.get("items", []) 
                if item.get("name") and item.get("name", "") == capitalized_name), None)
    
    if menu_item:
        logger.info(f"[MENU-MATCH] Found capitalized match: '{item_name}' -> '{capitalized_name}'")
        updated_data["price"] = menu_item.get("price", 7.5)
        updated_data["reference_handler"] = menu_item.get("reference_handler", "")
        return updated_data
    
    # Try Levenshtein distance-based matching for close matches
    import Levenshtein
    best_item = None
    best_score = 0.4  # Minimum similarity threshold (0-1)
    
    for item in menu_data.get("items", []):
        if not item.get("name"):
            continue
            
        menu_item_name = item.get("name", "").lower()
        item_len = max(len(item_name_lower), len(menu_item_name))
        if item_len == 0:
            continue
            
        # Calculate normalized similarity score (0-1)
        distance = Levenshtein.distance(item_name_lower, menu_item_name)
        similarity = 1.0 - (distance / item_len)
        
        if similarity > best_score:
            best_score = similarity
            best_item = item
    
    if best_item:
        logger.info(f"[MENU-MATCH] Found fuzzy match: '{item_name}' -> '{best_item.get('name')}' (similarity: {best_score:.2f})")
        updated_data["price"] = best_item.get("price", 7.5)
        updated_data["reference_handler"] = best_item.get("reference_handler", "")
        return updated_data
    
    # Try substring matching
    potential_items = [item for item in menu_data.get("items", []) 
                     if item.get("name") and (
                         item_name_lower in item.get("name", "").lower() or 
                         item.get("name", "").lower() in item_name_lower)]
    
    if potential_items:
        # Sort matches by length of name for better matches
        potential_items.sort(key=lambda x: -len(x.get("name", "")))
        best_match = potential_items[0]
        
        logger.info(f"[MENU-MATCH] Found substring match: '{item_name}' -> '{best_match.get('name')}'")
        updated_data["price"] = best_match.get("price")
        updated_data["reference_handler"] = best_match.get("reference_handler", "")
        return updated_data
    
    # Last resort: use smart fallback system
    logger.info(f"[MENU-FALLBACK] No menu match found for '{item_name}', using fallback system")
    return apply_fallback_pricing(item_name, updated_data)

def apply_fallback_pricing(item_name, item_data):
    """
    Smart fallback pricing system for items not found in the menu.
    Uses a hierarchical matching approach:
    1. Exact match by name
    2. Contains match (item name contains key or key contains item name)
    3. Word-level matching
    4. Default fallback values
    
    Args:
        item_name: Name of the menu item
        item_data: Current item data
        
    Returns:
        dict: Updated item data with best available price and reference
    """
    # Load common prices from a managed dictionary
    common_prices = get_common_prices()
    
    updated_data = item_data.copy()
    item_lower = item_name.lower()
    
    logger.info(f"[MENU-FALLBACK] Searching fallback prices for '{item_lower}'")
    
    # Log a few sample entries for context
    sample_entries = list(common_prices.items())[:3]
    sample_str = ", ".join([f"'{k}' (${v.get('price')})" for k, v in sample_entries])
    logger.info(f"[MENU-FALLBACK] Sample entries: {sample_str}")
    
    # Step 1: Try exact match first (highest priority)
    if item_lower in common_prices:
        price_info = common_prices[item_lower]
        logger.info(f"[MENU-MATCH] Exact match: '{item_lower}' = ${price_info.get('price')}")
        updated_data["price"] = price_info.get("price", 7.5)
        updated_data["reference_handler"] = price_info.get("reference_handler", "")
        return updated_data
    
    # Step 2: Try contains match 
    best_match = None
    best_match_len = 0
    
    for key, price_info in common_prices.items():
        # Skip very short keys to avoid false matches
        if len(key) < 4:
            continue
            
        # If the item name contains this key (e.g., "cheeseburger" contains "burger")
        if key in item_lower and len(key) > best_match_len:
            best_match = (key, price_info)
            best_match_len = len(key)
            
        # Or if the key contains the item name (e.g., "veggie burger" contains "burger")
        elif item_lower in key and "full_name" in price_info and len(item_lower) > best_match_len:
            best_match = (key, price_info)
            best_match_len = len(item_lower)
    
    if best_match:
        key, price_info = best_match
        orig_name = price_info.get("full_name", key)
        logger.info(f"[MENU-MATCH] Partial match: '{item_lower}' matches '{orig_name}' (${price_info.get('price')})")
        updated_data["price"] = price_info.get("price", 7.5)
        updated_data["reference_handler"] = price_info.get("reference_handler", "")
        return updated_data
    
    # Step 3: Try word-level matching for compound names
    words = item_lower.split()
    for word in words:
        if len(word) > 3 and word in common_prices:
            price_info = common_prices[word]
            logger.info(f"[MENU-MATCH] Word match: '{word}' in '{item_lower}' matches '{price_info.get('full_name', word)}' (${price_info.get('price')})")
            updated_data["price"] = price_info.get("price", 7.5)
            updated_data["reference_handler"] = price_info.get("reference_handler", "")
            return updated_data
    
    # Step 4: No match found, use default values
    category_defaults = {
        "burger": {"price": 8.0, "prefix": "BRG"},
        "fries": {"price": 2.0, "prefix": "FRY"},
        "pizza": {"price": 8.0, "prefix": "PIZ"},
        "salad": {"price": 6.0, "prefix": "SLD"},
        "drink": {"price": 4.0, "prefix": "DRK"},
        "soda": {"price": 4.0, "prefix": "DRK"},
        "cola": {"price": 4.0, "prefix": "DRK"},
    }
    
    # Try to categorize the item for a better default price
    for category, defaults in category_defaults.items():
        if category in item_lower:
            logger.info(f"[MENU-DEFAULT] Categorized '{item_lower}' as {category.upper()}")
            updated_data["price"] = defaults["price"]
            updated_data["reference_handler"] = f"{defaults['prefix']}-{generate_consistent_reference_id(item_name)[-6:]}"
            return updated_data
    
    # Last resort: completely generic default
    updated_data["price"] = 7.5  # Default price
    logger.info(f"[MENU-DEFAULT] Using generic default price for '{item_name}': $7.5")
    
    # Generate a consistent reference handler based on the item name
    updated_data["reference_handler"] = generate_consistent_reference_id(item_name)
    
    return updated_data


def process_deliverect_menu(deliverect_menu, location_id=None):
    """
    Efficiently converts Deliverect menu format to our internal format,
    preserving all PLUs/reference_handlers exactly as provided by Deliverect.
    
    Handles menu transitions when items are replaced or modified by:
    1. Tracking all current and new items by ID and name
    2. Preserving existing reference handlers for consistent ordering
    3. Maintaining a transition mapping for replaced items
    
    Args:
        deliverect_menu: The menu data from Deliverect
        location_id: Optional location ID for location-specific settings
        
    Returns:
        dict: Processed menu in our format
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Load existing menu to handle transitions
    try:
        existing_menu = load_menu_data(force_refresh=True, skip_validation=True)
        
        # Create mappings for existing items
        existing_by_id = {item.get("id", ""): item for item in existing_menu.get("items", []) if item.get("id")}
        existing_by_name = {item.get("name", "").lower(): item for item in existing_menu.get("items", []) if item.get("name")}
        existing_by_plu = {item.get("reference_handler", ""): item for item in existing_menu.get("items", []) if item.get("reference_handler")}
        
        logger.info(f"[MENU-TRANSITION] Found {len(existing_by_id)} items by ID, {len(existing_by_name)} by name, {len(existing_by_plu)} by PLU")
    except Exception as e:
        logger.warning(f"[MENU-TRANSITION] Could not load existing menu: {e}")
        existing_by_id = {}
        existing_by_name = {}
        existing_by_plu = {}
    
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Track processed IDs to avoid duplicates
    processed_item_ids = set()
    processed_modifier_group_ids = set()
    
    # Create a master PLU mapping (id -> reference_handler) to maintain consistency
    plu_map = {}
    
    # Track menu transitions for reporting
    transition_map = {
        "new_items": [],
        "updated_items": [],
        "removed_items": [],
        "plu_changes": []
    }
    
    # Process categories and products
    categories = deliverect_menu.get("categories", [])
    logger.info(f"[DELIVERECT] Processing {len(categories)} categories")
    
    # Initial pass - collect all incoming items
    all_incoming_items = []
    incoming_ids = set()
    for category in categories:
        for product in category.get("products", []):
            all_incoming_items.append(product)
            incoming_ids.add(product.get("id", ""))
    
    # Check for removed items
    for existing_id, existing_item in existing_by_id.items():
        if existing_id and existing_id not in incoming_ids:
            name = existing_item.get("name", "Unknown")
            plu = existing_item.get("reference_handler", "")
            transition_map["removed_items"].append({"id": existing_id, "name": name, "plu": plu})
            logger.info(f"[MENU-TRANSITION] Item removed: '{name}' (ID: {existing_id}, PLU: {plu})")
    
    # Process all products
    for category in categories:
        cat_id = category.get("id")
        cat_name = category.get("name")
        products = category.get("products", [])
        
        for product in products:
            prod_id = product.get("id")
            prod_name = product.get("name", "")
            
            # Skip duplicates
            if prod_id in processed_item_ids:
                continue
                
            processed_item_ids.add(prod_id)
            
            # IMPORTANT: Always preserve the exact PLU/reference_handler from Deliverect
            plu = product.get("plu", "")
            if plu:
                plu_map[prod_id] = plu
                
            # Create menu item entry with complete data
            prod = {
                "id": prod_id,
                "name": prod_name,
                "price": product.get("price", 0) / 100,  # Convert from cents
                "reference_handler": plu,  # Use exact PLU as provided
                "description": product.get("description", ""),
                "imageUrl": product.get("imageUrl", ""),
                "snoozed": not product.get("available", True),  # Convert to our snoozed paradigm
                "category": cat_name,
                "categoryId": cat_id
            }
            
            # Handle menu transitions - check if this is a new or updated item
            is_new = True
            if prod_id in existing_by_id:
                is_new = False
                # Item exists by ID - track changes for transition
                old_item = existing_by_id[prod_id]
                old_name = old_item.get("name", "")
                old_plu = old_item.get("reference_handler", "")
                
                # Check for key differences
                if old_name != prod_name:
                    logger.info(f"[MENU-TRANSITION] Item name changed: '{old_name}' → '{prod_name}' (ID: {prod_id})")
                    
                if old_plu != plu and old_plu and plu:
                    logger.info(f"[MENU-TRANSITION] PLU changed: '{old_plu}' → '{plu}' for '{prod_name}'")
                    transition_map["plu_changes"].append({
                        "id": prod_id,
                        "name": prod_name,
                        "old_plu": old_plu,
                        "new_plu": plu
                    })
                
                transition_map["updated_items"].append({
                    "id": prod_id,
                    "name": prod_name,
                    "old_name": old_name,
                    "plu": plu
                })
            else:
                # New item - log for transition tracking
                transition_map["new_items"].append({
                    "id": prod_id,
                    "name": prod_name,
                    "plu": plu
                })
                logger.info(f"[MENU-TRANSITION] New item: '{prod_name}' (ID: {prod_id}, PLU: {plu})")
            
            # Process location-specific PLUs (override if specified for this location)
            if location_id:
                for location in product.get("locations", []):
                    if location.get("id") == location_id and location.get("plu"):
                        prod["reference_handler"] = location.get("plu")
                        plu_map[prod_id] = location.get("plu")
                        prod["price"] = location.get("price", prod["price"]) / 100
                        break
            
            # Process availabilities
            if "availability" in product:
                prod["availabilities"] = convert_availability(product.get("availability", []))
                
            # Process modifier groups (simplify reference)
            mod_groups = []
            for group in product.get("modifierGroups", []):
                group_id = group.get("id")
                mod_groups.append(group_id)
                
                # Only process each modifier group once
                if group_id not in processed_modifier_group_ids:
                    processed_modifier_group_ids.add(group_id)
                    
                    # Create the modifier group record
                    new_group = {
                        "id": group_id,
                        "name": group.get("name"),
                        "min": group.get("minAmount", 0),
                        "max": group.get("maxAmount", 999),
                        "modifiers": []
                    }
                    
                    # Process modifiers in this group
                    for modifier in group.get("modifiers", []):
                        mod_id = modifier.get("id")
                        mod_name = modifier.get("name", "")
                        mod_plu = modifier.get("plu", "")
                        
                        # Store in PLU map
                        if mod_plu:
                            plu_map[mod_id] = mod_plu
                            
                        new_group["modifiers"].append({
                            "id": mod_id,
                            "name": mod_name,
                            "price": modifier.get("price", 0) / 100,
                            "snoozed": not modifier.get("available", True),
                            "reference_handler": mod_plu
                        })
                    
                    result["modifierGroups"].append(new_group)
            
            # Add modifier groups to product
            if mod_groups:
                prod["modifierGroups"] = mod_groups
                
            result["items"].append(prod)
    
    # Log transition summary
    logger.info(f"[MENU-TRANSITION] Summary: {len(transition_map['new_items'])} new items, " +
                f"{len(transition_map['updated_items'])} updated items, " +
                f"{len(transition_map['removed_items'])} removed items, " +
                f"{len(transition_map['plu_changes'])} PLU changes")
    
    # Create a quick lookup for item names -> reference_handlers for future use
    plu_reference = {}
    for item in result["items"]:
        name = item.get("name", "")
        ref = item.get("reference_handler", "")
        if name and ref:
            plu_reference[name.lower()] = ref
            
    # Log a sample of PLU mappings
    sample_items = list(plu_reference.items())[:5]
    for name, ref in sample_items:
        logger.info(f"[DELIVERECT-PLU] '{name}' = '{ref}'")
    
    logger.info(f"[DELIVERECT] Processed: {len(result['items'])} items, {len(result['modifierGroups'])} modifier groups")
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
    Process changes to a product from Deliverect, ensuring exact PLU preservation.
    
    Args:
        product_id: The ID of the product to update
        changes: Dictionary of changes from Deliverect
        location_id: Optional location ID for location-specific menu
        
    Returns:
        bool: Success status
    """
    logger = logging.getLogger(__name__)
    logger.info(f"[DELIVERECT-UPDATE] Processing changes for product {product_id}")
    
    # Load current menu
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Find the product
    for item in menu_data.get("items", []):
        if item.get("id") == product_id:
            # Track what's changing
            changed_fields = []
            
            # Apply changes - ALWAYS preserve exact PLU / reference_handler from Deliverect
            for key, value in changes.items():
                # Handle special cases
                if key == "price":
                    item[key] = value / 100  # Convert from cents
                    changed_fields.append(f"price: {value/100}")
                elif key == "plu" and value:
                    # CRITICAL: Always use exact PLU from Deliverect
                    item["reference_handler"] = value
                    changed_fields.append(f"reference_handler: {value}")
                elif key == "available":
                    # Map to our snoozed paradigm
                    item["snoozed"] = not value
                    changed_fields.append(f"snoozed: {not value}")
                    
                    # Update snooze timestamps appropriately
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if not value:  # Making unavailable
                        item["snoozeStart"] = now.isoformat()
                        item["snoozeEnd"] = (now + datetime.timedelta(hours=24)).isoformat()
                    else:  # Making available
                        if "snoozeStart" in item:
                            del item["snoozeStart"]
                        if "snoozeEnd" in item:
                            del item["snoozeEnd"]
                # Standard field updates
                elif key in ["name", "description", "imageUrl", "sequence"]:
                    item[key] = value
                    changed_fields.append(f"{key}: {value}")
            
            # Log the changes in a structured way
            if changed_fields:
                logger.info(f"[DELIVERECT-UPDATE] Updated '{item.get('name')}' ({product_id}): {', '.join(changed_fields)}")
                
                # Save updated menu
                write_menu_file(menu_data)
                return True
            else:
                logger.info(f"[DELIVERECT-UPDATE] No changes applied to '{item.get('name')}' ({product_id})")
                return True
            
    logger.warning(f"[DELIVERECT-UPDATE] Product {product_id} not found in menu")
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
    logger = logging.getLogger(__name__)
    logger.info(f"[DELIVERECT-UPDATE] Processing changes for modifier group {group_id}")
    
    # Load current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Find the modifier group
    for group in menu_data.get("modifierGroups", []):
        if group.get("id") == group_id:
            # Track changes
            changed_fields = []
            
            # Apply changes
            for key, value in changes.items():
                if key == "name":
                    group[key] = value
                    changed_fields.append(f"name: {value}")
                elif key == "minAmount":
                    group["min"] = value  # Use shorter keys for consistency
                    changed_fields.append(f"min: {value}")
                elif key == "maxAmount":
                    group["max"] = value  # Use shorter keys for consistency
                    changed_fields.append(f"max: {value}")
                elif key == "sequence":
                    group["sequence"] = value
                    changed_fields.append(f"sequence: {value}")
                    
            # Log changes
            if changed_fields:
                logger.info(f"[DELIVERECT-UPDATE] Updated modifier group '{group.get('name')}' ({group_id}): {', '.join(changed_fields)}")
                
                # Save updated menu
                write_menu_file(menu_data)
                return True
            else:
                logger.info(f"[DELIVERECT-UPDATE] No changes applied to modifier group '{group.get('name')}' ({group_id})")
                return True
            
    logger.warning(f"[DELIVERECT-UPDATE] Modifier group {group_id} not found in menu")
    return False


def process_modifier_changes(modifier_id, changes):
    """
    Process changes to a modifier from Deliverect, ensuring exact PLU preservation.
    
    Args:
        modifier_id: The ID of the modifier to update
        changes: Dictionary of changes from Deliverect
        
    Returns:
        bool: Success status
    """
    logger = logging.getLogger(__name__)
    logger.info(f"[DELIVERECT-UPDATE] Processing changes for modifier {modifier_id}")
    
    # Load current menu
    menu_data = load_menu_data(force_refresh=True)
    
    # Search through all modifier groups
    for group in menu_data.get("modifierGroups", []):
        for modifier in group.get("modifiers", []):
            if modifier.get("id") == modifier_id:
                # Track changes
                changed_fields = []
                
                # Apply changes - ALWAYS preserve exact PLU / reference_handler
                for key, value in changes.items():
                    if key == "name":
                        modifier[key] = value
                        changed_fields.append(f"name: {value}")
                    elif key == "price":
                        modifier[key] = value / 100  # Convert from cents
                        changed_fields.append(f"price: {value/100}")
                    elif key == "plu" and value:
                        # CRITICAL: Always use exact PLU from Deliverect
                        modifier["reference_handler"] = value
                        changed_fields.append(f"reference_handler: {value}")
                    elif key == "sequence":
                        modifier["sequence"] = value
                        changed_fields.append(f"sequence: {value}")
                    elif key == "available":
                        # Map to our snoozed paradigm
                        modifier["snoozed"] = not value
                        changed_fields.append(f"snoozed: {not value}")
                        
                        # Update snooze timestamps
                        now = datetime.datetime.now(datetime.timezone.utc)
                        if not value:  # Making unavailable
                            modifier["snoozeStart"] = now.isoformat()
                            modifier["snoozeEnd"] = (now + datetime.timedelta(hours=24)).isoformat()
                        else:  # Making available
                            if "snoozeStart" in modifier:
                                del modifier["snoozeStart"]
                            if "snoozeEnd" in modifier:
                                del modifier["snoozeEnd"]
                
                # Log changes
                if changed_fields:
                    logger.info(f"[DELIVERECT-UPDATE] Updated modifier '{modifier.get('name')}' ({modifier_id}): {', '.join(changed_fields)}")
                    
                    # Save updated menu
                    write_menu_file(menu_data)
                    return True
                else:
                    logger.info(f"[DELIVERECT-UPDATE] No changes applied to modifier '{modifier.get('name')}' ({modifier_id})")
                    return True
            
    logger.warning(f"[DELIVERECT-UPDATE] Modifier {modifier_id} not found in menu")
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

def sync_reference_handlers(source_location_id=None, target_location_id=None):
    """
    Synchronizes reference handlers between different menu sources.
    This ensures consistency across different menu versions.
    
    Args:
        source_location_id: Optional location ID to use as reference source
        target_location_id: Optional location ID to update
        
    Returns:
        dict: Stats about the synchronization
    """
    # Load source menu with validation skipped to avoid recursion
    source_menu = load_menu_data(location_id=source_location_id, force_refresh=True, skip_validation=True)
    source_items = {item.get("name", "").lower(): item for item in source_menu.get("items", [])}
    
    # If target is specified, load it, otherwise update the same menu
    if target_location_id and target_location_id != source_location_id:
        target_menu = load_menu_data(location_id=target_location_id, force_refresh=True, skip_validation=True)
        save_target = True
    else:
        target_menu = source_menu
        save_target = False
    
    # Track stats
    stats = {
        "items_checked": 0,
        "references_updated": 0,
        "prices_updated": 0,
        "modifiers_checked": 0,
        "modifier_references_updated": 0
    }
    
    # Check for missing reference handlers in all items
    for item in target_menu.get("items", []):
        stats["items_checked"] += 1
        item_name = item.get("name", "").lower()
        
        # Skip if it already has a valid reference handler
        if item.get("reference_handler"):
            continue
            
        # Check if it exists in source menu
        if item_name in source_items and source_items[item_name].get("reference_handler"):
            item["reference_handler"] = source_items[item_name]["reference_handler"]
            stats["references_updated"] += 1
            logger.info(f"Updated reference handler for {item.get('name')} to {item['reference_handler']}")
    
    # Save the target menu if needed
    if save_target and (stats["references_updated"] > 0 or stats["prices_updated"] > 0):
        write_menu_file(target_menu)
        load_menu_data(location_id=target_location_id, force_refresh=True, skip_validation=True)
        
    return stats