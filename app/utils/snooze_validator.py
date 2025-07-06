"""
Snooze validator utility for menu item availability.

This module provides functions to validate item availability
based on snoozing and other availability conditions.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional


def is_item_available(item: Dict[str, Any]) -> bool:
    """
    Check if a menu item is currently available.
    
    Args:
        item: Menu item dictionary with availability fields
        
    Returns:
        bool: True if item is available, False otherwise
    """
    if not item.get('is_available', True):
        return False
    
    # Check if item is snoozed
    snoozed_until = item.get('snoozed_until')
    if snoozed_until:
        if isinstance(snoozed_until, str):
            try:
                snoozed_until = datetime.fromisoformat(snoozed_until.replace('Z', '+00:00'))
            except ValueError:
                return False
        
        if isinstance(snoozed_until, datetime):
            if datetime.now() < snoozed_until:
                return False
    
    return True


def validate_items_availability(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate availability of multiple menu items.
    
    Args:
        items: List of menu item dictionaries
        
    Returns:
        Dict with validation results including available/unavailable items
    """
    available_items = []
    unavailable_items = []
    
    for item in items:
        if is_item_available(item):
            available_items.append(item)
        else:
            unavailable_items.append(item)
    
    return {
        'available_items': available_items,
        'unavailable_items': unavailable_items,
        'total_items': len(items),
        'available_count': len(available_items),
        'unavailable_count': len(unavailable_items)
    }