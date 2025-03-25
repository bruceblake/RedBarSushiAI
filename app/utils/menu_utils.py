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
    
    # Alternative paths if file not found
    alternative_paths = [
        MENU_FILE_PATH,
        os.path.join(os.getcwd(), "menu_data.json"),
        os.path.join(os.getcwd(), "redbar_menu_data.json")
    ]
    
    # Try original path first
    if os.path.exists(file_path):
        menu_path = file_path
    else:
        # Try alternative paths
        for path in alternative_paths:
            if os.path.exists(path):
                menu_path = path
                logger.info(f"Using alternative menu path: {path}")
                break
        else:
            # No menu file found
            logger.error("No menu file found at any path")
            return {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}
    
    try:
        # Read and parse menu data
        with open(menu_path, 'r') as f:
            menu_data = json.load(f)
        
        # Ensure required structures exist
        if not isinstance(menu_data, dict):
            menu_data = {}
            
        for key in ["items", "modifiers", "modifierGroups", "name_variants"]:
            if key not in menu_data:
                if key == "name_variants":
                    menu_data[key] = {}
                else:
                    menu_data[key] = []
        
        # Update cache
        _menu_cache = menu_data
        _last_refresh_time = current_time
        
        return menu_data
        
    except Exception as e:
        logger.error(f"Error loading menu data: {e}")
        # Return empty menu structure on error
        return {"items": [], "modifiers": [], "modifierGroups": [], "name_variants": {}}

