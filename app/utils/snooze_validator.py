"""
Stronger snoozed item validation for Deliverect integration.
This module ensures that snoozed items are not available for ordering.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.menu_utils import is_item_snoozed_timebased, is_item_currently_available_by_schedule

logger = logging.getLogger(__name__)

def is_item_available(item: Dict[str, Any]) -> bool:
    """
    Comprehensive check for item availability.
    
    Args:
        item: The menu item to check
        
    Returns:
        bool: True if the item is available, False otherwise
    """
    # Item must exist
    if not item:
        logger.warning("[AVAILABILITY] Item is None or empty")
        return False
        
    # Check basic availability flag
    if not item.get("available", True):
        logger.warning(f"[AVAILABILITY] Item '{item.get('name')}' is marked as unavailable")
        return False
        
    # Check basic snoozed flag
    if item.get("snoozed", False):
        logger.warning(f"[AVAILABILITY] Item '{item.get('name')}' is marked as snoozed")
        return False
        
    # Check time-based snoozing
    if is_item_snoozed_timebased(item):
        logger.warning(f"[AVAILABILITY] Item '{item.get('name')}' is time-snoozed")
        return False
        
    # Check scheduled availability
    try:
        if "availabilities" in item and not is_item_currently_available_by_schedule(item):
            logger.warning(f"[AVAILABILITY] Item '{item.get('name')}' is not available by schedule")
            return False
    except Exception as e:
        logger.error(f"[AVAILABILITY] Error checking schedule: {e}")
        # Be conservative - if there's an error checking availability, consider it unavailable
        return False
        
    # If reference handler is missing, the item is not available for ordering
    if not item.get("reference_handler"):
        logger.warning(f"[AVAILABILITY] Item '{item.get('name')}' has no reference handler")
        return False
        
    # If we reach here, the item is available
    return True

def validate_items_availability(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out unavailable items from a list of items.
    
    Args:
        items: List of menu items to check
        
    Returns:
        List[Dict[str, Any]]: Only the available items
    """
    available_items = []
    unavailable_items = []
    
    for item in items:
        if is_item_available(item):
            available_items.append(item)
        else:
            unavailable_items.append(item.get("name", "Unknown item"))
            
    if unavailable_items:
        logger.warning(f"[AVAILABILITY] Filtered out unavailable items: {unavailable_items}")
        
    return available_items

def check_item_availability_by_reference(reference_handler: str, all_items: List[Dict[str, Any]]) -> bool:
    """
    Check if an item with a specific reference handler is available.
    
    Args:
        reference_handler: The reference handler to check
        all_items: List of all menu items
        
    Returns:
        bool: True if the item is available, False otherwise
    """
    for item in all_items:
        if item.get("reference_handler") == reference_handler:
            return is_item_available(item)
            
    # If not found, it's not available
    logger.warning(f"[AVAILABILITY] Item with reference '{reference_handler}' not found")
    return False
