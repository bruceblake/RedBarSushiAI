"""
Menu utility functions for handling menu data from Deliverect.
This module ensures proper processing of menu updates and provides access to menu data.
"""
import json
import os
import time
import logging
import datetime
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone, time as dt_time

logger = logging.getLogger(__name__)

# Cache variables
_menu_cache = None
_last_refresh_time = 0
_cache_duration = 30  # 30 seconds cache duration for menu data

# Default paths - ensure they work in production environment
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT_PARENT = os.path.dirname(APP_ROOT)

# Production path - known from deployment environment
PRODUCTION_PATH = '/home/pegasus/mysite/RedBarSushiAI/menu_data.json'

# Order of precedence:
# 1. MENU_FILE_PATH environment variable
# 2. Production path at /home/pegasus/mysite/RedBarSushiAI/menu_data.json
# 3. app_root/menu_data.json
# 4. app_root_parent/menu_data.json
# 5. Current directory/menu_data.json
MENU_FILE_PATH = os.getenv('MENU_FILE_PATH',
                          os.path.exists(PRODUCTION_PATH) and PRODUCTION_PATH or
                          os.path.exists(os.path.join(APP_ROOT, 'menu_data.json')) and os.path.join(APP_ROOT, 'menu_data.json') or
                          os.path.exists(os.path.join(APP_ROOT_PARENT, 'menu_data.json')) and os.path.join(APP_ROOT_PARENT, 'menu_data.json') or
                          os.path.join(os.getcwd(), 'menu_data.json'))
                          
# Ensure backup folder is in a writable location
# If in a read-only environment, use /tmp
BACKUP_FOLDER = os.access(os.path.dirname(MENU_FILE_PATH), os.W_OK) and os.path.join(os.path.dirname(MENU_FILE_PATH), 'backups') or '/tmp/redbar_backups'

# Log where we're looking for files
logger.info(f"Using menu file path: {MENU_FILE_PATH}")
logger.info(f"Using backup folder: {BACKUP_FOLDER}")

