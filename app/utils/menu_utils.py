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

# Cache variables - increased cache duration for Render
_menu_cache = None
_last_refresh_time = 0
_cache_duration = 300  # 5 minutes cache duration for menu data in production
# Use a shorter duration in development
if not os.environ.get('RENDER', False):
    _cache_duration = 30  # 30 seconds for development

# Default paths - ensure they work in production environment
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT_PARENT = os.path.dirname(APP_ROOT)

# Define all possible menu file locations to check
POSSIBLE_MENU_PATHS = [
    # 1. Environment variable (highest priority)
    os.getenv('MENU_FILE_PATH'),
    
    # 2. Render-specific paths
    '/app/menu_data.json',  # Docker container path
    '/var/task/menu_data.json',  # Alternate container path
    
    # 3. Traditional deployment paths
    '/home/pegasus/mysite/RedBarSushiAI/menu_data.json',  # Legacy production path
    
    # 4. App paths
    os.path.join(APP_ROOT, 'menu_data.json'),
    os.path.join(APP_ROOT_PARENT, 'menu_data.json'),
    
    # 5. Current directory and alternatives 
    os.path.join(os.getcwd(), 'menu_data.json'),
    os.path.join(os.getcwd(), 'redbar_menu_data.json'),
    
    # 6. Fallback to temporary directory
    '/tmp/menu_data.json'
]

# Find the first path that exists
for path in POSSIBLE_MENU_PATHS:
    if path and os.path.exists(path):
        MENU_FILE_PATH = path
        logger.info(f"Menu file found at: {MENU_FILE_PATH}")
        break
else:
    # If no file exists, default to current directory
    MENU_FILE_PATH = os.path.join(os.getcwd(), 'menu_data.json')
    logger.warning(f"No menu file found, defaulting to: {MENU_FILE_PATH}")
                          
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

def create_default_menu():
    """Create a default menu with some basic items when no menu file is found."""
    logger.warning("Creating default menu with basic items")
    
    # Create a basic menu structure with some common sushi items
    default_menu = {
        "items": [
            {
                "name": "California Roll",
                "price": 8.99,
                "reference_handler": "cali-roll-1",
                "available": True,
                "snoozed": False
            },
            {
                "name": "Spicy Tuna Roll",
                "price": 9.99,
                "reference_handler": "spicy-tuna-1", 
                "available": True,
                "snoozed": False
            },
            {
                "name": "Salmon Nigiri",
                "price": 7.99,
                "reference_handler": "salmon-nigiri-1",
                "available": True,
                "snoozed": False
            },
            {
                "name": "Dragon Roll",
                "price": 12.99,
                "reference_handler": "dragon-roll-1",
                "available": True,
                "snoozed": False
            }
        ],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {
            "california": "California Roll",
            "cali roll": "California Roll",
            "spicy tuna": "Spicy Tuna Roll",
            "salmon": "Salmon Nigiri",
            "dragon": "Dragon Roll"
        }
    }
    
    return default_menu

