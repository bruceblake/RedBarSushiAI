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

# Cache variables - optimized for memory usage
_menu_cache = None
_last_refresh_time = 0
_cache_duration = 900  # 15 minutes cache duration for menu data in production
# Use a shorter duration in development
if os.environ.get('FLASK_ENV') == 'development':
    _cache_duration = 60  # 1 minute for development

# Toggle to use redbar_menu_data.json instead of menu_data.json
# Set this to True to use redbar_menu_data.json
USE_REDBAR_MENU = os.environ.get('USE_REDBAR_MENU', 'false').lower() == 'true'

# Default paths - ensure they work in production environment
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT_PARENT = os.path.dirname(APP_ROOT)

# Detect if we're running in a Docker environment
IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
if IN_DOCKER:
    logger.info("Docker environment detected")

# Docker root directory for production runs
DOCKER_ROOT = '/app'
DOCKER_MENU_PATH = os.path.join(DOCKER_ROOT, 'menu_data.json')

# Determine which menu file to use based on the toggle
DEFAULT_MENU_FILENAME = 'redbar_menu_data.json' if USE_REDBAR_MENU else 'menu_data.json'

# Log the menu file choice
logger.info(f"Menu selection: Using {'redbar_menu_data.json' if USE_REDBAR_MENU else 'menu_data.json'}")

# Define all possible menu file locations to check
POSSIBLE_MENU_PATHS = [
    # 1. Environment variable (highest priority)
    os.getenv('MENU_FILE_PATH'),
    
    # 2. Docker container paths (prioritized when in Docker)
    os.path.join(DOCKER_ROOT, DEFAULT_MENU_FILENAME),
    '/var/task/' + DEFAULT_MENU_FILENAME,  # Alternate container path
    
    # 3. Traditional deployment paths
    '/app/' + DEFAULT_MENU_FILENAME,      
    # 4. App paths
    os.path.join(APP_ROOT, DEFAULT_MENU_FILENAME),
    os.path.join(APP_ROOT_PARENT, DEFAULT_MENU_FILENAME),
    
    # 5. Current directory and alternatives 
    os.path.join(os.getcwd(), DEFAULT_MENU_FILENAME),
    
    # 6. Always include both menu files as fallbacks
    os.path.join(os.getcwd(), 'menu_data.json'),
    os.path.join(os.getcwd(), 'redbar_menu_data.json'),
]

def find_menu_file_path():
    """
    Check all possible locations for menu file and return the first one that exists.
    """
    for path in POSSIBLE_MENU_PATHS:
        if path and os.path.exists(path) and os.path.isfile(path):
            return path
    
    # No file found
    return None

# Determine the actual menu file path
MENU_FILE_PATH = find_menu_file_path()
if not MENU_FILE_PATH:
    # If Docker environment, default to Docker path
    if os.path.exists(DOCKER_ROOT):
        MENU_FILE_PATH = os.path.join(DOCKER_ROOT, DEFAULT_MENU_FILENAME)
        logger.warning(f"No menu file found, defaulting to Docker path: {MENU_FILE_PATH}")
    else:
        # If no file exists, default to current directory
        MENU_FILE_PATH = os.path.join(os.getcwd(), DEFAULT_MENU_FILENAME)
        logger.warning(f"No menu file found, defaulting to: {MENU_FILE_PATH}")
                      
# Ensure backup folder is in a writable location
# If in a read-only environment, use /tmp
BACKUP_FOLDER = os.access(os.path.dirname(MENU_FILE_PATH), os.W_OK) and os.path.join(os.path.dirname(MENU_FILE_PATH), 'backups') or '/tmp/redbar_backups'

# Log where we're looking for files
logger.info(f"Using menu file path: {MENU_FILE_PATH}")
logger.info(f"Using backup folder: {BACKUP_FOLDER}")

