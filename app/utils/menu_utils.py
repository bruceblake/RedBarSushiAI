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

# Default paths
MENU_FILE_PATH = os.getenv('MENU_FILE_PATH', os.path.join(os.getcwd(), 'menu_data.json'))
BACKUP_FOLDER = os.path.join(os.getcwd(), 'backups')

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
            
        # Make sure directory exists
        directory = os.path.dirname(actual_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Create backups directory if it doesn't exist
        if not os.path.exists(BACKUP_FOLDER):
            os.makedirs(BACKUP_FOLDER, exist_ok=True)
        
        # Create a backup with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_FOLDER, f"menu_backup_{timestamp}.json")
        
        # If the file exists, make a backup before overwriting
        if os.path.exists(actual_path):
            shutil.copy2(actual_path, backup_path)
            logger.info(f"Menu backup created at {backup_path}")
        
        # Write to file
        with open(actual_path, 'w') as f:
            json.dump(menu_data, f, indent=2)
            
        logger.info(f"Menu data written to {actual_path}")
        
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
    if location_id:
        location_file = f"menu_data_{location_id}.json"
        location_path = os.path.join(os.path.dirname(MENU_FILE_PATH), location_file)
        if os.path.exists(location_path):
            file_path = location_path
    
    try:
        # Load menu data from file
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
        
        # Update cache
        _menu_cache = menu_data
        _last_refresh_time = current_time
        
        return menu_data
    except Exception as e:
        logger.error(f"Error loading menu data: {e}")
        # Return empty structure if file can't be loaded
        return {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}

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
    
    # Normalize name for case-insensitive matching
    item_name_lower = item_name.lower().strip()
    
    # Check name variants first
    name_variants = menu_data.get("name_variants", {})
    if item_name_lower in name_variants:
        actual_name = name_variants[item_name_lower]
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == actual_name.lower():
                return item
    
    # Try direct match
    for item in menu_data.get("items", []):
        if item.get("name", "").lower() == item_name_lower:
            return item
    
    # No match found
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