def process_deliverect_menu(deliverect_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process menu data from Deliverect into our internal format.
    
    Args:
        deliverect_data (dict): Menu data from Deliverect
        
    Returns:
        dict: Processed menu in our internal format
    """
    logger.info("[DELIVERECT] Processing menu data from Deliverect")
    
    # Initialize result structures
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {}
    }
    
    # Process categories and products
    categories = deliverect_data.get("categories", [])
    logger.info(f"[DELIVERECT] Processing {len(categories)} categories")
    
    # Track IDs to avoid duplicates
    processed_item_ids = set()
    processed_modifier_group_ids = set()
    
    # Process all categories and their products
    for category in categories:
        cat_id = category.get("id", "")
        cat_name = category.get("name", "")
        
        for product in category.get("products", []):
            prod_id = product.get("id", "")
            
            # Skip duplicates
            if prod_id in processed_item_ids:
                continue
                
            processed_item_ids.add(prod_id)
            
            # Extract product data
            prod_name = product.get("name", "")
            plu = product.get("plu", "")
            description = product.get("description", "")
            price = product.get("price", 0) / 100  # Convert from cents
            available = product.get("available", True)
            image_url = product.get("imageUrl", "")
            
            # Create product entry
            menu_item = {
                "id": prod_id,
                "name": prod_name,
                "price": price,
                "reference_handler": plu,
                "description": description,
                "imageUrl": image_url,
                "category": cat_name,
                "categoryId": cat_id,
                "available": available,
                "snoozed": not available
            }
            
            # Add to items list
            result["items"].append(menu_item)
            
            # Generate name variants for this product
            prod_name_lower = prod_name.lower()
            result["name_variants"][prod_name_lower] = prod_name
            
            # Add single word from name as variant if unique enough (at least 4 chars)
            words = prod_name_lower.split()
            
            # For multi-word items, add key words as variants
            if len(words) > 1:
                # Add first word as variant if long enough
                if len(words[0]) >= 4 and words[0] not in ["with", "and", "the"]:
                    result["name_variants"][words[0]] = prod_name
                
                # Add last word as variant if long enough
                if len(words[-1]) >= 4 and words[-1] not in ["with", "and", "the"]:
                    result["name_variants"][words[-1]] = prod_name
                
                # Add no-space version
                result["name_variants"][prod_name_lower.replace(" ", "")] = prod_name
                
                # Special handling for "French Fries" => "Fries" and similar
                if "french fries" in prod_name_lower:
                    result["name_variants"]["fries"] = prod_name
                    
                if "cheeseburger" in prod_name_lower:
                    result["name_variants"]["burger"] = prod_name
                    
                if "hamburger" in prod_name_lower and "burger" not in result["name_variants"]:
                    result["name_variants"]["burger"] = prod_name
            
            # Process modifier groups for this product
            for mod_group in product.get("modifierGroups", []):
                group_id = mod_group.get("id", "")
                
                # Add reference to product
                if "modifierGroups" not in menu_item:
                    menu_item["modifierGroups"] = []
                    
                menu_item["modifierGroups"].append(group_id)
                
                # Skip if already processed
                if group_id in processed_modifier_group_ids:
                    continue
                    
                processed_modifier_group_ids.add(group_id)
                
                # Create modifier group
                group_data = {
                    "id": group_id,
                    "name": mod_group.get("name", ""),
                    "min": mod_group.get("min", 0),
                    "max": mod_group.get("max", 0),
                    "minAllowed": mod_group.get("min", 0),
                    "maxAllowed": mod_group.get("max", 0),
                    "modifiers": []
                }
                
                # Process modifiers in this group
                for modifier in mod_group.get("modifiers", []):
                    mod_id = modifier.get("id", "")
                    mod_name = modifier.get("name", "")
                    mod_price = modifier.get("price", 0) / 100
                    mod_plu = modifier.get("plu", "")
                    mod_available = modifier.get("available", True)
                    
                    modifier_data = {
                        "id": mod_id,
                        "name": mod_name,
                        "price": mod_price,
                        "reference_handler": mod_plu,
                        "available": mod_available,
                        "snoozed": not mod_available
                    }
                    
                    # Add to modifiers list
                    result["modifiers"].append(modifier_data)
                    
                    # Add to modifier group
                    group_data["modifiers"].append(mod_id)
                    
                # Add group to modifier groups
                result["modifierGroups"].append(group_data)
    
    # Log summary of what was processed
    logger.info(f"[DELIVERECT] Processed {len(result['items'])} items, {len(result['modifierGroups'])} modifier groups")
    logger.info(f"[DELIVERECT] Generated {len(result['name_variants'])} name variants")
    
    return result

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
    if start_time is None or end_time is None:
        return False
        
    # Check if current time is within snooze window
    now = datetime.now(timezone.utc)
    return start_time <= now <= end_time

def is_item_currently_available_by_schedule(item: Dict[str, Any]) -> bool:
    """
    Check if an item is available based on its scheduled availability.
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if available, False otherwise
    """
    # Get availability blocks
    availability_blocks = item.get("availabilities", [])
    
    # If no blocks defined, item is always available
    if not availability_blocks:
        return True
        
    # Get current time info
    now = datetime.now(timezone.utc)
    current_day = now.isoweekday()  # 1=Monday, 7=Sunday
    current_time = now.time()
    
    # Check each availability block
    for block in availability_blocks:
        # Check day of week
        if block.get("dayOfWeek") != current_day:
            continue
            
        # Parse time strings
        try:
            start_str = block.get("startTime", "00:00")
            end_str = block.get("endTime", "23:59")
            
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
            
            start_time = dt_time(hour=start_hour, minute=start_min)
            end_time = dt_time(hour=end_hour, minute=end_min)
            
            # Check if current time is in this block
            if start_time <= current_time <= end_time:
                return True
        except (ValueError, TypeError):
            # Skip invalid time formats
            continue
    
    # No matching blocks found
    return False

def find_menu_item_by_name(item_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a menu item by name using exact matching and name variants.
    
    Args:
        item_name (str): The name of the item to find
        
    Returns:
        dict: The menu item if found, None otherwise
    """
    # Load current menu data
    menu_data = load_menu_data()
    items = menu_data.get("items", [])
    name_variants = menu_data.get("name_variants", {})
    
    # Normalize input
    item_name_lower = item_name.lower().strip()
    
    # Check name variants first
    if item_name_lower in name_variants:
        actual_name = name_variants[item_name_lower]
        logger.info(f"Found name variant match: '{item_name}' → '{actual_name}'")
        
        # Find the actual item with this name
        for item in items:
            if item.get("name", "").lower() == actual_name.lower():
                return item
    
    # Try direct match if no variant found
    for item in items:
        if item.get("name", "").lower() == item_name_lower:
            return item
    
    # No match found
    return None

def get_all_menu_items() -> List[Dict[str, Any]]:
    """
    Get all available menu items.
    
    Returns:
        list: All menu items
    """
    menu_data = load_menu_data()
    return menu_data.get("items", [])

def get_all_name_variants() -> Dict[str, str]:
    """
    Get all name variants in the menu.
    
    Returns:
        dict: All name variants
    """
    menu_data = load_menu_data()
    return menu_data.get("name_variants", {})

def sync_reference_handlers(source_location_id: Optional[str] = None, 
                           target_location_id: Optional[str] = None) -> Dict[str, int]:
    """
    Synchronize reference handlers between locations.
    
    Args:
        source_location_id (str): Source location ID
        target_location_id (str): Target location ID
        
    Returns:
        dict: Synchronization statistics
    """
    stats = {"updated": 0, "skipped": 0, "total": 0}
    
    # Load source menu
    source_menu = load_menu_data(force_refresh=True, location_id=source_location_id)
    
    # Load target menu
    target_menu = load_menu_data(force_refresh=True, location_id=target_location_id)
    
    # Build lookup tables
    source_items_by_name = {item.get("name", "").lower(): item for item in source_menu.get("items", [])}
    
    # Update target items
    for target_item in target_menu.get("items", []):
        stats["total"] += 1
        item_name = target_item.get("name", "").lower()
        
        if item_name in source_items_by_name:
            source_item = source_items_by_name[item_name]
            source_ref = source_item.get("reference_handler")
            target_ref = target_item.get("reference_handler")
            
            if source_ref and source_ref != target_ref:
                target_item["reference_handler"] = source_ref
                stats["updated"] += 1
            else:
                stats["skipped"] += 1
        else:
            stats["skipped"] += 1
    
    # Save updated target menu
    target_file = f"menu_data_{target_location_id}.json" if target_location_id else "menu_data.json"
    target_path = os.path.join(os.path.dirname(MENU_FILE_PATH), target_file)
    
    write_menu_file(target_menu, target_path)
    
    return stats