def write_menu_file(menu_data: Dict[str, Any], file_path: Optional[str] = None, location_id: Optional[str] = None) -> bool:
    """
    Write menu data to the configured file path.
    
    Args:
        menu_data: The menu data to write
        file_path: The file path to write to (optional)
        location_id: The location ID to write to (optional)
        
    Returns:
        bool: True if write was successful, False otherwise
    """
    if file_path is None:
        file_path = MENU_FILE_PATH
        
    # Create a backup before writing
    try:
        # Create backup directory if it doesn't exist
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        
        # Check if file exists first
        if os.path.exists(file_path):
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            backup_file = os.path.join(BACKUP_FOLDER, f'menu_backup_{timestamp}.json')
            shutil.copy2(file_path, backup_file)
            logger.info(f"Created backup at {backup_file}")
    except Exception as e:
        logger.warning(f"Could not create backup: {e}")
    
    # Write the new file
    try:
        with open(file_path, 'w') as file:
            json.dump(menu_data, file, indent=2)
        
        logger.info(f"Successfully wrote menu data to {file_path}")
        
        # Clear cache to force reload
        global _menu_cache, _last_refresh_time
        _menu_cache = None
        _last_refresh_time = 0
        
        return True
    except Exception as e:
        logger.error(f"Error writing menu file: {e}")
        return False

def create_empty_menu():
    """Create an empty menu structure when no menu file is found.
    
    IMPORTANT: We don't create default items anymore - all menu data must come from Deliverect.
    Only using an empty structure as a placeholder until real data arrives.
    """
    logger.warning("Creating empty menu structure - NO DEFAULT ITEMS")
    
    # Log where the empty menu will likely be stored
    if os.path.exists(DOCKER_ROOT):
        logger.info(f"Running in Docker environment, menu will be stored at {DOCKER_MENU_PATH}")
    else:
        logger.info(f"Running in standard environment, menu will be stored at {MENU_FILE_PATH}")
    
    return {
        "items": [],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {}
    }

def create_default_menu():
    """Create a default menu to use when no menu file is available."""
    # For now, just use the empty menu as we don't want default items
    return create_empty_menu()

def load_menu_data(force_refresh=False):
    """
    Load menu data from the file, with caching to avoid frequent reads.
    
    Args:
        force_refresh: If True, bypass cache and load directly from file
        
    Returns:
        dict: The menu data
    """
    global _menu_cache, _last_refresh_time
    current_time = time.time()
    
    # Check if we have cached data that's still fresh
    if _menu_cache is not None and not force_refresh:
        time_since_refresh = current_time - _last_refresh_time
        if time_since_refresh < _cache_duration:
            return _menu_cache
    
    # Determine the path to the menu file, with fallbacks
    file_path = find_menu_file_path()
    
    if not file_path:
        logger.warning("No menu file found. Creating an empty menu structure.")
        empty_menu = create_empty_menu()
        
        # Update cache
        _menu_cache = empty_menu
        _last_refresh_time = current_time
        
        return empty_menu
    
    logger.info(f"Loading menu data from {file_path}")
    
    try:
        with open(file_path, 'r') as file:
            menu_data = json.load(file)
        
        # Validate menu data structure
        if 'items' not in menu_data:
            logger.warning("Menu data does not contain 'items' key")
            
            # Check if this is a Deliverect-format file that needs processing
            if 'channels' in menu_data or 'products' in menu_data:
                logger.info("Found Deliverect-format menu data - needs processing")
                
                # Import in the function to avoid circular imports
                from app.utils.deliverect import process_deliverect_menu
                menu_data = process_deliverect_menu(menu_data)
                logger.info("Processed Deliverect menu data")
            
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
            logger.debug(f"Sample item: {item.get('name')} - {item.get('price')}")
        
        logger.info(f"Loaded {items_count} total items, {available_count} currently available")
        
        return menu_data
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in menu file {file_path}")
        # Return empty menu structure - NO DEFAULT ITEMS
        empty_menu = create_empty_menu()
        
        # Update cache with empty menu
        _menu_cache = empty_menu
        _last_refresh_time = current_time
        
        return empty_menu
    except Exception as e:
        logger.error(f"Error loading menu data: {e}")
        # Return empty menu structure - NO DEFAULT ITEMS
        empty_menu = create_empty_menu()
        
        # Update cache to avoid repeat errors
        _menu_cache = empty_menu
        _last_refresh_time = current_time
        
        # Try to save it for future use
        try:
            write_menu_file(empty_menu, os.path.join(os.getcwd(), 'menu_data.json'))
            logger.info("Saved empty menu structure after loading error")
        except Exception:
            pass
            
        return empty_menu