def load_menu_data(force_refresh: bool = False, location_id: Optional[str] = None, skip_validation: bool = False, timeout: int = 5) -> Dict[str, Any]:
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
                    menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
                    write_menu_file(menu_data, file_path)
                    logger.info(f"Replaced non-dictionary menu data with empty menu structure")
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in menu file {file_path}")
                menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
                write_menu_file(menu_data, file_path)
                logger.info(f"Replaced corrupt menu file with empty menu structure")
        
        # Check for empty or invalid data
        if (len(menu_data.get('items', [])) == 0 or 
            all(not item.get('name') for item in menu_data.get('items', []))):
            
            # If it's Deliverect format with categories - convert it
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
                    # Use empty menu structure instead of default menu
                    menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
            
            # If it's not a Deliverect format, just use an empty structure
            else:
                logger.error(f"Invalid menu data detected - using empty menu structure")
                menu_data = {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
                logger.info(f"Created empty menu structure")
            
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
        # Log the error and create a default menu with sample items
        logger.error(f"Menu file not found at {file_path} - using default menu")
        
        # Create a default menu with common sushi items instead of an empty one
        default_menu = create_default_menu()
        
        # Save the default menu for future use
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
        # Return default menu structure with sample items instead of empty
        default_menu = create_default_menu()
        
        # Update cache with default menu to avoid repeat errors
        _menu_cache = default_menu
        _last_refresh_time = current_time
        
        # Try to save it for future use
        try:
            write_menu_file(default_menu, os.path.join(os.getcwd(), 'menu_data.json'))
            logger.info("Saved default menu after loading error")
        except Exception:
            pass
            
        return default_menu

def find_menu_item_by_name(item_name: str, check_availability: bool = True) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name.
    
    Args:
        item_name (str): The name of the item to find
        check_availability (bool): Whether to filter out unavailable items
        
    Returns:
        dict: The menu item if found, None otherwise
    """
    # Load menu data
    menu_data = load_menu_data()
    
    # Add debug logging
    logger.info(f"[MENU-LOOKUP] Looking for item: '{item_name}'")
    
    # Normalize name for case-insensitive matching
    item_name_lower = item_name.lower().strip()
    
    # Also clean the name for more flexible matching
    import re
    item_name_clean = re.sub(r'[^\w\s]', ' ', item_name_lower)
    item_name_clean = re.sub(r'\s+', ' ', item_name_clean).strip()
    
    logger.info(f"[MENU-LOOKUP] Normalized to: '{item_name_lower}', Cleaned to: '{item_name_clean}'")
    
    # Check name variants first - exact matches
    name_variants = menu_data.get("name_variants", {})
    logger.info(f"[MENU-LOOKUP] Checking against {len(name_variants)} name variants")
    
    # Log sample variants for debugging
    variant_keys = list(name_variants.keys())
    if variant_keys:
        sample_keys = variant_keys[:5] if len(variant_keys) > 5 else variant_keys
        logger.info(f"[MENU-LOOKUP] Sample variants: {sample_keys}")
    
    # Check for exact matches in variants
    exact_match_names = []
    
    # First try exact match with original name (most reliable)
    if item_name_lower in name_variants:
        actual_name = name_variants[item_name_lower]
        logger.info(f"[MENU-LOOKUP] Found exact name variant match: '{item_name_lower}' → '{actual_name}'")
        exact_match_names.append(actual_name)
    
    # Then try exact match with cleaned name
    if item_name_clean in name_variants:
        actual_name = name_variants[item_name_clean]
        logger.info(f"[MENU-LOOKUP] Found exact clean variant match: '{item_name_clean}' → '{actual_name}'")
        if actual_name not in exact_match_names:
            exact_match_names.append(actual_name)
    
    # Look up the items for the exact matches first
    for actual_name in exact_match_names:
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == actual_name.lower():
                # Verify this item is available if required
                if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                    logger.info(f"[MENU-LOOKUP] Found matching menu item: {item.get('name')}")
                    return item
                else:
                    logger.warning(f"[MENU-LOOKUP] Found match '{item.get('name')}' but item is unavailable/snoozed")
    
    # Try direct item name match
    for item in menu_data.get("items", []):
        item_name_in_menu = item.get("name", "").lower()
        if item_name_in_menu == item_name_lower:
            # Verify this item is available if required
            if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                logger.info(f"[MENU-LOOKUP] Found direct match: '{item_name_lower}' = '{item_name_in_menu}'")
                return item
            else:
                logger.warning(f"[MENU-LOOKUP] Found direct match '{item_name_in_menu}' but item is unavailable/snoozed")
    
    # No exact matches - don't use static food categories
    # Instead, try direct partial matching for what was provided
    
    # Try partial variant match if both above fail
    partial_matches = []
    for variant, actual_name in name_variants.items():
        # Check if variant is contained in search term or vice versa
        if len(variant) >= 4 and (variant in item_name_lower or item_name_lower in variant):
            logger.info(f"[MENU-LOOKUP] Found partial name variant match: '{item_name_lower}' ⟷ '{variant}' → '{actual_name}'")
            partial_matches.append(actual_name)
    
    # Look up items for partial matches
    for actual_name in partial_matches:
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == actual_name.lower():
                # Verify this item is available if required
                if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                    logger.info(f"[MENU-LOOKUP] Found matching menu item via partial variant: {item.get('name')}")
                    return item
                else:
                    logger.warning(f"[MENU-LOOKUP] Found match via partial variant '{item.get('name')}' but item is unavailable/snoozed")
    
    # Try partial matches within menu items - last resort
    for item in menu_data.get("items", []):
        item_name_in_menu = item.get("name", "").lower()
        # Only do partial matching if both strings are reasonably long
        if len(item_name_lower) >= 3 and len(item_name_in_menu) >= 3:
            if item_name_lower in item_name_in_menu or item_name_in_menu in item_name_lower:
                # Verify this item is available if required
                if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                    logger.info(f"[MENU-LOOKUP] Found partial item match: '{item_name_lower}' ⊂ '{item_name_in_menu}'")
                    return item
                else:
                    logger.warning(f"[MENU-LOOKUP] Found match '{item_name_in_menu}' but item is unavailable/snoozed")
    
    # One last try - if check_availability is true, try again without checking
    if check_availability:
        item = find_menu_item_by_name(item_name, check_availability=False)
        if item:
            logger.warning(f"[MENU-LOOKUP] Found item '{item.get('name')}' but it's unavailable/snoozed")
            # Still return None since the item isn't available
            return None
    
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
    4. Handles string values in products lists and other unexpected formats
    
    Args:
        deliverect_menu: The menu data from Deliverect
        location_id: Optional location ID for location-specific settings
        
    Returns:
        dict: Processed menu in our internal format
    """
    # Log the raw structure to help diagnose issues
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[DELIVERECT-MENU] Starting menu processing")
    
    # Initialize result structure with empty collections
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {}
    }
    
    # Handle empty input
    if not deliverect_menu:
        logger.warning("[DELIVERECT-MENU] Empty menu data provided")
        return result
        
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
                    
                    # Verify categories contain actual products before processing
                    if isinstance(first_item["categories"], list):
                        for cat in first_item["categories"]:
                            if isinstance(cat, dict) and "products" in cat:
                                # Check if products contain valid items with names
                                if isinstance(cat["products"], list):
                                    all_strings = True
                                    for prod in cat["products"]:
                                        if isinstance(prod, dict) and "name" in prod:
                                            logger.info(f"[DELIVERECT-MENU] Found valid product in category: {prod.get('name')}")
                                            # At least one real product found, process normally
                                            return process_deliverect_menu(first_item, location_id)
                                        elif not isinstance(prod, str):
                                            all_strings = False
                                            
                                    # Special case: If all products are strings (IDs), check if there's a products dict elsewhere
                                    if all_strings and all(isinstance(p, str) for p in cat["products"]):
                                        logger.info(f"[DELIVERECT-MENU] Found category with product ID strings, looking for product mapping")
                                        
                                        # Look for a products dictionary in the first item
                                        if "products" in first_item and isinstance(first_item["products"], dict):
                                            # This is the ID-to-product mapping
                                            product_map = first_item["products"]
                                            logger.info(f"[DELIVERECT-MENU] Found product mapping with {len(product_map)} products")
                                            
                                            # Replace each category's product IDs with actual product objects
                                            for category in first_item["categories"]:
                                                if isinstance(category, dict) and "products" in category and isinstance(category["products"], list):
                                                    real_products = []
                                                    for prod_id in category["products"]:
                                                        if isinstance(prod_id, str) and prod_id in product_map:
                                                            real_products.append(product_map[prod_id])
                                                            logger.info(f"[DELIVERECT-MENU] Resolved product ID {prod_id} to {product_map[prod_id].get('name', 'Unnamed')}")
                                                    
                                                    # Replace string IDs with actual product objects
                                                    if real_products:
                                                        category["products"] = real_products
                                                        
                                            # Now process with the enriched data
                                            return process_deliverect_menu(first_item, location_id)
                                            
                                # Look for the products mapping in a different location or format
                                for key in first_item:
                                    if key != "categories" and isinstance(first_item[key], dict):
                                        # Check if this dictionary contains product objects with names
                                        product_map = {}
                                        for product_id, product_data in first_item[key].items():
                                            if isinstance(product_data, dict) and "name" in product_data:
                                                product_map[product_id] = product_data
                                        
                                        # If we found products, try to map them to categories
                                        if product_map:
                                            logger.info(f"[DELIVERECT-MENU] Found potential product mapping in '{key}' with {len(product_map)} products")
                                            
                                            # Replace each category's product IDs with actual product objects
                                            products_mapped = False
                                            for category in first_item["categories"]:
                                                if isinstance(category, dict) and "products" in category and isinstance(category["products"], list):
                                                    real_products = []
                                                    for prod_id in category["products"]:
                                                        if isinstance(prod_id, str) and prod_id in product_map:
                                                            real_products.append(product_map[prod_id])
                                                            products_mapped = True
                                                            logger.info(f"[DELIVERECT-MENU] Resolved product ID {prod_id} to {product_map[prod_id].get('name', 'Unnamed')}")
                                                    
                                                    # Replace string IDs with actual product objects
                                                    if real_products:
                                                        category["products"] = real_products
                                            
                                            # Process the data if we successfully mapped products
                                            if products_mapped:
                                                return process_deliverect_menu(first_item, location_id)
                    
                    # No valid products found in categories, attempt deep inspection
                    logger.info("[DELIVERECT-MENU] Categories found but no valid products, attempting deep inspection")
                    
                # Check for nested menu structure - test_nested_menu_structure case
                elif "menu" in first_item and isinstance(first_item["menu"], dict) and "categories" in first_item["menu"]:
                    # It's a list where first item has a menu structure in a 'menu' field
                    logger.info("[DELIVERECT-MENU] List format with first item containing menu.categories")
                    # Process the nested menu
                    return process_deliverect_menu(first_item["menu"], location_id)
                    
                # Check for sections pattern directly - test_recursively_find_products case
                elif "data" in first_item and isinstance(first_item["data"], dict):
                    data = first_item["data"]
                    if "store" in data and isinstance(data["store"], dict):
                        store = data["store"]
                        if "menu" in store and isinstance(store["menu"], dict):
                            menu = store["menu"]
                            if "sections" in menu and isinstance(menu["sections"], list):
                                sections = menu["sections"]
                                logger.info("[DELIVERECT-MENU] List format with sections pattern")
                                
                                # Convert sections to categories
                                structured_menu = {"categories": []}
                                
                                for section in sections:
                                    if isinstance(section, dict) and "name" in section:
                                        # Look for products in different keys
                                        for products_key in ["dishes", "products", "items", "menuItems"]:
                                            if products_key in section and isinstance(section[products_key], list):
                                                # Create a new category
                                                category = {
                                                    "id": section.get("id", f"section-{int(time.time())}"),
                                                    "name": section["name"],
                                                    "products": section[products_key]
                                                }
                                                structured_menu["categories"].append(category)
                                
                                if structured_menu["categories"]:
                                    return process_deliverect_menu(structured_menu, location_id)
                else:
                    # It's a list of menu items
                    logger.info("[DELIVERECT-MENU] List format with direct menu items")
                    
                    # First, look for real products directly in the list
                    real_products_found = False
                    for i, item in enumerate(deliverect_menu):
                        if isinstance(item, dict) and "name" in item and ("price" in item or "plu" in item or "id" in item):
                            logger.info(f"[DELIVERECT-MENU] Found direct product: {item.get('name')}")
                            real_products_found = True
                            break
                            
                    if real_products_found:
                        # Process the list as direct products
                        logger.info("[DELIVERECT-MENU] Processing list as direct products")
                        # Create a category with only verified real products
                        valid_products = [item for item in deliverect_menu if isinstance(item, dict) and "name" in item]
                        if valid_products:
                            structured_menu = {
                                "categories": [
                                    {
                                        "id": f"category-{int(time.time())}",
                                        "name": "", # Empty name - will not be shown in output data
                                        "products": valid_products
                                    }
                                ]
                            }
                        return process_deliverect_menu(structured_menu, location_id)
                    
                    # Process each item in the list to ensure it has a name
                    for i, item in enumerate(deliverect_menu):
                        # Skip non-dictionary items
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
                        
                        # Ensure name is a string
                        if item.get("name") and not isinstance(item["name"], str):
                            item["name"] = str(item["name"])
                        
                        # Add any other required fields
                        if not item.get("reference_handler") and item.get("plu"):
                            item["reference_handler"] = item["plu"]
                        elif not item.get("reference_handler"):
                            # Use the item ID as the reference if available, otherwise use a product ID based on timestamp
                            if item.get("id"):
                                item["reference_handler"] = f"{item['id']}"
                            elif item.get("name"):
                                # Create a reference based on name - ensures consistency
                                import re
                                import hashlib
                                # Clean the name for reference use
                                clean_name = re.sub(r'[^a-zA-Z0-9]', '', item["name"])
                                if clean_name:
                                    item["reference_handler"] = f"{clean_name[:10]}-{i}"
                                else:
                                    # Last resort if name has no alphanumeric chars
                                    item["reference_handler"] = f"PROD-{int(time.time() * 1000) % 1000000}-{i}"
                            else:
                                # Very last resort
                                item["reference_handler"] = f"PROD-{int(time.time() * 1000) % 1000000}-{i}"
                            
                        # Ensure price is in correct format (dollars, not cents)
                        if "price" in item and isinstance(item["price"], (int, float)) and item["price"] > 100:
                            item["price"] = item["price"] / 100  # Convert cents to dollars
                            
                        # Add item to result
                        result["items"].append(item)
                        
                    # Reset name variants for a clean slate (prevents one item from overwriting another)
                    name_variants = {}
                    
                    # Add name variants - process each item individually
                    for item in result["items"]:
                        if item.get("name"):
                            # Clear temp_variants for each item to prevent carrying variants from one item to another
                            temp_variants = {}
                            try:
                                logger.info(f"[DELIVERECT-MENU] Adding name variants for item: '{item['name']}'")
                                add_name_variants(item["name"], temp_variants)
                                
                                # Now add these to the main variants dictionary
                                for variant, variant_name in temp_variants.items():
                                    # For direct exact matches (e.g., "cheeseburger" for Cheeseburger), 
                                    # always use the exact match over partial matches
                                    if variant.lower() == item["name"].lower() or variant == item["name"].lower():
                                        name_variants[variant] = item["name"]
                                        logger.info(f"[DELIVERECT-MENU] Added exact match variant: '{variant}' → '{item['name']}'")
                                    # For keyword variants, try to avoid duplicates by checking the variant length
                                    # Prefer more specific matches (specific food words like "veggie" should go to "Veggie Burger")
                                    elif variant in name_variants:
                                        # Check if this is a more specific match (contains the variant as a word)
                                        if variant in item["name"].lower() and variant not in name_variants[variant].lower():
                                            name_variants[variant] = item["name"]
                                            logger.info(f"[DELIVERECT-MENU] Replaced variant with better match: '{variant}' → '{item['name']}'")
                                        else:
                                            logger.info(f"[DELIVERECT-MENU] Keeping existing variant mapping: '{variant}' → '{name_variants[variant]}'")
                                    else:
                                        name_variants[variant] = item["name"]
                                        logger.info(f"[DELIVERECT-MENU] Added variant: '{variant}' → '{item['name']}'")
                            except Exception as e:
                                logger.warning(f"[DELIVERECT-MENU] Error adding variants for {item['name']}: {e}")
                                # At minimum, add the base name
                                try:
                                    name_variants[item["name"].lower()] = item["name"]
                                    logger.info(f"[DELIVERECT-MENU] Added basic variant for {item['name']}")
                                except Exception as be:
                                    logger.error(f"[DELIVERECT-MENU] Failed to add even basic variant: {be}")
                    
                    # Set the result name variants
                    result["name_variants"] = name_variants
                    logger.info(f"[DELIVERECT-MENU] Added {len(name_variants)} name variants for {len(result['items'])} items")
                        
                    logger.info(f"[DELIVERECT-MENU] Processed {len(result['items'])} items from list format")
                    return result
        
        # If we reached here with a list but couldn't process it normally, try to extract any useful data
        logger.warning("[DELIVERECT-MENU] List format but no valid processing path, attempting detailed data extraction")
        try:
            # First, look for items with categories to process
            for item in deliverect_menu:
                if isinstance(item, dict) and "categories" in item:
                    logger.info("[DELIVERECT-MENU] Found categories in list item, processing recursively")
                    return process_deliverect_menu(item, location_id)
            
            # Next, inspect if any items in the list are categories themselves
            found_categories = []
            for item in deliverect_menu:
                if isinstance(item, dict):
                    # Look for category-like structures (has name and products array)
                    if item.get("name") and isinstance(item.get("products"), list):
                        logger.info(f"[DELIVERECT-MENU] Found category-like item: {item.get('name')}")
                        found_categories.append(item)
            
            # If we found categories, create a proper menu structure
            if found_categories:
                logger.info(f"[DELIVERECT-MENU] Creating menu from {len(found_categories)} categories")
                structured_menu = {"categories": found_categories}
                return process_deliverect_menu(structured_menu, location_id)
                
            # Next, look for product lists at specific keys in any dictionary item
            for item in deliverect_menu:
                if isinstance(item, dict):
                    for key in ["products", "menu", "items", "menuItems"]:
                        if key in item and isinstance(item[key], list) and len(item[key]) > 0:
                            logger.info(f"[DELIVERECT-MENU] Found products list in key: {key}")
                            # Create a menu with properly structured categories
                            products = item[key]
                            
                            # Try to determine a category name using ONLY direct data
                            category_name = ""  # Empty fallback - will be skipped
                            if item.get("name"):
                                category_name = item.get("name")
                            elif item.get("category"):
                                category_name = item.get("category")
                            elif item.get("type"):
                                category_name = item.get("type")
                                
                            # Now check and clean up the products list
                            clean_products = []
                            for product in products:
                                # Skip non-dict products
                                if not isinstance(product, dict):
                                    continue
                                    
                                # Make sure each product has a name
                                if not product.get("name"):
                                    if product.get("title"):
                                        product["name"] = product.get("title")
                                    elif product.get("product_name"):
                                        product["name"] = product.get("product_name")
                                        
                                # Make sure each product has a proper reference handler
                                if not product.get("reference_handler") and product.get("plu"):
                                    product["reference_handler"] = product.get("plu")
                                    
                                # Add to clean products
                                clean_products.append(product)
                                
                            # Only create structured menu if we have valid products with real names
                            valid_products = [p for p in clean_products if isinstance(p, dict) and p.get("name")]
                            if valid_products:
                                structured_menu = {
                                    "categories": [
                                        {
                                            "id": f"category-{int(time.time())}",
                                            "name": category_name,
                                            "products": valid_products  # Only use products with real names
                                        }
                                    ]
                                }
                            
                            logger.info(f"[DELIVERECT-MENU] Created menu with {len(clean_products)} products in '{category_name}' category")
                            return process_deliverect_menu(structured_menu, location_id)
                            
            # Last attempt: scan all dictionary items in the list for category or product arrays
            all_products = []
            all_categories = []
            
            for item in deliverect_menu:
                if isinstance(item, dict):
                    # Look for any fields that could be products
                    for key, value in item.items():
                        if isinstance(value, list) and len(value) > 0:
                            if key.lower() in ["products", "items", "menuitems"]:
                                all_products.extend(value)
                            elif key.lower() in ["categories", "category", "sections"]:
                                all_categories.extend(value)
            
            if all_categories:
                logger.info(f"[DELIVERECT-MENU] Found {len(all_categories)} categories in field scan")
                structured_menu = {"categories": all_categories}
                return process_deliverect_menu(structured_menu, location_id)
            
            if all_products:
                logger.info(f"[DELIVERECT-MENU] Found {len(all_products)} products in field scan")
                
                # Clean up products
                clean_products = []
                for product in all_products:
                    # Skip non-dict products
                    if not isinstance(product, dict):
                        continue
                        
                    # Make sure each product has a name
                    if not product.get("name"):
                        if product.get("title"):
                            product["name"] = product.get("title")
                        elif product.get("product_name"):
                            product["name"] = product.get("product_name")
                            
                    # Make sure each product has a proper reference handler
                    if not product.get("reference_handler") and product.get("plu"):
                        product["reference_handler"] = product.get("plu")
                        
                    # Add to clean products
                    clean_products.append(product)
                    
                # Create structured menu with clean products
                structured_menu = {
                    "categories": [
                        {
                            "id": f"category-{int(time.time())}",
                            "name": "Menu Items",
                            "products": clean_products
                        }
                    ]
                }
                logger.info(f"[DELIVERECT-MENU] Created menu with {len(clean_products)} clean products")
                return process_deliverect_menu(structured_menu, location_id)
                
            # If we got here, it's a list we couldn't extract useful data from through standard methods
            # Perform deep recursive inspection to find usable menu data
            try:
                # First attempt: Check for typical Deliverect ID-based format
                # For Deliverect's format where categories have product IDs and products dict has the details
                if isinstance(deliverect_menu, list) and len(deliverect_menu) > 0 and isinstance(deliverect_menu[0], dict):
                    first_item = deliverect_menu[0]
                    # Look for categories with string IDs and a products dictionary
                    if ("categories" in first_item and isinstance(first_item["categories"], list) and 
                        any(isinstance(cat, dict) and 
                            "products" in cat and 
                            isinstance(cat["products"], list) and 
                            all(isinstance(p, str) for p in cat["products"])
                            for cat in first_item["categories"])):
                        
                        # Now look for a products dictionary mapping
                        product_map = {}
                        for key, value in first_item.items():
                            if isinstance(value, dict) and key != "categories":
                                # See if this dict has product-like entries
                                for product_id, product_data in value.items():
                                    if isinstance(product_data, dict) and "name" in product_data:
                                        product_map[product_id] = product_data
                        
                        # If we found product mappings, replace the ID strings
                        if product_map:
                            logger.info(f"[DELIVERECT-MENU] Found {len(product_map)} products in mapping dictionary")
                            
                            # Replace each category's product IDs with actual product objects
                            for category in first_item["categories"]:
                                if isinstance(category, dict) and "products" in category and isinstance(category["products"], list):
                                    real_products = []
                                    for prod_id in category["products"]:
                                        if isinstance(prod_id, str) and prod_id in product_map:
                                            real_products.append(product_map[prod_id])
                                            logger.info(f"[DELIVERECT-MENU] Mapped product ID {prod_id} to {product_map[prod_id].get('name', 'Unnamed')}")
                                    
                                    # Replace string IDs with actual product objects
                                    if real_products:
                                        category["products"] = real_products
                                        
                            # Now process with the enriched data
                            return process_deliverect_menu(first_item, location_id)
                
                # Standard detailed inspection approach
                import json
                detailed_inspection = f"List format - first item keys: "
                
                if len(deliverect_menu) > 0 and isinstance(deliverect_menu[0], dict):
                    detailed_inspection += f"{list(deliverect_menu[0].keys())}"
                    
                    # Check if it has a menu structure - sometimes the categories are nested deeper
                    if "menu" in deliverect_menu[0]:
                        menu_data = deliverect_menu[0]["menu"]
                        if isinstance(menu_data, dict):
                            if "categories" in menu_data:
                                logger.info("[DELIVERECT-MENU] Found nested categories in menu key")
                                return process_deliverect_menu(menu_data, location_id)
                            elif "name" in menu_data and "menuId" in menu_data:
                                # This might be a Deliverect menu format - look deeper for categories
                                for key, value in menu_data.items():
                                    if isinstance(value, list) and len(value) > 0 and key.lower() in ["categories", "category"]:
                                        logger.info(f"[DELIVERECT-MENU] Found nested categories in menu.{key}")
                                        structured_menu = {"categories": value}
                                        return process_deliverect_menu(structured_menu, location_id)
                
                # Second attempt: Deep recursive inspection of all items in the list
                logger.info("[DELIVERECT-MENU] Starting deep recursive inspection of list data")
                
                def recursively_find_products(obj, path="", found_products=None, found_categories=None):
                    """
                    Recursively search through nested data structures to find products and categories
                    """
                    if found_products is None:
                        found_products = []
                    if found_categories is None:
                        found_categories = []
                        
                    # Handle menu structure first - highest priority match
                    if isinstance(obj, dict) and "categories" in obj and isinstance(obj["categories"], list):
                        logger.info(f"[DELIVERECT-MENU] Found menu with categories at {path}")
                        # This is a full menu structure - return it to be processed directly
                        raise ValueError("found_menu")
                        
                    # If it's a list, inspect each item
                    if isinstance(obj, list):
                        for i, item in enumerate(obj):
                            recursively_find_products(item, f"{path}[{i}]", found_products, found_categories)
                    
                    # If it's a dict, check keys and inspect values
                    elif isinstance(obj, dict):
                        # Check if this is a product (has name and price/plu)
                        if "name" in obj and ("price" in obj or "plu" in obj or "id" in obj):
                            logger.info(f"[DELIVERECT-MENU] Found potential product at {path}: {obj.get('name')}")
                            found_products.append(obj)
                        
                        # Check if this is a category (has name and products)
                        if "name" in obj and "products" in obj:
                            if isinstance(obj["products"], list):
                                logger.info(f"[DELIVERECT-MENU] Found potential category at {path}: {obj.get('name')}")
                                found_categories.append(obj)
                            elif obj["products"] and isinstance(obj["products"], str):
                                # Sometimes "products" might be a string due to data format issues
                                # Create a placeholder category with empty products list for later processing
                                cat_copy = obj.copy()
                                cat_copy["products"] = []
                                logger.info(f"[DELIVERECT-MENU] Found category with string products at {path}: {obj.get('name')}")
                                found_categories.append(cat_copy)
                        
                        # Special handling for nested menu structures
                        if "menu" in obj and isinstance(obj["menu"], dict):
                            menu_obj = obj["menu"]
                            # Check if it has categories
                            if "categories" in menu_obj and isinstance(menu_obj["categories"], list):
                                logger.info(f"[DELIVERECT-MENU] Found nested menu.categories at {path}")
                                # Process this menu directly
                                raise ValueError("found_nested_menu")
                            
                        # Special handling for "sections" which is sometimes used instead of "categories"
                        if "sections" in obj and isinstance(obj["sections"], list):
                            # Check if sections look like categories (have name and 'dishes'/'products')
                            for section in obj["sections"]:
                                if isinstance(section, dict) and "name" in section:
                                    # Look for product-like arrays
                                    for key in ["dishes", "products", "items", "menuItems"]:
                                        if key in section and isinstance(section[key], list):
                                            # This is likely a category equivalent
                                            cat_copy = {
                                                "id": section.get("id", f"section-{int(time.time())}"),
                                                "name": section["name"],
                                                "products": section[key]
                                            }
                                            logger.info(f"[DELIVERECT-MENU] Converting section to category: {section['name']}")
                                            found_categories.append(cat_copy)
                        
                        # Process all values recursively
                        for key, value in obj.items():
                            # Special handling for known container keys
                            if key in ["products", "items", "dishes", "menuItems", "menu", "categories", "sections"]:
                                recursively_find_products(value, f"{path}.{key}", found_products, found_categories)
                            # For other dictionary values
                            elif isinstance(value, (dict, list)):
                                recursively_find_products(value, f"{path}.{key}", found_products, found_categories)
                
                # Perform deep inspection on the list
                all_products = []
                all_categories = []
                
                # Process up to 5 items from the list to avoid excessive processing
                items_to_process = deliverect_menu[:5] if len(deliverect_menu) > 5 else deliverect_menu
                
                try:
                    # First try to find any complete menu structures
                    for i, item in enumerate(items_to_process):
                        try:
                            recursively_find_products(item, f"[{i}]", all_products, all_categories)
                        except ValueError as ve:
                            if str(ve) == "found_menu":
                                # Found a complete menu with categories
                                logger.info(f"[DELIVERECT-MENU] Found complete menu structure in item {i}")
                                return process_deliverect_menu(item, location_id)
                            elif str(ve) == "found_nested_menu":
                                # Found a menu with categories in the "menu" field
                                logger.info(f"[DELIVERECT-MENU] Found nested menu structure in item {i}")
                                # Extract the menu from the "menu" field that triggered the exception
                                if "menu" in item and isinstance(item["menu"], dict) and "categories" in item["menu"]:
                                    # Direct nested menu
                                    return process_deliverect_menu(item["menu"], location_id)
                                
                                # It might be several levels deep - perform a targeted search for the menu structure
                                def find_menu_obj(obj):
                                    if isinstance(obj, dict):
                                        if "menu" in obj and isinstance(obj["menu"], dict) and "categories" in obj["menu"]:
                                            return obj["menu"]
                                        # Search all values
                                        for key, value in obj.items():
                                            if isinstance(value, (dict, list)):
                                                result = find_menu_obj(value)
                                                if result:
                                                    return result
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            result = find_menu_obj(item)
                                            if result:
                                                return result
                                    return None
                                
                                # Find the menu object
                                menu_obj = find_menu_obj(item)
                                if menu_obj:
                                    logger.info(f"[DELIVERECT-MENU] Found nested menu structure by targeted search")
                                    return process_deliverect_menu(menu_obj, location_id)
                except Exception as e:
                    logger.warning(f"[DELIVERECT-MENU] Error in initial menu search: {e}")
                
                # If no complete menu was found, reset collected data and try again to collect products/categories
                all_products = []
                all_categories = []
                
                # Try to collect all products and categories
                for i, item in enumerate(items_to_process):
                    try:
                        # Proceed with normal extraction
                        recursively_find_products(item, f"[{i}]", all_products, all_categories)
                    except ValueError:
                        # Skip items that raise ValueError (already handled in the first loop)
                        continue
                    except Exception as e:
                        logger.warning(f"[DELIVERECT-MENU] Error processing item {i}: {e}")
                
                # For complex structures with sections instead of categories
                # Look specifically for sections pattern in items
                for i, item in enumerate(items_to_process):
                    if isinstance(item, dict):
                        # Deep scan for sections -> dishes pattern
                        if "data" in item and isinstance(item["data"], dict):
                            data = item["data"]
                            if "store" in data and isinstance(data["store"], dict):
                                store = data["store"]
                                if "menu" in store and isinstance(store["menu"], dict):
                                    menu = store["menu"]
                                    if "sections" in menu and isinstance(menu["sections"], list):
                                        sections = menu["sections"]
                                        logger.info(f"[DELIVERECT-MENU] Found deep sections pattern in item {i}")
                                        
                                        # Process each section as a category
                                        for section in sections:
                                            if isinstance(section, dict) and "name" in section:
                                                # Look for products in different keys
                                                for products_key in ["dishes", "products", "items", "menuItems"]:
                                                    if products_key in section and isinstance(section[products_key], list):
                                                        # Convert section to category
                                                        cat = {
                                                            "id": section.get("id", f"section-{int(time.time())}"),
                                                            "name": section["name"],
                                                            "products": section[products_key]
                                                        }
                                                        all_categories.append(cat)
                                                        logger.info(f"[DELIVERECT-MENU] Converted section '{section['name']}' to category")
                
                # Use the found data to create a structured menu
                if all_categories:
                    logger.info(f"[DELIVERECT-MENU] Deep inspection found {len(all_categories)} categories")
                    structured_menu = {"categories": all_categories}
                    return process_deliverect_menu(structured_menu, location_id)
                
                elif all_products:
                    logger.info(f"[DELIVERECT-MENU] Deep inspection found {len(all_products)} products")
                    
                    # Filter for only products with real names
                    valid_products = [p for p in all_products if isinstance(p, dict) and p.get("name")]
                    if valid_products:
                        logger.info(f"[DELIVERECT-MENU] {len(valid_products)} valid products with real names")
                        # Create a category with only products that have real names
                        structured_menu = {
                            "categories": [
                                {
                                    "id": f"category-{int(time.time())}",
                                    "name": "",  # No default name
                                    "products": valid_products  # Only include products with real names
                                }
                            ]
                        }
                        return process_deliverect_menu(structured_menu, location_id)
                    else:
                        logger.warning("[DELIVERECT-MENU] No valid products with real names found")
                        # Return empty result since we have no real products
                
                # Third attempt: Look for products with minimal structure requirements
                all_potential_items = []
                
                for i, item in enumerate(deliverect_menu):
                    if isinstance(item, dict):
                        # Check if this could potentially be a menu item
                        # Minimal requirement: has at least a name or identifier
                        if ("name" in item or "title" in item or "id" in item or "plu" in item or 
                            "product_name" in item or "productName" in item):
                            all_potential_items.append(item)
                
                if all_potential_items:
                    logger.info(f"[DELIVERECT-MENU] Found {len(all_potential_items)} potential items with minimal structure")
                    
                    # Create items directly (no categories)
                    result = {
                        "items": [],
                        "modifiers": [],
                        "modifierGroups": [],
                        "name_variants": {}
                    }
                    
                    # Only process items that have an actual name - don't create any synthetic names
                    valid_items = [item for item in all_potential_items if isinstance(item, dict) and 
                                 (item.get("name") or item.get("title") or item.get("product_name") or item.get("productName"))]
                                 
                    # Process each valid item with real data
                    for i, item in enumerate(valid_items):
                        # Determine the actual name from various possible fields, but ONLY use real data
                        item_name = ""
                        if item.get("name"):
                            item_name = item.get("name")
                        elif item.get("title"):
                            item_name = item.get("title")
                        elif item.get("product_name"):
                            item_name = item.get("product_name")
                        elif item.get("productName"):
                            item_name = item.get("productName")
                            
                        # Skip items without a real name
                        if not item_name:
                            continue
                            
                        # Create menu item with real data
                        menu_item = {
                            "id": item.get("id", ""),  # Use empty string as fallback, not synthetic ID
                            "name": item_name,  # Only using real data
                            "price": 0.0,  # Will be updated below if available
                            "available": item.get("available", True),
                            "snoozed": item.get("snoozed", False),
                            "description": item.get("description", "")
                        }
                        
                        # Set price if available
                        price_value = item.get("price", 0)
                        if isinstance(price_value, (int, float)):
                            menu_item["price"] = price_value / 100 if price_value > 100 else price_value
                        
                        # Set reference handler with priority
                        if item.get("plu"):
                            menu_item["reference_handler"] = item.get("plu")
                        elif item.get("id"):
                            menu_item["reference_handler"] = item.get("id")
                        elif menu_item["name"]:
                            import re
                            clean_name = re.sub(r'[^a-zA-Z0-9]', '', menu_item["name"])
                            if clean_name:
                                menu_item["reference_handler"] = clean_name[:15]
                            else:
                                menu_item["reference_handler"] = f"ITEM-{i}"
                        else:
                            menu_item["reference_handler"] = f"ITEM-{i}"
                            
                        result["items"].append(menu_item)
                    
                    # Generate name variants for all items
                    for item in result["items"]:
                        try:
                            add_name_variants(item["name"], result["name_variants"])
                        except Exception as e:
                            logger.warning(f"[DELIVERECT-MENU] Error adding name variants for {item['name']}: {e}")
                            
                    logger.info(f"[DELIVERECT-MENU] Created menu with {len(result['items'])} items from minimal data")
                    return result
                
                logger.warning(f"[DELIVERECT-MENU] Could not extract valid menu data from list after deep inspection. {detailed_inspection}")
            except Exception as detailed_e:
                logger.error(f"[DELIVERECT-MENU] Error in deep inspection: {detailed_e}")
                
            # Create empty result as fallback
            return result
        except Exception as e:
            logger.error(f"[DELIVERECT-MENU] Error attempting data extraction from list: {e}")
            # Return an empty menu when all extraction methods fail
            return result
    
    # At this point we either have a dictionary or need to create a valid one
    if not isinstance(deliverect_menu, dict):
        logger.error(f"[DELIVERECT-MENU] Invalid menu data type: {type(deliverect_menu)}, creating empty structure")
        deliverect_menu = {"categories": []}
    
    # Create/extract categories
    categories = []
    if "categories" in deliverect_menu:
        categories_data = deliverect_menu.get("categories", [])
        if isinstance(categories_data, list):
            categories = categories_data
        else:
            logger.warning(f"[DELIVERECT-MENU] Categories is not a list: {type(categories_data)}")
    
    # Track IDs to avoid duplicates
    processed_item_ids = set()
    
    # Create name variants dictionary for easier item lookups
    name_variants = {}
    
    # Check for products at the top level as well (some Deliverect data has this format)
    root_products = deliverect_menu.get("products", [])
    if isinstance(root_products, list) and len(root_products) > 0:
        logger.info(f"[DELIVERECT-MENU] Found {len(root_products)} products at the root level")
        # Only include products with actual names
        valid_products = [p for p in root_products if isinstance(p, dict) and p.get("name")]
        if valid_products:
            logger.info(f"[DELIVERECT-MENU] Found {len(valid_products)} valid products with names at root level")
            # Create a category for these products
            root_category = {
                "id": "root_products",
                "name": "",  # No default name
                "products": valid_products  # Only include products with real names
            }
            categories.append(root_category)
    
    logger.info(f"[DELIVERECT-MENU] Processing {len(categories)} categories")
    
    # Process each category
    for category in categories:
        # Ensure category is a dictionary
        if not isinstance(category, dict):
            logger.warning(f"[DELIVERECT-MENU] Category is not a dictionary: {type(category)}")
            continue
            
        cat_id = category.get("id", f"cat-{len(processed_item_ids)}")
        cat_name = category.get("name", "Uncategorized")
        products = category.get("products", [])
        
        # Special handling for products field
        if not products:
            # Skip empty products
            logger.warning(f"[DELIVERECT-MENU] Category {cat_name} has empty products")
            continue
        elif isinstance(products, str):
            # Sometimes 'products' might be a string due to data format issues
            logger.warning(f"[DELIVERECT-MENU] Products in category {cat_name} is a string: '{products[:30]}...'")
            try:
                # Try to parse it as JSON if it looks like a JSON string
                if products.strip().startswith('[') and products.strip().endswith(']'):
                    import json
                    parsed_products = json.loads(products)
                    if isinstance(parsed_products, list):
                        logger.info(f"[DELIVERECT-MENU] Successfully parsed products string as JSON array with {len(parsed_products)} items")
                        products = parsed_products
                    else:
                        logger.warning("[DELIVERECT-MENU] Products JSON string did not parse to a list")
                        products = []
                else:
                    # Do not create synthetic products
                    logger.warning(f"[DELIVERECT-MENU] Products in category {cat_name} is a string, not using synthetic data")
                    products = []  # Empty products list instead of creating synthetic data
            except Exception as e:
                logger.error(f"[DELIVERECT-MENU] Error handling string products: {e}")
                products = []
        elif not isinstance(products, list):
            # Handle other non-list types
            logger.warning(f"[DELIVERECT-MENU] Products in category {cat_id} is not a list: {type(products)}")
            try:
                # Try to convert to a list if possible
                if isinstance(products, dict):
                    # If it's a dict, it might be a single product or a container
                    if "name" in products or "id" in products or "plu" in products:
                        # It looks like a single product
                        products = [products]
                        logger.info(f"[DELIVERECT-MENU] Converted dict to single-product list in category {cat_name}")
                    else:
                        # It might be a container - check if any values are lists or dicts
                        product_candidates = []
                        for key, value in products.items():
                            if isinstance(value, list):
                                # This might be a list of products
                                product_candidates.extend(value)
                            elif isinstance(value, dict) and ("name" in value or "id" in value):
                                # This might be a single product
                                product_candidates.append(value)
                        
                        if product_candidates:
                            products = product_candidates
                            logger.info(f"[DELIVERECT-MENU] Extracted {len(products)} products from dict in category {cat_name}")
                        else:
                            products = []
                else:
                    # For other types, create an empty list
                    products = []
            except Exception as e:
                logger.error(f"[DELIVERECT-MENU] Error converting products to list: {e}")
                products = []
        
        # Process each product in this category
        for i, product in enumerate(products):
            # ONLY process if we have an actual product dictionary with a real name
            # Skip anything that doesn't have direct Deliverect data
            if not isinstance(product, dict) or not product.get("name"):
                continue  # Skip this item entirely rather than creating synthetic data
                
            # Create a new product record ONLY with data directly from Deliverect
            menu_item = {
                "id": product.get("id", ""),  # Only use real product ID
                "name": product.get("name", ""),  # Only use real product name
                "price": 0.0,  # Will be set from product data below
                "reference_handler": "",  # Will be set from PLU below
                "description": product.get("description", ""),
                "category": cat_name,
                "categoryId": cat_id,
                "available": product.get("available", True),
                "snoozed": product.get("snoozed", False)
            }
            
            # Handle different product types
            if isinstance(product, dict):
                # It's a normal dictionary product - extract fields
                prod_id = product.get("id")
                prod_name = product.get("name")
                
                # Skip duplicates
                if prod_id and prod_id in processed_item_ids:
                    continue
                
                if prod_id:
                    processed_item_ids.add(prod_id)
                    menu_item["id"] = prod_id
                
                # Process name (ensuring it's a string)
                if prod_name is not None:
                    if isinstance(prod_name, str):
                        menu_item["name"] = prod_name
                    else:
                        menu_item["name"] = str(prod_name)
                elif product.get("title"):
                    menu_item["name"] = product.get("title")
                
                # Get PLU (reference_handler)
                # PLU is the most important reference - this is what Deliverect requires 
                if product.get("plu"):
                    menu_item["reference_handler"] = product.get("plu")
                # If no PLU, try using product ID, which may still work with Deliverect
                elif product.get("id"):
                    menu_item["reference_handler"] = product.get("id")
                # If neither, use the product name to create a stable reference
                elif product.get("name"):
                    # Create a reference based on name - ensures consistency
                    import re
                    # Clean the name for reference use
                    clean_name = re.sub(r'[^a-zA-Z0-9]', '', product.get("name"))
                    if clean_name:
                        menu_item["reference_handler"] = f"{clean_name[:15]}"
                    else:
                        # Last resort
                        menu_item["reference_handler"] = f"PROD-{i}"
                
                # Get price (converting from cents if needed)
                price_value = product.get("price", 0)
                if isinstance(price_value, (int, float)):
                    menu_item["price"] = price_value / 100 if price_value > 100 else price_value
                
                # Get description
                if product.get("description"):
                    menu_item["description"] = product.get("description")
                
                # Get availability
                if "available" in product:
                    menu_item["available"] = bool(product.get("available"))
                    menu_item["snoozed"] = not menu_item["available"]
                
                # Get image URL
                if product.get("imageUrl"):
                    menu_item["imageUrl"] = product.get("imageUrl")
                
                # Process availability schedule
                if "availability" in product:
                    try:
                        menu_item["availabilities"] = convert_availability(product.get("availability", []))
                    except Exception as e:
                        logger.warning(f"[DELIVERECT-MENU] Error converting availability: {e}")
                elif "availabilities" in product:
                    try:
                        menu_item["availabilities"] = convert_availability(product.get("availabilities", []))
                    except Exception as e:
                        logger.warning(f"[DELIVERECT-MENU] Error converting availabilities: {e}")
                
                # Process modifier groups
                mod_groups = product.get("modifierGroups", [])
                if isinstance(mod_groups, list):
                    mod_group_ids = []
                    for group in mod_groups:
                        if isinstance(group, dict) and group.get("id"):
                            mod_group_ids.append(group.get("id"))
                    if mod_group_ids:
                        menu_item["modifierGroups"] = mod_group_ids
            
            elif isinstance(product, str):
                # It's a string - try to extract product data from it
                import re
                import json
                
                # Try to parse JSON first if it looks like a JSON string
                if product.strip().startswith('{') and product.strip().endswith('}'):
                    try:
                        parsed = json.loads(product)
                        if isinstance(parsed, dict):
                            # If parsing worked, process this as a new dictionary product
                            if parsed.get("name"):
                                menu_item["name"] = parsed.get("name")
                            if parsed.get("id"):
                                menu_item["id"] = parsed.get("id")
                            if parsed.get("plu"):
                                menu_item["reference_handler"] = parsed.get("plu")
                            if "price" in parsed and isinstance(parsed["price"], (int, float)):
                                menu_item["price"] = parsed["price"] / 100 if parsed["price"] > 100 else parsed["price"]
                            if parsed.get("description"):
                                menu_item["description"] = parsed.get("description")
                            logger.info(f"[DELIVERECT-MENU] Successfully parsed string product as JSON")
                    except Exception:
                        # If JSON parsing fails, continue with regex approach
                        pass
                
                # Try regex patterns if JSON parsing failed or string isn't JSON
                if menu_item["name"] == f"Item {len(result['items']) + 1}":  # Only if we haven't set a name yet
                    # Multiple regex patterns for different string formats
                    name_patterns = [
                        r'name["\']?\s*[:=]\s*["\']([^"\']+)["\']',  # name="Product Name"
                        r'name=([^,\s]+)',                            # name=ProductName
                        r'Product.*?name=["\']?([^"\',\s]+)["\']?',   # Product...name="Name"
                        r'name\W+([a-zA-Z0-9 ]+)',                    # name: Product
                        r'product_name["\']?\s*[:=]\s*["\']([^"\']+)["\']',  # product_name="Name"
                        r'title["\']?\s*[:=]\s*["\']([^"\']+)["\']'   # title="Name"
                    ]
                    
                    # Try each pattern
                    for pattern in name_patterns:
                        match = re.search(pattern, product)
                        if match:
                            menu_item["name"] = match.group(1)
                            break
                    
                    # Try to extract other fields with regex
                    id_match = re.search(r'id["\']?\s*[:=]\s*["\']?([^"\',\s]+)["\']?', product)
                    if id_match:
                        menu_item["id"] = id_match.group(1)
                        
                    plu_match = re.search(r'plu["\']?\s*[:=]\s*["\']?([^"\',\s]+)["\']?', product)
                    if plu_match:
                        menu_item["reference_handler"] = plu_match.group(1)
                    
                    price_match = re.search(r'price["\']?\s*[:=]\s*(\d+)', product)
                    if price_match:
                        try:
                            price = int(price_match.group(1))
                            menu_item["price"] = price / 100 if price > 100 else price
                        except (ValueError, TypeError):
                            pass
            
            else:
                # It's some other type - create a generic placeholder
                menu_item["name"] = f"Item Type {type(product).__name__} {i+1}"
                menu_item["description"] = f"Auto-generated from non-standard data type: {type(product).__name__}"
            
            # Add the processed item to our results - only if it has a meaningful name
            if menu_item["name"] != f"Item {len(result['items']) + 1}" and menu_item["name"].strip():
                # Capture the original name for logging
                original_name = menu_item["name"]
                result["items"].append(menu_item)
                
                # Add name variants for easier search
                try:
                    logger.info(f"[DELIVERECT-MENU] Adding name variants for: '{menu_item['name']}'")
                    add_name_variants(menu_item["name"], name_variants)
                except Exception as e:
                    logger.warning(f"[DELIVERECT-MENU] Error adding name variants for '{original_name}': {e}")
                    # Add at least the basic variant
                    try:
                        name_lower = menu_item["name"].lower()
                        name_variants[name_lower] = menu_item["name"]
                        logger.info(f"[DELIVERECT-MENU] Added basic variant: '{name_lower}' -> '{menu_item['name']}'")
                    except Exception as basic_e:
                        logger.warning(f"[DELIVERECT-MENU] Even basic variant failed: {basic_e}")
            elif len(result['items']) == 0:
                # If it's our first item and it has a generic name, try to use a better name from the category
                if cat_name and cat_name != "Uncategorized":
                    menu_item["name"] = f"{cat_name} Item"
                    logger.info(f"[DELIVERECT-MENU] Using category name for first item: '{menu_item['name']}'")
                result["items"].append(menu_item)
                
                # Add name variants for the category-based name
                try:
                    add_name_variants(menu_item["name"], name_variants)
                except Exception as e:
                    logger.warning(f"[DELIVERECT-MENU] Error adding name variants: {e}")
    
    # Process modifier groups
    modifier_groups_data = deliverect_menu.get("modifierGroups", {})
    if isinstance(modifier_groups_data, dict):
        for group_id, group_data in modifier_groups_data.items():
            if not isinstance(group_data, dict):
                logger.warning(f"[DELIVERECT-MENU] Modifier group data for {group_id} is not a dictionary: {type(group_data)}")
                continue
                
            # Create the group structure
            group = {
                "id": group_id,
                "name": group_data.get("name", f"Group {group_id}"),
                "minAllowed": group_data.get("min", 0),
                "maxAllowed": group_data.get("max", 999),
                "modifiers": []
            }
            
            # Add modifiers to the group
            modifiers = group_data.get("subProducts", [])
            if isinstance(modifiers, list):
                for mod in modifiers:
                    if isinstance(mod, str):
                        group["modifiers"].append(mod)
                    elif isinstance(mod, dict) and "id" in mod:
                        group["modifiers"].append(mod["id"])
            
            # Add the group to the result
            result["modifierGroups"].append(group)
    else:
        logger.warning(f"[DELIVERECT-MENU] modifierGroups is not a dictionary: {type(modifier_groups_data)}")
    
    # Process modifiers
    modifiers_data = deliverect_menu.get("modifiers", {})
    if isinstance(modifiers_data, dict):
        for modifier_id, modifier_data in modifiers_data.items():
            if not isinstance(modifier_data, dict):
                logger.warning(f"[DELIVERECT-MENU] Modifier data for {modifier_id} is not a dictionary: {type(modifier_data)}")
                continue
                
            # Create the modifier record
            try:
                price = modifier_data.get("price", 0)
                if isinstance(price, (int, float)):
                    price = price / 100 if price > 100 else price
                else:
                    price = 0
                
                modifier = {
                    "id": modifier_id,
                    "name": modifier_data.get("name", f"Modifier {modifier_id}"),
                    "price": price,
                    "available": modifier_data.get("available", True),
                    "snoozed": not modifier_data.get("available", True),
                    "reference_handler": modifier_data.get("plu", "")
                }
                
                # Add the modifier to the result
                result["modifiers"].append(modifier)
            except Exception as e:
                logger.error(f"[DELIVERECT-MENU] Error creating modifier {modifier_id}: {e}")
    else:
        logger.warning(f"[DELIVERECT-MENU] modifiers is not a dictionary: {type(modifiers_data)}")
    
    # Add name variants to the result
    result["name_variants"] = name_variants
    
    # Log summary
    logger.info(f"[DELIVERECT-MENU] Processed: {len(result['items'])} items, " + 
                f"{len(result['modifiers'])} modifiers, " + 
                f"{len(result['modifierGroups'])} modifier groups, " + 
                f"{len(name_variants)} name variants")
    
    return result

