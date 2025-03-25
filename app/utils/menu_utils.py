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
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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

def load_menu_data(force_refresh: bool = False, location_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load menu data from file or cache.
    
    Args:
        force_refresh (bool): Force a refresh from disk instead of using cache
        location_id (str, optional): Location-specific menu data
        
    Returns:
        dict: Menu data structure
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
            MENU_FILE_PATH,
            PRODUCTION_PATH,
            # Try various paths in the production environment
            '/home/pegasus/mysite/RedBarSushiAI/menu_data.json',
            '/home/pegasus/mysite/menu_data.json',
            '/home/pegasus/menu_data.json',
            os.path.join(APP_ROOT, 'menu_data.json'),
            os.path.join(APP_ROOT_PARENT, 'menu_data.json'),
            os.path.join(APP_ROOT_PARENT, 'redbar_menu_data.json'),
            '/tmp/menu_data.json',
            '/tmp/redbar_menu_data.json'
        ]
        
        for path in possible_files:
            if os.path.exists(path):
                file_path = path
                logger.info(f"Fallback: Using menu file at {file_path}")
                break
    
    # Try to load the file
    try:
        # Load menu data from file
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
        
        # Update cache
        _menu_cache = menu_data
        _last_refresh_time = current_time
        
        logger.info(f"Successfully loaded menu data from {file_path}")
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
    # Implementation for checking item availability by schedule
    pass

def process_deliverect_menu(deliverect_menu, location_id=None):
    """
    Process menu updates from Deliverect for a specific location.
    
    Args:
        deliverect_menu: Menu data from Deliverect
        location_id: Optional location ID
        
    Returns:
        dict: Processed menu data
    """
    pass

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