def find_menu_item_by_name(item_name: str, check_availability: bool = False) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name, with fuzzy matching as needed.
    
    Args:
        item_name: The name of the item to find
        check_availability: If True, only return items that are available
        
    Returns:
        dict or None: The menu item if found, None otherwise
    """
    if not item_name:
        return None
        
    logger.info(f"[MENU-LOOKUP] Looking for item: '{item_name}'")
    
    # Normalize the item name
    item_name_lower = item_name.lower().strip()
    logger.debug(f"[MENU-LOOKUP] Normalized to: '{item_name_lower}'")
    
    # Get menu data
    menu_data = load_menu_data()
    name_variants = menu_data.get("name_variants", {})
    
    # Add some debug logging
    logger.debug(f"[MENU-LOOKUP] Checking against {len(name_variants)} name variants")
    logger.debug(f"[MENU-LOOKUP] Available variants: {list(name_variants.keys())[:5]}...")
    
    # First try direct match against a variant
    if item_name_lower in name_variants:
        actual_name = name_variants[item_name_lower]
        logger.info(f"[MENU-LOOKUP] Found direct name variant match: '{item_name_lower}' → '{actual_name}'")
        
        # Look up the item
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == actual_name.lower():
                # Verify this item is available if required
                if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                    logger.info(f"[MENU-LOOKUP] Found matching menu item: {item.get('name')}")
                    return item
                else:
                    logger.warning(f"[MENU-LOOKUP] Found match '{item.get('name')}' but item is unavailable/snoozed")
                    return None
    
    # Try direct match against menu items
    for item in menu_data.get("items", []):
        if item.get("name", "").lower() == item_name_lower:
            # Verify this item is available if required
            if not check_availability or (item.get("available", True) and not item.get("snoozed", False)):
                logger.info(f"[MENU-LOOKUP] Found direct menu item match: {item.get('name')}")
                return item
            else:
                logger.warning(f"[MENU-LOOKUP] Found direct match '{item.get('name')}' but item is unavailable/snoozed")
                return None
    
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
        timestamp: The UTC timestamp string to parse (ISO format)
        
    Returns:
        datetime or None: The parsed datetime, or None if timestamp is invalid/None
    """
    if not timestamp:
        return None
        
    try:
        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        # Fallback method
        try:
            from dateutil import parser
            return parser.parse(timestamp)
        except (ValueError, ImportError):
            logger.error(f"Failed to parse timestamp: {timestamp}")
            return None

def is_item_snoozed_timebased(item: Dict[str, Any]) -> bool:
    """
    Check if an item is snoozed based on its snooze timestamps.
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if the item is currently snoozed, False otherwise
    """
    # If item doesn't have snoozed flag, it's not snoozed
    if not item.get('snoozed', False):
        return False
        
    # Check if snoozed timestamp is in the future
    snooze_until = item.get('snoozeUntil')
    if not snooze_until:
        # If no timestamp, use the boolean snoozed flag
        return item.get('snoozed', False)
        
    # Parse the timestamp
    snooze_datetime = parse_utc_timestamp(snooze_until)
    if not snooze_datetime:
        # If we can't parse it, use the boolean flag
        return item.get('snoozed', False)
        
    # Check if current time is past the snooze time
    now = datetime.now(timezone.utc)
    return now < snooze_datetime

