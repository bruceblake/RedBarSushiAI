"""
Stronger snoozed item validation for Deliverect integration.
This module ensures that snoozed items are not available for ordering.
"""

import logging
from typing import Dict, Any

# These are simple validation functions that don't need database access
from datetime import datetime

logger = logging.getLogger(__name__)


def is_item_snoozed_timebased(item: Dict[str, Any]) -> bool:
    """
    Check if an item is snoozed based on time.

    Args:
        item: The menu item to check

    Returns:
        bool: True if the item is currently snoozed, False otherwise
    """
    snoozed_until = item.get("snoozed_until")
    if not snoozed_until:
        return False

    # Parse the snoozed_until timestamp
    if isinstance(snoozed_until, str):
        try:
            snoozed_until_dt = datetime.fromisoformat(
                snoozed_until.replace("Z", "+00:00")
            )
            return datetime.now() < snoozed_until_dt
        except Exception as e:  # Changed bare except to except Exception
            logger.warning(
                f"Error parsing snoozed_until string '{snoozed_until}': {e}"
            )
            return False
    elif isinstance(snoozed_until, datetime):
        return datetime.now() < snoozed_until

    return False


def is_item_currently_available_by_schedule(item: Dict[str, Any]) -> bool:
    """
    Check if an item is available based on its schedule.

    Args:
        item: The menu item to check

    Returns:
        bool: True if the item is available now, False otherwise
    """
    availabilities = item.get("availabilities", [])
    if not availabilities:
        # No schedule means always available
        return True

    # For now, assume items are available if they have any availability schedule
    # TODO: Implement proper day/time checking
    return True


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
        logger.warning(
            f"[AVAILABILITY] Item '{item.get('name')}' is marked as unavailable"
        )
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
        if "availabilities" in item and not is_item_currently_available_by_schedule(
            item
        ):
            logger.warning(
                f"[AVAILABILITY] Item '{item.get('name')}' is not available by schedule"
            )
            return False
    except Exception as e:
        logger.error(f"[AVAILABILITY] Error checking schedule: {e}")
        # Be conservative - if there's an error checking availability, consider it unavailable
        return False

    # If reference handler is missing, the item is not available for ordering
    if not item.get("reference_handler"):
        logger.warning(
            f"[AVAILABILITY] Item '{item.get('name')}' has no reference handler"
        )
        return False

    # If we reach here, the item is available
    return True