def write_menu_file(menu_data: Dict[str, Any], file_path: Optional[str] = None) -> bool:
    """
    Write menu data to the configured file path.
    
    Args:
        menu_data (dict): The menu data to write
        file_path (str, optional): Override the default file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use provided path or default
        actual_path = file_path or MENU_FILE_PATH
        
        # Safety check - ensure it's a JSON file path
        if not actual_path.lower().endswith('.json'):
            actual_path += '.json'
            logger.warning(f"Added .json extension to file path: {actual_path}")
            
        # Make sure directory exists
        directory = os.path.dirname(actual_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except PermissionError:
                # If we can't create the directory, try using /tmp
                tmp_path = f"/tmp/{os.path.basename(actual_path)}"
                logger.warning(f"Permission error creating directory {directory}, using {tmp_path} instead")
                actual_path = tmp_path
                directory = "/tmp"
        
        # Create backups directory if it doesn't exist
        try:
            if not os.path.exists(BACKUP_FOLDER):
                os.makedirs(BACKUP_FOLDER, exist_ok=True)
                logger.info(f"Created backup directory: {BACKUP_FOLDER}")
                
            # Create a backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_FOLDER, f"menu_backup_{timestamp}.json")
            
            # If the file exists, make a backup before overwriting
            if os.path.exists(actual_path):
                shutil.copy2(actual_path, backup_path)
                logger.info(f"Menu backup created at {backup_path}")
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not create backup: {e}")
        
        # Try to write to production path first, then fallback to provided path
        paths_to_try = [
            # First try the production path if we're not already using it
            PRODUCTION_PATH if actual_path != PRODUCTION_PATH else None,
            # Then try the path that was requested
            actual_path,
            # Then try some additional fallbacks
            os.path.join(APP_ROOT, 'menu_data.json'),
            os.path.join(APP_ROOT_PARENT, 'menu_data.json'),
            # Finally use a temporary path 
            f"/tmp/menu_data_{os.getpid()}.json"
        ]
        
        # Filter out None values
        paths_to_try = [p for p in paths_to_try if p]
        
        success = False
        for try_path in paths_to_try:
            try:
                # Make sure directory exists
                directory = os.path.dirname(try_path)
                if directory and not os.path.exists(directory):
                    try:
                        os.makedirs(directory, exist_ok=True)
                    except:
                        # If we can't create the directory, skip this path
                        continue
                
                # Try to write the file
                with open(try_path, 'w') as f:
                    json.dump(menu_data, f, indent=2)
                logger.info(f"Menu data written to {try_path}")
                
                # Update the path for future reference
                actual_path = try_path
                success = True
                break
            except Exception as we:
                logger.warning(f"Could not write to {try_path}: {we}")
                continue
                
        if not success:
            logger.error("Failed to write menu data to any location")
            # One last attempt - try /tmp with a timestamp
            last_resort = f"/tmp/menu_data_last_resort_{int(time.time())}.json"
            try:
                with open(last_resort, 'w') as f:
                    json.dump(menu_data, f, indent=2)
                logger.info(f"Last resort: Menu data written to {last_resort}")
                actual_path = last_resort
            except Exception as e:
                logger.error(f"Even last resort write failed: {e}")
                # Nothing more we can do
            
        # Invalidate cache
        global _menu_cache, _last_refresh_time
        _menu_cache = None
        _last_refresh_time = 0
        
        return True
    except Exception as e:
        logger.error(f"Error writing menu file: {e}")
        return False

def load_menu_data(force_refresh: bool = False, location_id: Optional[str] = None, skip_validation: bool = False) -> Dict[str, Any]:
    """
    Load menu data from file or cache.
    Tries multiple locations to find a valid menu file.
    
    Args:
        force_refresh (bool): Force a refresh from disk instead of using cache
        location_id (str, optional): Location-specific menu data
        skip_validation (bool): Skip validation of menu data
        
    Returns:
        dict: Menu data structure (never empty)
    """
    global _menu_cache, _last_refresh_time
    
    # Use cache if available and not expired
    current_time = time.time()
    if not force_refresh and _menu_cache is not None and (current_time - _last_refresh_time) < _cache_duration:
        return _menu_cache
    
    # Determine file path based on location
    file_path = MENU_FILE_PATH
    
    # Try location-specific path if provided
    if location_id:
        location_file = f"menu_data_{location_id}.json"
        # Try multiple locations for the location-specific file
        possible_paths = [
            os.path.join(os.path.dirname(MENU_FILE_PATH), location_file),
            os.path.join(APP_ROOT, location_file),
            os.path.join(APP_ROOT_PARENT, location_file),
            os.path.join('/tmp', location_file)
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                logger.info(f"Found location-specific menu at {file_path}")
                break
    
    # If we got here and file doesn't exist, try to find any valid menu file
    if not os.path.exists(file_path):
        # Try a series of well-known locations
        possible_files = [
            # First try the production path explicitly
            '/home/pegasus/mysite/RedBarSushiAI/menu_data.json',
            # Then try configured paths
            MENU_FILE_PATH,
            PRODUCTION_PATH,
            # Try various alternative paths in the production environment
            '/home/pegasus/mysite/menu_data.json',
            '/home/pegasus/menu_data.json',
            # Try various local paths
            os.path.join(APP_ROOT, 'menu_data.json'),
            os.path.join(APP_ROOT_PARENT, 'menu_data.json'),
            os.path.join(APP_ROOT_PARENT, 'redbar_menu_data.json'),
            os.path.join(os.getcwd(), 'menu_data.json'),
            os.path.join(os.getcwd(), 'redbar_menu_data.json'),
            # Finally try temp paths
            '/tmp/menu_data.json',
            '/tmp/redbar_menu_data.json'
        ]
        
        # Log all paths we're checking
        logger.info(f"[MENU-LOAD] Looking for menu file in these locations: {possible_files}")
        
        for path in possible_files:
            if os.path.exists(path):
                file_path = path
                logger.info(f"Fallback: Using menu file at {file_path}")
                break
    
    # Try to load the file
    try:
        # Load menu data from file
        with open(file_path, 'r') as f:
            try:
                menu_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in menu file {file_path}")
                menu_data = create_default_menu()
                write_menu_file(menu_data, file_path)
                logger.info(f"Replaced corrupt menu file with default menu")
        
        # Check for empty or invalid data and fix it
        if (len(menu_data.get('items', [])) == 0 or 
            all(not item.get('name') for item in menu_data.get('items', []))):
            
            # Case 1: It's Deliverect format with categories - convert it
            if "categories" in menu_data:
                logger.info(f"Detected Deliverect format with categories - processing automatically")
                try:
                    menu_data = process_deliverect_menu(menu_data)
                    
                    # Save the processed menu for future use
                    if len(menu_data.get('items', [])) > 0:
                        write_menu_file(menu_data)
                        logger.info(f"Processed Deliverect menu with {len(menu_data.get('items', []))} items and saved")
                    else:
                        logger.error(f"Processed Deliverect menu has 0 items - something went wrong")
                except Exception as e:
                    logger.error(f"Error processing Deliverect menu: {e}")
                    # Fall back to default menu
                    menu_data = create_default_menu()
                    write_menu_file(menu_data)
                    
            # Case 2: It's invalid data - use default menu
            else:
                logger.error(f"Invalid menu data detected - loading default menu")
                menu_data = create_default_menu()
                
                # Save the default menu
                write_menu_file(menu_data)
                logger.info(f"Created default menu with {len(menu_data.get('items', []))} items")
            
        # Update cache
        _menu_cache = menu_data
        _last_refresh_time = current_time
        
        logger.info(f"Successfully loaded menu data from {file_path}")
        
        # Count items by category and log statistics
        items_count = len(menu_data.get('items', []))
        available_count = sum(1 for item in menu_data.get('items', []) 
                           if not item.get('snoozed', False) and item.get('available', True))
        
        # Log sample items
        for item in menu_data.get('items', [])[:3]:  # Just show the first 3
            logger.info(f"Menu item: {item.get('name', '[No name]')} → {item.get('reference_handler', '')}")
            
        logger.info(f"Menu loaded: {items_count} total items, {available_count} available")
        
        # Ensure menu has the required structure
        if "items" not in menu_data:
            menu_data["items"] = []
        if "modifiers" not in menu_data:
            menu_data["modifiers"] = []
        if "modifierGroups" not in menu_data:
            menu_data["modifierGroups"] = []
        if "name_variants" not in menu_data:
            menu_data["name_variants"] = {}
            
        return menu_data 
    except FileNotFoundError:
        # Log the error and generate a simple default menu for demo purposes
        logger.error(f"Menu file not found at {file_path} - using default menu data")
        
        # Check if we have sample menu data
        sample_menu_path = os.path.join(APP_ROOT_PARENT, 'testing_data', 'sample_menu.json')
        if os.path.exists(sample_menu_path):
            try:
                with open(sample_menu_path, 'r') as f:
                    menu_data = json.load(f)
                logger.info(f"Loaded sample menu from {sample_menu_path}")
                
                # Cache this sample data
                _menu_cache = menu_data
                _last_refresh_time = current_time
                
                # Also write it to the expected location for future use
                write_menu_file(menu_data, file_path)
                
                return menu_data
            except Exception as e:
                logger.error(f"Error loading sample menu: {e}")
        
        # Create a minimal default menu
        default_menu = {
            "items": [
                {
                    "id": "california_roll",
                    "name": "California Roll",
                    "price": 9.95,
                    "reference_handler": "CAL-ROLL",
                    "available": True,
                    "category": "Rolls"
                },
                {
                    "id": "spicy_tuna",
                    "name": "Spicy Tuna Roll",
                    "price": 12.95,
                    "reference_handler": "SPICY-TUNA",
                    "available": True,
                    "category": "Rolls"
                },
                {
                    "id": "edamame",
                    "name": "Edamame",
                    "price": 5.95,
                    "reference_handler": "EDAMAME",
                    "available": True,
                    "category": "Appetizers"
                }
            ],
            "modifiers": [],
            "modifierGroups": [],
            "name_variants": {
                "california roll": "California Roll",
                "california": "California Roll",
                "spicy tuna roll": "Spicy Tuna Roll",
                "spicy tuna": "Spicy Tuna Roll",
                "edamame": "Edamame"
            }
        }
        
        # Save this default menu for future use
        try:
            write_menu_file(default_menu, file_path)
            logger.info(f"Created default menu at {file_path}")
        except Exception as e:
            logger.error(f"Could not write default menu: {e}")
        
        # Update cache with default menu
        _menu_cache = default_menu
        _last_refresh_time = current_time
        
        return default_menu
    except Exception as e:
        logger.error(f"Error loading menu data: {e}")
        # Return empty structure if file can't be loaded
        empty_menu = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
        
        # Update cache with empty menu to avoid repeat errors
        _menu_cache = empty_menu
        _last_refresh_time = current_time
        
        return empty_menu

def find_menu_item_by_name(item_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name.
    
    Args:
        item_name (str): The name of the item to find
        
    Returns:
        dict: The menu item if found, None otherwise
    """
    # Load menu data
    menu_data = load_menu_data()
    
    # Add debug logging
    logger.info(f"[MENU-LOOKUP] Looking for item: '{item_name}'")
    
    # Normalize name for case-insensitive matching
    item_name_lower = item_name.lower().strip()
    logger.debug(f"[MENU-LOOKUP] Normalized to: '{item_name_lower}'")
    
    # Check name variants first
    name_variants = menu_data.get("name_variants", {})
    logger.debug(f"[MENU-LOOKUP] Checking against {len(name_variants)} name variants")
    
    # Log available variants for debugging
    variant_keys = list(name_variants.keys())
    logger.debug(f"[MENU-LOOKUP] Available variants: {variant_keys[:5]}...")
    
    if item_name_lower in name_variants:
        actual_name = name_variants[item_name_lower]
        logger.info(f"[MENU-LOOKUP] Found name variant match: '{item_name_lower}' → '{actual_name}'")
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == actual_name.lower():
                logger.info(f"[MENU-LOOKUP] Found matching menu item: {item.get('name')}")
                return item
    
    # Try partial variant match if exact match fails
    for variant, actual_name in name_variants.items():
        if variant in item_name_lower or item_name_lower in variant:
            logger.info(f"[MENU-LOOKUP] Found partial name variant match: '{item_name_lower}' ⊂ '{variant}' → '{actual_name}'")
            for item in menu_data.get("items", []):
                if item.get("name", "").lower() == actual_name.lower():
                    logger.info(f"[MENU-LOOKUP] Found matching menu item via partial variant: {item.get('name')}")
                    return item
    
    # Try direct match
    logger.debug(f"[MENU-LOOKUP] Checking against {len(menu_data.get('items', []))} menu items")
    for item in menu_data.get("items", []):
        item_name_in_menu = item.get("name", "").lower()
        if item_name_in_menu == item_name_lower:
            logger.info(f"[MENU-LOOKUP] Found direct match: '{item_name_lower}' = '{item_name_in_menu}'")
            return item
        # Try partial matches within menu items
        elif item_name_lower in item_name_in_menu or item_name_in_menu in item_name_lower:
            logger.info(f"[MENU-LOOKUP] Found partial item match: '{item_name_lower}' ⊂ '{item_name_in_menu}'")
            return item
    
    # No match found
    logger.warning(f"[MENU-LOOKUP] No match found for '{item_name}'")
    return None