def is_item_snoozed(item: Dict[str, Any]) -> bool:
    """
    Check if an item is snoozed (composite check).
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if the item is currently snoozed, False otherwise
    """
    # Simple boolean check first
    boolean_snoozed = item.get('snoozed', False)
    
    # If not snoozed by boolean, check time-based snooze
    if not boolean_snoozed:
        return False
        
    # If snoozed, check if there's a time-based condition
    return is_item_snoozed_timebased(item)

def is_time_in_range(current_time: dt_time, start_time: dt_time, end_time: dt_time) -> bool:
    """
    Check if a time is within a time range, handling overnight ranges.
    
    Args:
        current_time: The time to check
        start_time: The start time of the range
        end_time: The end time of the range
        
    Returns:
        bool: True if current_time is within the range, False otherwise
    """
    if start_time <= end_time:
        # Normal range (e.g., 9:00 to 17:00)
        return start_time <= current_time <= end_time
    else:
        # Overnight range (e.g., 22:00 to 03:00)
        return current_time >= start_time or current_time <= end_time

def is_item_currently_available_by_schedule(item: Dict[str, Any]) -> bool:
    """
    Check if an item is currently available based on its availability schedule.
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if the item is currently available, False otherwise
    """
    # If no schedule, item is always available
    schedule = item.get('availabilitySchedule')
    if not schedule:
        return True
        
    # Get current time in local timezone (assuming schedule is in local time)
    now = datetime.now()
    current_day = now.strftime('%A').lower()  # day of week in lowercase
    current_time = now.time()
    
    # Check if item is available on this day
    day_schedule = schedule.get(current_day)
    if not day_schedule:
        # No schedule for today means not available
        return False
        
    # Check each time range for today
    for time_range in day_schedule:
        start_str = time_range.get('start')
        end_str = time_range.get('end')
        
        if not start_str or not end_str:
            continue
            
        # Parse time strings (H:M:S format)
        try:
            # Handle various time formats
            if 'T' in start_str:
                # ISO format with T separator
                start_time = datetime.fromisoformat(start_str).time()
            else:
                # HH:MM:SS format
                h, m, s = map(int, start_str.split(':'))
                start_time = dt_time(h, m, s)
                
            if 'T' in end_str:
                # ISO format with T separator
                end_time = datetime.fromisoformat(end_str).time()
            else:
                # HH:MM:SS format
                h, m, s = map(int, end_str.split(':'))
                end_time = dt_time(h, m, s)
                
            # Check if current time is in this range
            if is_time_in_range(current_time, start_time, end_time):
                return True
        except ValueError:
            logger.error(f"Invalid time format in schedule: {start_str} - {end_str}")
            continue
    
    # If we get here, no time range matched
    return False

def get_popular_menu_items(count=5):
    """
    Get a list of popular menu items to display to customers.
    This is useful for menu queries and recommendations.
    
    Args:
        count: Number of popular items to return
        
    Returns:
        list: List of popular menu items with names and prices
    """
    menu_data = load_menu_data()
    items = menu_data.get('items', [])
    
    # Sort by popularity if available, otherwise return first few items
    if not items:
        return []
        
    # Filter out any items that are not currently available
    available_items = []
    for item in items:
        if item.get('available', True) and not is_item_snoozed(item):
            available_items.append(item)
    
    # If we have a popularity field, use it
    if available_items and 'popularity' in available_items[0]:
        popular_items = sorted(available_items, key=lambda x: x.get('popularity', 0), reverse=True)
    else:
        # Otherwise just take the first few items
        popular_items = available_items
    
    # Return the top N items with name and price
    result = []
    for item in popular_items[:count]:
        result.append({
            'name': item.get('name', 'Unknown'),
            'price': item.get('price', 0),
            'category': item.get('category', ''),
            'description': item.get('description', '')
        })
    
    return result