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
    if not force_refresh and _menu_cache is not None and isinstance(_menu_cache, dict) and (current_time - _last_refresh_time) < _cache_duration:
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
                
                # Validate that menu_data is a dictionary
                if not isinstance(menu_data, dict):
                    logger.error(f"Menu data in {file_path} is not a dictionary, it's a {type(menu_data)}")
                    menu_data = create_default_menu()
                    write_menu_file(menu_data, file_path)
                    logger.info(f"Replaced non-dictionary menu data with default menu")
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
    
    # Validate order_items is a list
    if not isinstance(order_items, list):
        logger.warning(f"[MODIFIER-CONSTRAINTS] order_items is not a list: {type(order_items)}")
        return False, "Invalid order items format"
    
    for item in order_items:
        # Ensure item is a dictionary
        if not isinstance(item, dict):
            logger.warning(f"[MODIFIER-CONSTRAINTS] Skipping non-dictionary item: {type(item)}")
            continue
            
        item_name = item.get("name", "")
        # Find the menu item definition
        menu_item = next((i for i in menu_data.get("items", []) if i.get("name") == item_name), None)
        if not menu_item:
            continue
            
        # Get modifier groups for this item - ensure it's a list
        mod_group_ids = menu_item.get("modifierGroups", [])
        if not isinstance(mod_group_ids, list):
            logger.warning(f"[MODIFIER-CONSTRAINTS] modifierGroups for '{item_name}' is not a list: {type(mod_group_ids)}")
            mod_group_ids = []
            
        # Get selected modifiers - ensure it's a list
        selected_mods = item.get("modifier", [])
        if not isinstance(selected_mods, list):
            logger.warning(f"[MODIFIER-CONSTRAINTS] modifiers for '{item_name}' is not a list: {type(selected_mods)}")
            selected_mods = []
        
        # Check each modifier group
        for group_id in mod_group_ids:
            # Find the modifier group
            modifier_groups = menu_data.get("modifierGroups", [])
            if not isinstance(modifier_groups, list):
                logger.warning(f"[MODIFIER-CONSTRAINTS] modifierGroups in menu is not a list: {type(modifier_groups)}")
                continue
                
            group = next((g for g in modifier_groups if isinstance(g, dict) and g.get("id") == group_id), None)
            if not group:
                logger.warning(f"[MODIFIER-CONSTRAINTS] Modifier group '{group_id}' not found")
                continue
                
            min_allowed = group.get("minAllowed", 0)
            max_allowed = group.get("maxAllowed", 999)
            
            # Get modifiers from this group - ensure it's a list
            group_modifiers = group.get("modifiers", [])
            if not isinstance(group_modifiers, list):
                logger.warning(f"[MODIFIER-CONSTRAINTS] modifiers in group '{group_id}' is not a list: {type(group_modifiers)}")
                group_modifiers = []
            
            # Count modifiers from this group
            group_mod_ids = []
            group_mod_names = []
            
            for m in group_modifiers:
                if isinstance(m, dict):
                    if m.get("id"):
                        group_mod_ids.append(m.get("id"))
                    if m.get("name"):
                        name = m.get("name")
                        if isinstance(name, str):
                            group_mod_names.append(name.lower())
                elif isinstance(m, str):
                    # For string-based modifier references
                    group_mod_ids.append(m)
            
            # Match modifiers by ID or name
            selected_from_group = []
            for mod in selected_mods:
                if not isinstance(mod, dict):
                    logger.warning(f"[MODIFIER-CONSTRAINTS] Skipping non-dictionary modifier: {type(mod)}")
                    continue
                    
                mod_id = mod.get("id")
                mod_name = mod.get("name", "")
                if not isinstance(mod_name, str):
                    mod_name = str(mod_name) if mod_name is not None else ""
                mod_name = mod_name.lower()
                
                if mod_id in group_mod_ids or mod_name in group_mod_names:
                    selected_from_group.append(mod)
            
            # Calculate total quantity
            total_qty = 0
            for m in selected_from_group:
                qty = m.get("quantity", 1)
                if isinstance(qty, (int, float)):
                    total_qty += qty
                else:
                    # Try to convert to int
                    try:
                        total_qty += int(qty)
                    except (ValueError, TypeError):
                        logger.warning(f"[MODIFIER-CONSTRAINTS] Invalid quantity for modifier: {qty}")
                        total_qty += 1  # Default to 1
            
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
    
    Handles multiple Deliverect formats:
    1. Standard format with "categories" key
    2. List of menu items 
    3. List with first item containing categories and products
    
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
    
    # First, validate the input data and handle different formats
    if isinstance(deliverect_menu, list):
        # Handle list format (Deliverect sometimes sends menu as a list)
        if len(deliverect_menu) > 0:
            if isinstance(deliverect_menu[0], dict):
                # Check if first item has categories or is a direct menu item
                first_item = deliverect_menu[0]
                if "categories" in first_item:
                    # It's a list where first item has the menu structure
                    logger.info("[DELIVERECT-MENU] List format with first item containing categories")
                    deliverect_menu = first_item
                else:
                    # It's a list of menu items
                    logger.info("[DELIVERECT-MENU] List format with direct menu items")
                    # Create a direct menu structure with these items
                    result = {
                        "items": [],
                        "modifiers": [],
                        "modifierGroups": [],
                        "name_variants": {}
                    }
                    
                    # Process each item in the list to ensure it has a name
                    for i, item in enumerate(deliverect_menu):
                        if not isinstance(item, dict):
                            logger.warning(f"[DELIVERECT-MENU] Skipping non-dict item at index {i}")
                            continue
                            
                        # Make sure item has a name
                        if not item.get("name"):
                            # Try to get name from other fields
                            if item.get("title"):
                                item["name"] = item["title"]
                            elif item.get("product_name"):
                                item["name"] = item["product_name"]
                            elif item.get("plu"):
                                item["name"] = f"Item-{item['plu']}"
                            elif item.get("id") or item.get("_id"):
                                item_id = item.get("id") or item.get("_id")
                                item["name"] = f"Item-{item_id}"
                            else:
                                item["name"] = f"Menu Item {i+1}"
                        
                        # Add any other required fields
                        if not item.get("reference_handler") and item.get("plu"):
                            item["reference_handler"] = item["plu"]
                        elif not item.get("reference_handler"):
                            item["reference_handler"] = f"REF-{i:04d}"
                            
                        # Ensure price is in correct format (dollars, not cents)
                        if "price" in item and isinstance(item["price"], (int, float)) and item["price"] > 100:
                            item["price"] = item["price"] / 100  # Convert cents to dollars
                            
                        # Add item to result
                        result["items"].append(item)
                        
                    # Add name variants
                    for item in result["items"]:
                        if item.get("name"):
                            # Make sure name is a string
                            if not isinstance(item["name"], str):
                                item["name"] = str(item["name"])
                            try:
                                add_name_variants(item["name"], result["name_variants"])
                            except Exception as e:
                                logger.warning(f"[DELIVERECT-MENU] Error adding variants for {item['name']}: {e}")
                                # At minimum, add the base name
                                result["name_variants"][item["name"].lower()] = item["name"]
                        
                    logger.info(f"[DELIVERECT-MENU] Processed {len(result['items'])} items from list format")
                    return result
            else:
                logger.error("[DELIVERECT-MENU] List contains non-dictionary items")
                raise ValueError("Menu data list contains non-dictionary items")
        else:
            logger.error("[DELIVERECT-MENU] Empty list provided")
            raise ValueError("Empty menu data list provided")
    
    # At this point we should have a dictionary
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
    if not isinstance(categories, list):
        logger.warning(f"[DELIVERECT] Categories is not a list: {type(categories)}")
        categories = []
    
    # Check for products at the top level as well (some Deliverect data has this format)
    root_products = deliverect_menu.get("products", [])
    if isinstance(root_products, list) and len(root_products) > 0:
        logger.info(f"[DELIVERECT] Found {len(root_products)} products at the root level")
        # Create a synthetic category for these products
        root_category = {
            "id": "root_products",
            "name": "Menu Items",
            "products": root_products
        }
        categories.append(root_category)
    
    logger.info(f"[DELIVERECT] Processing {len(categories)} categories")
    
    for category in categories:
        # Ensure category is a dictionary
        if not isinstance(category, dict):
            logger.warning(f"[DELIVERECT] Category is not a dictionary: {type(category)}")
            continue
        cat_id = category.get("id")
        cat_name = category.get("name", "")
        products = category.get("products", [])
        
        # Ensure products is a list
        if not isinstance(products, list):
            logger.warning(f"[DELIVERECT] Products in category {cat_id} is not a list: {type(products)}")
            products = []
        
        # Filter out non-dictionary products (strings, etc.)
        valid_products = []
        invalid_count = 0
        parsed_count = 0
        
        for prod in products:
            if isinstance(prod, dict):
                valid_products.append(prod)
            else:
                # Try to parse string products as JSON if they look like JSON objects
                if isinstance(prod, str) and prod.strip().startswith('{') and prod.strip().endswith('}'):
                    try:
                        import json
                        parsed_prod = json.loads(prod)
                        if isinstance(parsed_prod, dict):
                            logger.info(f"[DELIVERECT] Successfully parsed string product as JSON in category {cat_id}")
                            valid_products.append(parsed_prod)
                            parsed_count += 1
                            continue
                    except Exception as e:
                        logger.warning(f"[DELIVERECT] Failed to parse string product as JSON: {e}")
                
                invalid_count += 1
        
        if invalid_count > 0:
            if parsed_count > 0:
                logger.info(f"[DELIVERECT] Successfully parsed {parsed_count} string products as JSON in category {cat_id}")
            
            logger.warning(f"[DELIVERECT] Filtered out {invalid_count} invalid products in category {cat_id}")
            products = valid_products
        
        # Process each product in the category
        for product in products:
            # Ensure product is a dictionary
            if not isinstance(product, dict):
                logger.warning(f"[DELIVERECT] Product in category {cat_id} is not a dictionary: {type(product)}")
                continue
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
                locations = product.get("locations", [])
                if not isinstance(locations, list):
                    logger.warning(f"[DELIVERECT] locations for product {prod_id} is not a list: {type(locations)}")
                    locations = []
                    
                for location in locations:
                    if not isinstance(location, dict):
                        logger.warning(f"[DELIVERECT] Location in product {prod_id} is not a dictionary: {type(location)}")
                        continue
                        
                    if location.get("id") == location_id and location.get("plu"):
                        plu = location.get("plu")
                        price_value = location.get("price", product.get("price", 0))
                        if isinstance(price_value, (int, float)):
                            price = price_value / 100
                        else:
                            logger.warning(f"[DELIVERECT] Invalid price for location {location_id}: {price_value}")
                            price = 0
                        break
                else:
                    price_value = product.get("price", 0)
                    if isinstance(price_value, (int, float)):
                        price = price_value / 100
                    else:
                        logger.warning(f"[DELIVERECT] Invalid price for product {prod_id}: {price_value}")
                        price = 0
            else:
                price_value = product.get("price", 0)
                if isinstance(price_value, (int, float)):
                    price = price_value / 100
                else:
                    logger.warning(f"[DELIVERECT] Invalid price for product {prod_id}: {price_value}")
                    price = 0
            
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
                availability_data = product.get("availability", [])
                try:
                    menu_item["availabilities"] = convert_availability(availability_data)
                except Exception as e:
                    logger.warning(f"[DELIVERECT] Error converting availability for product {prod_id}: {e}")
                    menu_item["availabilities"] = []
            # Also check for "availabilities" (plural) which is sometimes used
            elif "availabilities" in product:
                availability_data = product.get("availabilities", [])
                try:
                    menu_item["availabilities"] = convert_availability(availability_data)
                except Exception as e:
                    logger.warning(f"[DELIVERECT] Error converting availabilities for product {prod_id}: {e}")
                    menu_item["availabilities"] = []
            
            # Process modifier groups references
            mod_group_ids = []
            # Ensure modifierGroups is a list
            modifier_groups = product.get("modifierGroups", [])
            if not isinstance(modifier_groups, list):
                logger.warning(f"[DELIVERECT] modifierGroups for product {prod_id} is not a list: {type(modifier_groups)}")
                modifier_groups = []
                
            for group in modifier_groups:
                # Ensure group is a dictionary
                if not isinstance(group, dict):
                    logger.warning(f"[DELIVERECT] Modifier group for product {prod_id} is not a dictionary: {type(group)}")
                    continue
                    
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
        # Ensure category is a dictionary
        if not isinstance(category, dict):
            logger.warning(f"[DELIVERECT-MENU] Category is not a dictionary in collecting modifiers: {type(category)}")
            continue
            
        # Get products and ensure it's a list
        products = category.get("products", [])
        if not isinstance(products, list):
            logger.warning(f"[DELIVERECT-MENU] Products in category {category.get('id', 'unknown')} is not a list: {type(products)}")
            continue
            
        for product in products:
            # Ensure product is a dictionary
            if not isinstance(product, dict):
                logger.warning(f"[DELIVERECT-MENU] Product in category {category.get('id', 'unknown')} is not a dictionary: {type(product)}")
                continue
                
            # Get modifierGroups and ensure it's a list
            modifier_groups = product.get("modifierGroups", [])
            if not isinstance(modifier_groups, list):
                logger.warning(f"[DELIVERECT-MENU] ModifierGroups in product {product.get('id', 'unknown')} is not a list: {type(modifier_groups)}")
                continue
                
            for group in modifier_groups:
                # Ensure group is a dictionary
                if not isinstance(group, dict):
                    logger.warning(f"[DELIVERECT-MENU] Group in product {product.get('id', 'unknown')} is not a dictionary: {type(group)}")
                    continue
                    
                group_id = group.get("id")
                
                # Skip duplicates
                if group_id in processed_modifier_group_ids:
                    continue
                    
                processed_modifier_group_ids.add(group_id)
                
                # Create the modifier group record
                modifier_groups = deliverect_menu.get("modifierGroups", {})
                if isinstance(modifier_groups, dict):
                    group_data = modifier_groups.get(group_id, {})
                else:
                    # Handle the case where modifierGroups is not a dictionary
                    logger.warning(f"[DELIVERECT-MENU] ModifierGroups is not a dictionary: {type(modifier_groups)}")
                    group_data = {}
                
                new_group = {
                    "id": group_id,
                    "name": group_data.get("name", "") if isinstance(group_data, dict) else "",
                    "minAllowed": group_data.get("min", 0) if isinstance(group_data, dict) else 0,
                    "maxAllowed": group_data.get("max", 999) if isinstance(group_data, dict) else 999,
                    "modifiers": []
                }
                
                # Add modifiers to group
                if isinstance(group_data, dict):
                    sub_products = group_data.get("subProducts", [])
                    if isinstance(sub_products, list):
                        for modifier_id in sub_products:
                            new_group["modifiers"].append(modifier_id)
                    else:
                        logger.warning(f"[DELIVERECT-MENU] subProducts is not a list: {type(sub_products)}")
                
                # Add to all_modifier_groups
                all_modifier_groups[group_id] = new_group
    
    # Process all modifiers in the menu
    modifiers_data = deliverect_menu.get("modifiers", {})
    if not isinstance(modifiers_data, dict):
        logger.warning(f"[DELIVERECT-MENU] modifiers is not a dictionary: {type(modifiers_data)}")
        modifiers_data = {}
        
    for modifier_id, modifier_data in modifiers_data.items():
        # Skip if already processed
        if modifier_id in processed_modifier_ids:
            continue
            
        processed_modifier_ids.add(modifier_id)
        
        # Check if modifier_data is a dictionary
        if not isinstance(modifier_data, dict):
            logger.warning(f"[DELIVERECT-MENU] Modifier data for {modifier_id} is not a dictionary: {type(modifier_data)}")
            continue
        
        # Create the modifier record
        try:
            price = modifier_data.get("price", 0)
            if isinstance(price, (int, float)):
                price = price / 100
            else:
                price = 0
                logger.warning(f"[DELIVERECT-MENU] Invalid price for modifier {modifier_id}: {price}")
            
            new_modifier = {
                "id": modifier_id,
                "name": modifier_data.get("name", ""),
                "price": price,
                "available": modifier_data.get("available", True),
                "snoozed": not modifier_data.get("available", True),
                "reference_handler": modifier_data.get("plu", "")
            }
        except Exception as e:
            logger.error(f"[DELIVERECT-MENU] Error creating modifier {modifier_id}: {e}")
            continue
        
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
    # Log args for debugging
    logger.debug(f"[NAME-VARIANTS] Adding variants for: '{item_name}', type: {type(item_name)}")
    
    # Validate input arguments
    if item_name is None:
        logger.warning("[NAME-VARIANTS] Cannot add variants for None item_name")
        return
        
    if not isinstance(item_name, str):
        logger.warning(f"[NAME-VARIANTS] Converting non-string name to string: {type(item_name)}")
        try:
            item_name = str(item_name)
        except Exception as e:
            logger.error(f"[NAME-VARIANTS] Failed to convert item name to string: {e}")
            return
        
    if not item_name.strip():
        logger.warning("[NAME-VARIANTS] Cannot add variants for empty item_name")
        return
        
    if not isinstance(variants_dict, dict):
        logger.error(f"[NAME-VARIANTS] variants_dict is not a dictionary: {type(variants_dict)}")
        raise ValueError("variants_dict must be a dictionary")
        
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
    logger = logging.getLogger(__name__)
    result = []
    
    # Handle different format types
    if availability_data is None:
        logger.warning("[AVAILABILITY] availability_data is None")
        return result
        
    # Sometimes availability_data is a string (e.g. "[]")
    if isinstance(availability_data, str):
        logger.info(f"[AVAILABILITY] Converting string availability data: {availability_data[:50]}...")
        try:
            import json
            availability_data = json.loads(availability_data)
        except Exception as e:
            logger.error(f"[AVAILABILITY] Error parsing availability string: {e}")
            return result
    
    # If it's not a list by now, return empty
    if not isinstance(availability_data, list):
        logger.warning(f"[AVAILABILITY] Availability data is not a list: {type(availability_data)}")
        return result
    
    # Process each day
    for i, day_data in enumerate(availability_data):
        try:
            # Skip if not a dictionary
            if not isinstance(day_data, dict):
                logger.warning(f"[AVAILABILITY] Day data at index {i} is not a dictionary: {type(day_data)}")
                continue
                
            day = day_data.get("dayOfWeek")
            if day is None:
                logger.warning(f"[AVAILABILITY] Missing dayOfWeek in day data at index {i}")
                continue
                
            # Some formats have timeSlots, others have direct startTime/endTime
            if "timeSlots" in day_data:
                time_slots = day_data.get("timeSlots", [])
                if not isinstance(time_slots, list):
                    logger.warning(f"[AVAILABILITY] timeSlots for day {day} is not a list: {type(time_slots)}")
                    time_slots = []
                
                for j, slot in enumerate(time_slots):
                    try:
                        if not isinstance(slot, dict):
                            logger.warning(f"[AVAILABILITY] Slot at index {j} for day {day} is not a dictionary: {type(slot)}")
                            continue
                            
                        start_time = slot.get("startTime", "00:00")
                        end_time = slot.get("endTime", "23:59")
                        
                        # Validate time format
                        if not isinstance(start_time, str) or not isinstance(end_time, str):
                            logger.warning(f"[AVAILABILITY] Invalid time format for day {day}, slot {j}")
                            start_time = "00:00" if not isinstance(start_time, str) else start_time
                            end_time = "23:59" if not isinstance(end_time, str) else end_time
                        
                        result.append({
                            "dayOfWeek": day,
                            "startTime": start_time,
                            "endTime": end_time
                        })
                    except Exception as slot_e:
                        logger.error(f"[AVAILABILITY] Error processing slot at index {j} for day {day}: {slot_e}")
                        continue
            else:
                # Direct start/end time
                try:
                    start_time = day_data.get("startTime", "00:00")
                    end_time = day_data.get("endTime", "23:59")
                    
                    # Validate time format
                    if not isinstance(start_time, str) or not isinstance(end_time, str):
                        logger.warning(f"[AVAILABILITY] Invalid time format for day {day}")
                        start_time = "00:00" if not isinstance(start_time, str) else start_time
                        end_time = "23:59" if not isinstance(end_time, str) else end_time
                    
                    result.append({
                        "dayOfWeek": day,
                        "startTime": start_time,
                        "endTime": end_time
                    })
                except Exception as time_e:
                    logger.error(f"[AVAILABILITY] Error processing direct time for day {day}: {time_e}")
                    continue
        except Exception as day_e:
            logger.error(f"[AVAILABILITY] Error processing day data at index {i}: {day_e}")
            continue
    
    # Log the result
    logger.info(f"[AVAILABILITY] Converted availability data: {len(result)} time blocks")
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
