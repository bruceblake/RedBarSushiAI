"""
Menu utility functions for handling menu data from database using async SQLAlchemy.
This is an updated version of menu_utils_db.py that uses async SQLAlchemy.
"""

import json
import os
import time
import logging
import shutil
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timezone, time as dt_time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.crud_menu_async import (
    get_items, get_modifier_groups, get_modifiers, 
    get_items_by_category, get_variants
)
from app.models.menu_async import (
    MenuCategory, MenuItem, MenuModifier, 
    MenuModifierGroup, MenuNameVariant
)

# Configure logging
logger = logging.getLogger(__name__)

async def load_menu_data(db: AsyncSession, location_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load menu data from the database.
    
    Args:
        db: Database session
        location_id: Optional location ID to filter by
        
    Returns:
        Dict containing menu data structure
    """
    menu_data = {
        "items": [],
        "modifiers": [],
        "modifier_groups": [],
        "variants": []
    }
    
    try:
        # Load menu items
        items = await get_items(db, limit=1000, location_id=location_id)
        menu_data["items"] = [item.to_dict() for item in items]
        
        # Load modifier groups
        modifier_groups = await get_modifier_groups(db, limit=1000, location_id=location_id, include_modifiers=True)
        menu_data["modifier_groups"] = [group.to_dict() for group in modifier_groups]
        
        # Load modifiers
        modifiers = await get_modifiers(db, limit=1000, location_id=location_id)
        menu_data["modifiers"] = [modifier.to_dict() for modifier in modifiers]
        
        # Load variants
        variants = await get_variants(db, limit=1000)
        menu_data["variants"] = [variant.to_dict() for variant in variants]
        
        logger.info(f"Loaded menu data from database: {len(menu_data['items'])} items, "
                   f"{len(menu_data['modifier_groups'])} groups, "
                   f"{len(menu_data['modifiers'])} modifiers, "
                   f"{len(menu_data['variants'])} variants")
        
    except Exception as e:
        logger.error(f"Error loading menu data from database: {e}")
        # Return empty menu data on error
    
    return menu_data

async def get_menu_categories(db: AsyncSession, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get menu categories from database.
    
    Args:
        db: Database session
        location_id: Optional location ID to filter by
        
    Returns:
        List of menu categories
    """
    try:
        # Query for categories
        stmt = select(MenuCategory)
        if location_id:
            stmt = stmt.where(MenuCategory.location_id == location_id)
            
        result = await db.execute(stmt)
        categories = result.scalars().all()
        
        # Convert to dicts
        category_dicts = [category.to_dict() for category in categories]
        
        return category_dicts
    
    except Exception as e:
        logger.error(f"Error getting menu categories: {e}")
        return []
        
async def get_menu_items_by_category(
    db: AsyncSession, 
    category_id: int,
    location_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get menu items for a specific category.
    
    Args:
        db: Database session
        category_id: Category ID to get items for
        location_id: Optional location ID to filter by
        
    Returns:
        List of menu items in the category
    """
    try:
        # Get items in the category
        items = await get_items_by_category(db, category_id, limit=500)
        
        # Convert to dicts
        item_dicts = [item.to_dict() for item in items]
        
        return item_dicts
    
    except Exception as e:
        logger.error(f"Error getting menu items for category {category_id}: {e}")
        return []