# Empty menu creation function removed

def add_name_variants(item_name, variants_dict):
    """
    Add standard name variants for an item to make it easier to find
    through voice search.
    
    Args:
        item_name: The item name to generate variants for
        variants_dict: Dictionary to update with variants
    """
    # Log args for debugging
    logger.info(f"[NAME-VARIANTS] Adding variants for: '{item_name}', type: {type(item_name)}")
    
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
        
    # Convert to lowercase for consistent matching and remove special characters
    import re
    item_name_clean = re.sub(r'[^\w\s]', ' ', item_name.lower())
    item_name_clean = re.sub(r'\s+', ' ', item_name_clean).strip()
    item_name_lower = item_name.lower().strip()
    
    # Add the base names
    variants_dict[item_name_lower] = item_name
    if item_name_clean != item_name_lower:
        variants_dict[item_name_clean] = item_name
        logger.info(f"[NAME-VARIANTS] Added cleaned variant: '{item_name_clean}'")
    
    # Split into words
    words = item_name_clean.split()
    
    # Add without the first word (e.g., "Spicy Tuna Roll" -> "Tuna Roll")
    if len(words) > 2:
        without_first = ' '.join(words[1:])
        variants_dict[without_first] = item_name
        logger.info(f"[NAME-VARIANTS] Added without first word: '{without_first}'")
    
    # Add without the last word (e.g., "Spicy Tuna Roll" -> "Spicy Tuna")
    if len(words) > 2:
        without_last = ' '.join(words[:-1])
        variants_dict[without_last] = item_name
        logger.info(f"[NAME-VARIANTS] Added without last word: '{without_last}'")
    
    # For multi-word items, add key words as variants
    for word in words:
        # Only filter out the most common English articles, conjunctions, and prepositions
        # Don't filter by length - preserve all product words regardless of length
        if word not in ["a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", "from"]:
            variants_dict[word] = item_name
            logger.info(f"[NAME-VARIANTS] Added keyword variant: '{word}'")
    
    # No hard-coded food categories or static keyword alternatives
    # Only use the actual item name and its direct variants
    
    return variants_dict
    
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
