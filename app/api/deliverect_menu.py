"""
Deliverect menu webhook endpoints.

This module handles menu updates from Deliverect.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from pydantic import BaseModel, Field

from app.dependencies import get_db
from app.utils.deliverect.menu_async import process_deliverect_menu_async
# Menu caching is handled by menu_matcher_cache_async
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup
from app.db.crud_menu_async import (
    create_category, create_item, create_modifier, create_modifier_group,
    link_item_to_modifier_group, link_modifier_to_group
)
from app.schemas.menu import (
    MenuCategoryCreate, MenuItemCreate, MenuModifierCreate, MenuModifierGroupCreate
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Snooze/Unsnooze Models
class DeliverectSnoozeRequest(BaseModel):
    """Deliverect snooze/unsnooze request."""
    action: str  # "snooze" or "unsnooze"
    channelLinkId: str
    items: List[Dict[str, Any]]  # List of items with PLU and snooze details


async def clear_menu_data(db: AsyncSession):
    """Clear all menu data from the database."""
    from sqlalchemy import text
    
    try:
        # Delete in correct order based on foreign key constraints:
        # 1. Junction tables and dependent tables first
        # 2. Tables with foreign keys next
        # 3. Parent tables last
        
        logger.info("Starting to clear menu data...")
        
        # First, clear menu name variants (no dependencies)
        await db.execute(text("DELETE FROM menu_name_variants"))
        await db.commit()
        logger.info("Cleared menu_name_variants")
        
        # Clear junction tables
        await db.execute(text("DELETE FROM item_modifier_group"))  # junction table for items and modifier groups
        await db.commit()
        logger.info("Cleared item_modifier_group")
        
        await db.execute(text("DELETE FROM group_modifier"))  # junction table for groups and modifiers
        await db.commit()
        logger.info("Cleared group_modifier")
        
        # Clear modifiers (depends on modifier_groups)
        await db.execute(text("DELETE FROM menu_modifiers"))
        await db.commit()
        logger.info("Cleared menu_modifiers")
        
        # Clear modifier groups
        await db.execute(text("DELETE FROM menu_modifier_groups"))
        await db.commit()
        logger.info("Cleared menu_modifier_groups")
        
        # Clear menu items (depends on categories)
        await db.execute(text("DELETE FROM menu_items"))
        await db.commit()
        logger.info("Cleared menu_items")
        
        # Finally clear categories (parent table)
        await db.execute(text("DELETE FROM menu_categories"))
        await db.commit()
        logger.info("Cleared menu_categories")
        
        logger.info("Successfully cleared all menu data from database")
        
    except Exception as e:
        logger.error(f"Error clearing menu data: {e}")
        await db.rollback()
        raise


@router.post("/menu/update")
async def handle_menu_update(
    menu_data: List[Dict[str, Any]] = Body(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Handle menu update webhook from Deliverect.
    
    Deliverect sends the menu as an array of location menus. Each location
    menu contains categories, products, modifiers, etc.
    """
    try:
        # Deliverect sends an array of menus (one per location)
        if not menu_data or not isinstance(menu_data, list):
            logger.error("Invalid menu data: expected array")
            return {"status": "FAILED"}
            
        # Process the first location menu (typically there's only one)
        location_menu = menu_data[0]
        
        logger.info(f"Received menu update for channel: {location_menu.get('channelLinkId')}")
        logger.info(f"Menu ID: {location_menu.get('menuId')}")
        logger.info(f"Categories: {len(location_menu.get('categories', []))}")
        logger.info(f"Products: {len(location_menu.get('products', {}))}")
        
        # Process the menu data using existing utility
        # The utility expects the location menu structure
        processed_data = await process_deliverect_menu_async(location_menu)
        
        # Clear existing menu data for this location
        logger.info("Clearing existing menu data...")
        await clear_menu_data(db)
        
        # Store categories
        category_map = {}  # Map category deliverect IDs to database IDs
        if processed_data.get("categories"):
            logger.info(f"Storing {len(processed_data['categories'])} categories...")
            for category in processed_data["categories"]:
                category_create = MenuCategoryCreate(
                    name=category["name"],
                    description=category.get("description", ""),
                    deliverect_category_id=category.get("deliverect_category_id")
                )
                db_category = await create_category(db, category_create)
                # Map both by deliverect ID and name for flexibility
                category_map[category["deliverect_category_id"]] = db_category.id
                category_map[category["name"]] = db_category.id
        
        # Store modifier groups and modifiers
        modifier_group_map = {}  # Map modifier group names to IDs
        if processed_data.get("modifierGroups"):
            logger.info(f"Storing {len(processed_data['modifierGroups'])} modifier groups...")
            for group in processed_data["modifierGroups"]:
                # Create modifier group
                group_create = MenuModifierGroupCreate(
                    name=group["name"],
                    min_selection=group.get("min_selection", 0),
                    max_selection=group.get("max_selection", 1),
                    multiMax=group.get("multi_max", 1),
                    deliverect_group_id=group.get("deliverect_group_id"),
                    plu=group.get("plu"),
                    is_variant_group=group.get("is_variant_group", False)
                )
                db_group = await create_modifier_group(db, group_create)
                modifier_group_map[group["deliverect_group_id"]] = db_group.id
                
                # Add modifiers to the group
                for modifier in group.get("modifiers", []):
                    modifier_create = MenuModifierCreate(
                        name=modifier["name"],
                        price_change=modifier.get("price_change", 0),
                        plu=modifier.get("plu"),
                        deliverect_modifier_id=modifier.get("deliverect_modifier_id"),
                        is_available=modifier.get("is_available", True)
                    )
                    db_modifier = await create_modifier(db, modifier_create)
                    
                    # Link modifier to group
                    if db_modifier and db_group:
                        await link_modifier_to_group(db, db_modifier.id, db_group.id)
        
        # Store items
        item_plu_map = {}  # Map PLUs to item IDs for linking modifier groups
        if processed_data.get("items"):
            logger.info(f"Storing {len(processed_data['items'])} items...")
            for item in processed_data["items"]:
                # Find category ID
                category_id = None
                if item.get("category_id"):
                    category_id = category_map.get(item["category_id"])
                elif item.get("category_name"):
                    category_id = category_map.get(item["category_name"])
                
                item_create = MenuItemCreate(
                    name=item["name"],
                    category_id=category_id,
                    price=item["price"],
                    description=item.get("description"),
                    plu=item.get("plu"),
                    deliverect_item_id=item.get("deliverect_item_id"),
                    is_available=item.get("is_available", True),
                    image_url=item.get("image_url"),
                    is_combo=item.get("is_combo", False),
                    is_variant=item.get("is_variant", False)
                )
                db_item = await create_item(db, item_create)
                if db_item:
                    item_plu_map[item.get("plu", "")] = db_item.id
                    
                    # Link item to its modifier groups
                    for mod_group in item.get("modifier_groups", []):
                        group_id = modifier_group_map.get(mod_group["deliverect_group_id"])
                        if group_id:
                            await link_item_to_modifier_group(db, db_item.id, group_id)
        
        # Handle snoozed products
        if processed_data.get("snoozed_products"):
            logger.info(f"Processing {len(processed_data['snoozed_products'])} snoozed products...")
            for snoozed in processed_data["snoozed_products"]:
                plu = snoozed.get("plu", "")
                if plu:
                    # Update item availability based on PLU
                    from sqlalchemy import update
                    from app.models.menu_async import MenuItem
                    
                    stmt = update(MenuItem).where(MenuItem.plu == plu).values(
                        is_available=False,
                        snoozed_until=snoozed.get("snooze_end")
                    )
                    await db.execute(stmt)
        
        # Commit all changes
        await db.commit()
        
        # Invalidate menu cache in background
        if background_tasks:
            background_tasks.add_task(invalidate_menu_cache)
        
        logger.info("Menu update completed successfully")
        
        # Return success status as expected by Deliverect
        return {"status": "ONLINE"}
        
    except Exception as e:
        logger.error(f"Error processing menu update: {str(e)}", exc_info=True)
        
        # Rollback any database changes
        await db.rollback()
        
        # Return failure status
        return {"status": "FAILED"}