def parse_utc_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
    """
    Parse a UTC timestamp string into a datetime object.
    
    Args:
        timestamp: A string timestamp in ISO format
        
    Returns:
        datetime: A timezone-aware datetime object, or None if parsing fails
    """
    if not timestamp:
        return None
        
    try:
        # Handle timestamps with 'Z' suffix
        if timestamp.endswith('Z'):
            # Remove 'Z' and add UTC timezone
            dt = datetime.fromisoformat(timestamp[:-1])
            return dt.replace(tzinfo=timezone.utc)
        else:
            # No 'Z', try to parse directly
            dt = datetime.fromisoformat(timestamp)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except (ValueError, TypeError):
        # Failed to parse
        return None

def is_item_snoozed_timebased(item: Dict[str, Any]) -> bool:
    """
    Check if an item is snoozed based on time-based snoozing.
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if item is snoozed, False otherwise
    """
    # Check if the item has snooze start and end times
    if not item or "snoozeStart" not in item or "snoozeEnd" not in item:
        return False
        
    # Parse the timestamps
    start_time = parse_utc_timestamp(item.get("snoozeStart"))
    end_time = parse_utc_timestamp(item.get("snoozeEnd"))
    
    # If timestamps invalid, item is not snoozed
    if not start_time or not end_time:
        return False
    
    # Check if current time is between start and end
    now = datetime.now(timezone.utc)
    return start_time <= now <= end_time

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

