"""
Menu utility functions for handling menu data from database using async SQLAlchemy.
This is an updated version of menu_utils_db.py that uses async SQLAlchemy.
"""

import logging

# import shutil # Removed as unused
from typing import Dict, Any, Optional
# from datetime import datetime, timezone, time as dt_time # Removed as unused

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud_menu_async import (
    get_items,
    get_modifier_groups,
    get_modifiers,
    get_variants,
)
# Ensure we're not importing from the old models package that leads to base.py
# Avoid: from app.models.menu import ...

# Configure logging
logger = logging.getLogger(__name__)


async def load_menu_data(
    db: AsyncSession, location_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load menu data from the database.

    Args:
        db: Database session
        location_id: Optional location ID to filter by

    Returns:
        Dict containing menu data structure
    """
    menu_data = {"items": [], "modifiers": [], "modifier_groups": [], "variants": []}

    try:
        # Load menu items
        items = await get_items(db, limit=1000, location_id=location_id)
        menu_data["items"] = [item.to_dict() for item in items]

        # Load modifier groups
        modifier_groups = await get_modifier_groups(
            db, limit=1000, location_id=location_id, include_modifiers=True
        )
        menu_data["modifier_groups"] = [group.to_dict() for group in modifier_groups]

        # Load modifiers
        modifiers = await get_modifiers(db, limit=1000, location_id=location_id)
        menu_data["modifiers"] = [modifier.to_dict() for modifier in modifiers]

        # Load variants
        variants = await get_variants(db, limit=1000)
        menu_data["variants"] = [variant.to_dict() for variant in variants]

        logger.info(
            f"Loaded menu data from database: {len(menu_data['items'])} items, "
            f"{len(menu_data['modifier_groups'])} groups, "
            f"{len(menu_data['modifiers'])} modifiers, "
            f"{len(menu_data['variants'])} variants"
        )

    except Exception as e:
        logger.error(f"Error loading menu data from database: {e}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error args: {e.args}")
        # Return empty menu data on error

    return menu_data


# get_menu_categories function removed as unused

# get_menu_items_by_category function removed as unused