@router.post("/menu/snooze")
async def handle_snooze_unsnooze(
    request: DeliverectSnoozeRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Handle snooze/unsnooze requests from Deliverect.
    
    This endpoint receives requests to temporarily make items unavailable (snooze)
    or make them available again (unsnooze).
    """
    try:
        logger.info(f"Received {request.action} request for channel: {request.channelLinkId}")
        
        from sqlalchemy import select, update
        from datetime import datetime
        
        for item in request.items:
            plu = item.get("plu")
            if not plu:
                continue
                
            if request.action == "snooze":
                # Mark item as unavailable
                snooze_until = item.get("snoozeUntil")  # Optional timestamp
                logger.info(f"Snoozing item with PLU {plu}")
                
                stmt = update(MenuItem).where(MenuItem.plu == plu).values(
                    is_available=False,
                    snoozed_until=datetime.fromisoformat(snooze_until) if snooze_until else None
                )
                await db.execute(stmt)
                
            elif request.action == "unsnooze":
                # Mark item as available
                logger.info(f"Unsnoozing item with PLU {plu}")
                
                stmt = update(MenuItem).where(MenuItem.plu == plu).values(
                    is_available=True,
                    snoozed_until=None
                )
                await db.execute(stmt)
        
        await db.commit()
        
        # Invalidate cache
        from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher
        await clear_cached_menu_matcher()
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(f"Error handling {request.action}: {str(e)}", exc_info=True)
        await db.rollback()
        return {"status": "FAILED"}


async def invalidate_menu_cache():
    """Invalidate the menu cache after a successful update."""
    try:
        logger.info("Invalidating menu cache...")
        
        # Clear async menu matcher cache (which also clears Redis cache)
        from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher
        await clear_cached_menu_matcher()
        
        logger.info("Menu cache invalidated successfully")
    except Exception as e:
        logger.error(f"Error invalidating menu cache: {str(e)}")