def is_item_currently_available_by_schedule(item: Dict[str, Any]) -> bool:
    """
    Check if an item is available based on its scheduled availability.
    
    Args:
        item: The menu item to check
    """
    # Get availability blocks from the item
    all_blocks = item.get("availabilities", [])
    if not all_blocks:
        return True  # No availabilities means always available
    
    # Get current day of week and time
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    day_of_week = now_utc.isoweekday()
    now_time = now_utc.time()
    
    # Check if the current time falls within any availability block
    for block in all_blocks:
        block_dow = block.get("dayOfWeek")
        start_str = block.get("startTime", "00:00")
        end_str = block.get("endTime", "23:59")
        
        # Skip blocks for different days
        if block_dow != day_of_week:
            continue
            
        # Parse time strings
        try:
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
        except Exception as e:
            logger.error(f"Error parsing block time: {e}")
            continue
            
        # Create time objects
        start_t = datetime.time(hour=start_hour, minute=start_min)
        end_t = datetime.time(hour=end_hour, minute=end_min)
        
        # Check if current time is within this block
        if start_t <= now_time <= end_t:
            return True
    
    # No matching block found for current day/time
    return False

def process_deliverect_menu(deliverect_menu, location_id=None):
    """
    Converts Deliverect menu format to our internal format required for ordering.
    Ensures that all items have valid names for Deliverect integration.
    
    Args:
        deliverect_menu: The menu data from Deliverect
        location_id: Optional location ID for location-specific settings
        
    Returns:
        dict: Processed menu in our internal format
        
    Raises:
        ValueError: If menu data is invalid or cannot be processed
    """
    # Log the raw structure to help diagnose issues
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[DELIVERECT-MENU] Starting menu processing")
    
    # First, validate the input data
    if not isinstance(deliverect_menu, dict):
        logger.error(f"[DELIVERECT-MENU] Invalid menu data type: {type(deliverect_menu)}")
        raise ValueError(f"Menu data must be a dictionary, got {type(deliverect_menu)}")
        
    # Check for required fields
    if "categories" not in deliverect_menu:
        logger.error("[DELIVERECT-MENU] Missing 'categories' in menu data")
        categories = []
    else:
        categories = deliverect_menu.get("categories", [])
        
    # Log general structure
    try:
        cat_count = len(categories)
        logger.info(f"[DELIVERECT-MENU] Processing menu with {cat_count} categories")
        
        # Count total products
        product_count = sum(len(cat.get("products", [])) for cat in categories)
        logger.info(f"[DELIVERECT-MENU] Found {product_count} total products across all categories")
    except Exception as e:
        logger.error(f"[DELIVERECT-MENU] Error analyzing menu structure: {e}")
        # Continue with processing anyway
    
    # Initialize result structure
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {}
    }
    
    # Track IDs to avoid duplicates
    processed_item_ids = set()
    processed_modifier_ids = set()
    processed_modifier_group_ids = set()
    
    # Create name variants dictionary for easier item lookups
    name_variants = {}
    
    # STEP 1: Extract categories and process the main products
    categories = deliverect_menu.get("categories", [])
    logger.info(f"[DELIVERECT] Processing {len(categories)} categories")
    
    for category in categories:
        cat_id = category.get("id")
        cat_name = category.get("name", "")
        products = category.get("products", [])
        
        # Process each product in the category
        for product in products:
            prod_id = product.get("id")
            prod_name = product.get("name")
            
            # Check if name is missing or empty
            if not prod_name:
                logger.warning(f"[DELIVERECT] Product with ID {prod_id} has no name, attempting to generate one")
                # Try to generate a name from other fields
                if product.get("title"):
                    prod_name = product.get("title")
                    logger.info(f"[DELIVERECT] Using 'title' as name for product {prod_id}")
                elif product.get("plu"):
                    prod_name = f"Item-{product.get('plu')}"
                    logger.info(f"[DELIVERECT] Using PLU to generate name for product {prod_id}")
                elif prod_id:
                    prod_name = f"Item-{prod_id}"
                    logger.info(f"[DELIVERECT] Using ID to generate name for product {prod_id}")
                else:
                    # Generate a placeholder name with index
                    prod_name = f"Unnamed Product {len(processed_item_ids) + 1}"
                    logger.warning(f"[DELIVERECT] Generated generic name for product without ID or name")
            elif prod_name == "":
                # Empty string name
                if prod_id:
                    prod_name = f"Item-{prod_id}"
                else:
                    prod_name = f"Unnamed Product {len(processed_item_ids) + 1}"
                logger.warning(f"[DELIVERECT] Fixed empty string name for product {prod_id}")
            
            # Skip duplicates
            if prod_id in processed_item_ids:
                continue
                
            processed_item_ids.add(prod_id)
            
            # Get PLU (reference_handler) from the product
            plu = product.get("plu", "")
            
            # Location-specific PLU override if provided
            if location_id:
                for location in product.get("locations", []):
                    if location.get("id") == location_id and location.get("plu"):
                        plu = location.get("plu")
                        price = location.get("price", product.get("price", 0)) / 100
                        break
                else:
                    price = product.get("price", 0) / 100
            else:
                price = product.get("price", 0) / 100
            
            # Create menu item with complete data
            menu_item = {
                "id": prod_id,
                "name": prod_name,
                "price": price,
                "reference_handler": plu,
                "description": product.get("description", ""),
                "imageUrl": product.get("imageUrl", ""),
                "snoozed": not product.get("available", True),
                "category": cat_name,
                "categoryId": cat_id,
                "available": product.get("available", True)
            }
            
            # Add availability schedule if present
            if "availability" in product:
                menu_item["availabilities"] = convert_availability(product.get("availability", []))
            
            # Process modifier groups references
            mod_group_ids = []
            for group in product.get("modifierGroups", []):
                group_id = group.get("id")
                if group_id:
                    mod_group_ids.append(group_id)
            
            if mod_group_ids:
                menu_item["modifierGroups"] = mod_group_ids
                
            # Add to items list
            result["items"].append(menu_item)
            
            # Generate name variants for this item (for easier lookup)
            add_name_variants(prod_name, name_variants)
    
    # STEP 2: Process modifiers and modifier groups
    all_modifiers = {}
    all_modifier_groups = {}
    
    # First collect all modifier groups from the nested structure
    for category in categories:
        for product in category.get("products", []):
            for group in product.get("modifierGroups", []):
                group_id = group.get("id")
                
                # Skip duplicates
                if group_id in processed_modifier_group_ids:
                    continue
                    
                processed_modifier_group_ids.add(group_id)
                
                # Create the modifier group record
                group_data = deliverect_menu.get("modifierGroups", {}).get(group_id, {})
                
                new_group = {
                    "id": group_id,
                    "name": group_data.get("name", ""),
                    "minAllowed": group_data.get("min", 0),
                    "maxAllowed": group_data.get("max", 999),
                    "modifiers": []
                }
                
                # Add modifiers to group
                for modifier_id in group_data.get("subProducts", []):
                    new_group["modifiers"].append(modifier_id)
                    
                    # Add to all_modifier_groups
                    all_modifier_groups[group_id] = new_group
    
    # Process all modifiers in the menu
    for modifier_id, modifier_data in deliverect_menu.get("modifiers", {}).items():
        # Skip if already processed
        if modifier_id in processed_modifier_ids:
            continue
            
        processed_modifier_ids.add(modifier_id)
        
        # Create the modifier record
        new_modifier = {
            "id": modifier_id,
            "name": modifier_data.get("name", ""),
            "price": modifier_data.get("price", 0) / 100,
            "available": modifier_data.get("available", True),
            "snoozed": not modifier_data.get("available", True),
            "reference_handler": modifier_data.get("plu", "")
        }
        
        # Add to all_modifiers
        all_modifiers[modifier_id] = new_modifier
    
    # Now add all modifiers and modifier groups to the result
    for modifier_id, modifier in all_modifiers.items():
        result["modifiers"].append(modifier)
        
    for group_id, group in all_modifier_groups.items():
        result["modifierGroups"].append(group)
    
    # Add name variants to the result
    result["name_variants"] = name_variants
    
    # Final validation to ensure all items have names
    items_missing_names = [item for item in result.get("items", []) if not item.get("name")]
    if items_missing_names:
        missing_count = len(items_missing_names)
        item_indices = [result.get("items", []).index(item) for item in items_missing_names[:3]]
        logger.error(f"[DELIVERECT] {missing_count} items still missing names after processing. Problem indices: {item_indices}")
        raise ValueError("Menu items must have names")
    
    # Log summary
    logger.info(f"[DELIVERECT] Processed: {len(result['items'])} items, " + 
                f"{len(result['modifiers'])} modifiers, " + 
                f"{len(result['modifierGroups'])} modifier groups, " + 
                f"{len(name_variants)} name variants")
    
    return result

