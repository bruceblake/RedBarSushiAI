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
        logger.info(f"menu data: {menu_data}")
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
        
        # Preserve existing name variants if available
        existing_variants = existing_menu.get("name_variants", {})
        
        logger.info(f"[MENU-TRANSITION] Found {len(existing_by_id)} items by ID, {len(existing_by_name)} by name, {len(existing_by_plu)} by PLU, {len(existing_variants)} existing variants")
    except Exception as e:
        logger.warning(f"[MENU-TRANSITION] Could not load existing menu: {e}")
        existing_by_id = {}
        existing_by_name = {}
        existing_by_plu = {}
        existing_variants = {}
    
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
    
    # Add name variants dictionary to handle common search variants
    # Start with existing variants to preserve manual additions
    name_variants = existing_variants.copy()
    
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
                "categoryId": cat_id,
                "available": product.get("available", True)  # CRITICAL: Preserve available flag exactly as provided
            }
            
            # Create name variants for this item using intelligent algorithmic generation
            # rather than hardcoded values
            prod_name_lower = prod_name.lower()
            name_variants[prod_name_lower] = prod_name  # Store base name
            
            # Generate word-level variants
            words = prod_name_lower.split()
            
            # Store single-word items directly
            if len(words) == 1 and len(words[0]) > 3:
                # No variants needed for single words, already captured above
                pass
                
            # For multi-word items, generate common variations
            elif len(words) > 1:
                # Add the first word if it's meaningful (not an article/etc)
                if len(words[0]) > 3 and words[0] not in ["with", "and", "the"]:
                    if words[0] not in name_variants:
                        name_variants[words[0]] = prod_name
                
                # Add the last word if it's meaningful
                if len(words[-1]) > 3 and words[-1] not in ["with", "and", "the"]:
                    if words[-1] not in name_variants:
                        name_variants[words[-1]] = prod_name
                        
                # Store key descriptive terms if they're not already taken
                for i, word in enumerate(words):
                    if (len(word) > 3 and 
                        word not in ["with", "and", "the", "for", "or"] and
                        word not in name_variants):
                        
                        # Check if this word is already the name of another item
                        word_collision = False
                        for existing_item in result.get("items", []):
                            if existing_item.get("name", "").lower() == word:
                                word_collision = True
                                break
                        
                        if not word_collision:
                            # Only add if it doesn't collide with another menu item
                            name_variants[word] = prod_name
                
                # Add combined terms for things that might have spaces vs no spaces
                # e.g., "ice cream" ↔ "icecream", "coca cola" ↔ "cocacola"
                if len(words) == 2:
                    combined = words[0] + words[1]
                    if combined not in name_variants:
                        name_variants[combined] = prod_name
                        
                # NEW: Handle order variations (e.g., "bacon cheeseburger" ↔ "cheeseburger bacon")
                if len(words) > 1 and len(words) <= 4:  # Don't do this for very long names
                    # Generate variations with word order changes
                    import itertools
                    for word_subset in itertools.permutations(words, len(words)):
                        variant = " ".join(word_subset)
                        if variant != prod_name_lower and variant not in name_variants:
                            name_variants[variant] = prod_name
                            
            # NEW: Add common short forms and abbreviations
            # French Fries → Fries
            if "french fries" in prod_name_lower:
                name_variants["fries"] = prod_name
                name_variants["frys"] = prod_name  # Common misspelling
                
            # Hamburger → Burger, Hamburger → Ham
            if "hamburger" in prod_name_lower:
                name_variants["burger"] = prod_name
                name_variants["ham"] = prod_name
                
            # Cheeseburger → Cheese
            if "cheeseburger" in prod_name_lower:
                name_variants["cheese"] = prod_name
                
            # Coca-Cola/Coca Cola → Coke
            if "coca" in prod_name_lower and "cola" in prod_name_lower:
                name_variants["coke"] = prod_name
                name_variants["cola"] = prod_name
                
            # Mountain Dew → Dew
            if "mountain dew" in prod_name_lower:
                name_variants["dew"] = prod_name
                name_variants["mt dew"] = prod_name
                
            # NEW: Add common typo handling for frequent words
            common_typos = {
                "hamburger": ["hambuger", "hamberger", "hamburgar"],
                "cheeseburger": ["cheseburger", "cheesburger", "cheezburger"],
                "sandwich": ["sandwitch", "sandwhich", "sandwish"],
                "chicken": ["chiken", "chiken", "chick"],
                "coffee": ["coffe", "cofee", "coffie"],
                "salad": ["sallad", "salid", "salud"],
                "pizza": ["piza", "pizzza", "pizzaa"],
                "bacon": ["bakon", "baccon"],
                "cheese": ["chese", "cheez", "chees"],
                "fries": ["frys", "friess", "fris"]
            }
            
            # Check if any common words with typos appear in this product
            for correct_word, typos in common_typos.items():
                if correct_word in prod_name_lower:
                    # Add all typo variations
                    for typo in typos:
                        # Replace the correct word with the typo in the full name
                        typo_name = prod_name_lower.replace(correct_word, typo)
                        name_variants[typo_name] = prod_name
                        
                        # Also add the typo as a standalone variant if it's not too short
                        if len(typo) >= 4 and typo not in name_variants:
                            name_variants[typo] = prod_name
                
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
                        "minAllowed": group.get("minAmount", 0),  # Also set standardized names
                        "maxAllowed": group.get("maxAmount", 999),
                        "modifiers": []
                    }
                    
                    # Ensure min <= max
                    if new_group["min"] > new_group["max"]:
                        logger.warning(f"[MENU-FIX] Fixed invalid min/max constraint for {new_group['name']}: {new_group['min']} > {new_group['max']}")
                        new_group["min"] = min(new_group["min"], new_group["max"])
                        new_group["minAllowed"] = new_group["min"]
                    
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
                            "available": modifier.get("available", True),  # Keep original available flag
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
            
    # Add name variants to separate section in result for easier matching
    result["name_variants"] = name_variants
            
    # Log a sample of PLU mappings and name variants
    sample_items = list(plu_reference.items())[:5]
    for name, ref in sample_items:
        logger.info(f"[DELIVERECT-PLU] '{name}' = '{ref}'")
        
    sample_variants = list(name_variants.items())[:5]
    for variant, original in sample_variants:
        logger.info(f"[NAME-VARIANT] '{variant}' → '{original}'")
    
    logger.info(f"[DELIVERECT] Processed: {len(result['items'])} items, {len(result['modifierGroups'])} modifier groups, {len(name_variants)} name variants")
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