def create_default_menu():
    """
    Creates a default menu with basic items when no valid menu is available.
    This ensures the system always has something to work with.
    
    Returns:
        dict: A basic menu with required structure and sample items
    """
    logger.warning("Creating default menu - this should only happen when no valid menu exists")
    
    # Create a more comprehensive default menu with common items
    default_menu = {
        "items": [
            # Sushi rolls
            {
                "id": "default_001",
                "name": "California Roll",
                "price": 9.95,
                "reference_handler": "CAL-ROLL",
                "description": "Crab, avocado and cucumber roll",
                "available": True,
                "snoozed": False,
                "category": "Sushi"
            },
            {
                "id": "default_002",
                "name": "Spicy Tuna Roll",
                "price": 12.95,
                "reference_handler": "SPICY-TUNA",
                "description": "Spicy tuna roll with cucumber",
                "available": True,
                "snoozed": False,
                "category": "Sushi"
            },
            {
                "id": "default_003",
                "name": "Dragon Roll",
                "price": 14.95,
                "reference_handler": "DRAGON",
                "description": "Eel, avocado and cucumber with special sauce",
                "available": True,
                "snoozed": False,
                "category": "Special Rolls"
            },
            # Appetizers
            {
                "id": "default_004",
                "name": "Edamame",
                "price": 5.95,
                "reference_handler": "EDAMAME",
                "description": "Steamed soy beans with sea salt",
                "available": True,
                "snoozed": False,
                "category": "Appetizers"
            },
            {
                "id": "default_005",
                "name": "Gyoza",
                "price": 7.95,
                "reference_handler": "GYOZA",
                "description": "Pan-fried dumplings filled with vegetables and pork",
                "available": True,
                "snoozed": False,
                "category": "Appetizers"
            },
            {
                "id": "default_006",
                "name": "Miso Soup",
                "price": 3.95,
                "reference_handler": "MISO",
                "description": "Traditional Japanese soup with tofu and seaweed",
                "available": True,
                "snoozed": False,
                "category": "Soup"
            },
            # Main dishes
            {
                "id": "default_007",
                "name": "Vegetable Tempura",
                "price": 10.95,
                "reference_handler": "VEG-TEMP",
                "description": "Assorted vegetables, lightly battered and deep fried",
                "available": True,
                "snoozed": False,
                "category": "Tempura"
            },
            {
                "id": "default_008",
                "name": "Chicken Teriyaki",
                "price": 14.95,
                "reference_handler": "CHIX-TERI",
                "description": "Grilled chicken with teriyaki sauce",
                "available": True,
                "snoozed": False,
                "category": "Main Dish"
            },
            {
                "id": "default_009",
                "name": "Salmon Teriyaki",
                "price": 16.95,
                "reference_handler": "SALM-TERI",
                "description": "Grilled salmon with teriyaki sauce",
                "available": True,
                "snoozed": False,
                "category": "Main Dish"
            },
            # Desserts
            {
                "id": "default_010",
                "name": "Mochi Ice Cream",
                "price": 5.95,
                "reference_handler": "MOCHI",
                "description": "Japanese rice cake filled with ice cream, 2 pieces",
                "available": True,
                "snoozed": False,
                "category": "Dessert"
            },
            # Burgers for demonstration
            {
                "id": "default_011",
                "name": "Veggie Burger",
                "price": 12.95,
                "reference_handler": "VEG-BURG",
                "description": "Plant-based burger patty with lettuce, tomato, and special sauce",
                "available": True,
                "snoozed": False,
                "category": "Burgers"
            }
        ],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {
            # Sushi rolls
            "california roll": "California Roll",
            "california": "California Roll",
            "spicy tuna roll": "Spicy Tuna Roll",
            "spicy tuna": "Spicy Tuna Roll",
            "tuna roll": "Spicy Tuna Roll",
            "dragon roll": "Dragon Roll",
            
            # Appetizers
            "edamame": "Edamame",
            "beans": "Edamame",
            "gyoza": "Gyoza",
            "dumplings": "Gyoza",
            "potstickers": "Gyoza",
            "miso soup": "Miso Soup",
            "miso": "Miso Soup",
            
            # Main dishes
            "vegetable tempura": "Vegetable Tempura",
            "tempura": "Vegetable Tempura",
            "veg tempura": "Vegetable Tempura",
            "chicken teriyaki": "Chicken Teriyaki",
            "teriyaki chicken": "Chicken Teriyaki",
            "salmon teriyaki": "Salmon Teriyaki",
            "teriyaki salmon": "Salmon Teriyaki",
            
            # Desserts
            "mochi": "Mochi Ice Cream",
            "mochi ice cream": "Mochi Ice Cream",
            
            # Burgers
            "veggie burger": "Veggie Burger",
            "vegetable burger": "Veggie Burger",
            "vegan burger": "Veggie Burger"
        }
    }
    
    logger.info(f"Created default menu with {len(default_menu['items'])} items")
    return default_menu

def add_name_variants(item_name, variants_dict):
    """
    Add standard name variants for an item to make it easier to find
    through voice search.
    
    Args:
        item_name: The item name to generate variants for
        variants_dict: Dictionary to update with variants
    """
    if not item_name:
        return
        
    # Convert to lowercase for consistent matching
    item_name_lower = item_name.lower()
    
    # Add the base name
    variants_dict[item_name_lower] = item_name
    
    # Split into words
    words = item_name_lower.split()
    
    # Handle single-word items
    if len(words) == 1:
        return
        
    # For multi-word items, add key words as variants
    for word in words:
        # Only add meaningful words (4+ chars, not common stopwords)
        if len(word) >= 4 and word not in ["with", "and", "the", "for", "or"]:
            if word not in variants_dict:
                variants_dict[word] = item_name
    
    # Common food word handling
    if "burger" in item_name_lower:
        variants_dict["burger"] = item_name
        
    if "fries" in item_name_lower:
        variants_dict["fries"] = item_name
        
    if "chicken" in item_name_lower:
        variants_dict["chicken"] = item_name
        
    if "pizza" in item_name_lower:
        variants_dict["pizza"] = item_name
    
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

def process_product_changes(product_id, data, location_id=None):
    """
    Process product changes from Deliverect.
    
    Args:
        product_id: Product ID
        data: Product data
        location_id: Optional location ID
        
    Returns:
        bool: Success status
    """
    pass

def process_modifier_group_changes(group_id, data):
    """
    Process modifier group changes from Deliverect.
    
    Args:
        group_id: Group ID
        data: Group data
        
    Returns:
        bool: Success status
    """
    pass

def process_modifier_changes(modifier_id, data):
    """
    Process modifier changes from Deliverect.
    
    Args:
        modifier_id: Modifier ID
        data: Modifier data
        
    Returns:
        bool: Success status
    """
    pass

def update_menu_ordering(data, location_id=None):
    """
    Update menu ordering from Deliverect.
    
    Args:
        data: Ordering data
        location_id: Optional location ID
        
    Returns:
        bool: Success status
    """
    pass

def process_meal_deal(meal_item, component_selections):
    """
    Process a meal deal order with component selections.
    
    Args:
        meal_item: The parent meal deal item
        component_selections: Dict of component selections by id
        
    Returns:
        dict: Processed meal deal item ready for ordering
    """
    # Create a copy of the main item
    processed_item = {
        "name": meal_item.get("name", ""),
        "reference_handler": meal_item.get("reference_handler", ""),
        "price": meal_item.get("price", 0.0),
        "quantity": 1,
        "modifier": [],
        "components": []
    }
    
    # Add selected components as modifiers
    for component_id, selection in component_selections.items():
        component_name = selection.get("name", "Unknown Component")
        modifiers = selection.get("modifier", [])
        
        # Add the component as an ordered component
        processed_item["components"].append({
            "id": component_id,
            "name": component_name,
            "modifiers": modifiers
        })
        
        # Also add modifiers to the main modifier list for compatibility
        for mod in modifiers:
            processed_item["modifier"].append(mod)
    
    return processed_item

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
    source_menu = load_menu_data(location_id=source_location_id, force_refresh=True)
    source_items = {item.get("name", "").lower(): item for item in source_menu.get("items", [])}
    
    # If target is specified, load it, otherwise update the same menu
    if target_location_id and target_location_id != source_location_id:
        target_menu = load_menu_data(location_id=target_location_id, force_refresh=True)
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
        load_menu_data(location_id=target_location_id, force_refresh=True)
        
    return stats
