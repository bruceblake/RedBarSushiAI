"""
Deliverect menu webhook endpoints.

This module handles menu updates from Deliverect.
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.dependencies import get_db
from app.utils.deliverect.menu_async import process_deliverect_menu_async
from app.utils.menu_db_store_async import AsyncMenuDbStore
from app.utils.menu_cache_sdk import menu_cache

logger = logging.getLogger(__name__)

router = APIRouter()


# Deliverect Menu Update Models
class DeliverectModifier(BaseModel):
    """Deliverect modifier model."""
    _id: str = Field(alias="id", default=None)
    name: str
    price: int = 0  # Price in cents
    plu: Optional[str] = None
    isAvailable: bool = True
    posId: Optional[str] = None


class DeliverectModifierGroup(BaseModel):
    """Deliverect modifier group model."""
    _id: str = Field(alias="id", default=None)
    name: str
    min: int = 0
    max: int = 1
    multiMax: Optional[int] = None
    plu: Optional[str] = None
    modifiers: List[DeliverectModifier] = []


class DeliverectProduct(BaseModel):
    """Deliverect product/item model."""
    _id: str = Field(alias="id", default=None)
    name: str
    description: Optional[str] = None
    price: int  # Price in cents
    plu: str
    imageUrl: Optional[str] = None
    isAvailable: bool = True
    posId: Optional[str] = None
    modifierGroups: List[DeliverectModifierGroup] = []
    category: Optional[str] = None


class DeliverectCategory(BaseModel):
    """Deliverect category model."""
    _id: str = Field(alias="id", default=None)
    name: str
    description: Optional[str] = None
    posId: Optional[str] = None


class DeliverectMenu(BaseModel):
    """Deliverect menu structure."""
    categories: List[DeliverectCategory] = []
    products: List[DeliverectProduct] = []


class DeliverectMenuPushRequest(BaseModel):
    """Deliverect menu push webhook payload."""
    menu: DeliverectMenu
    accountId: str
    channelLinkId: str
    menuId: Optional[str] = None
    locationId: Optional[str] = None


# Snooze/Unsnooze Models
class DeliverectSnoozeRequest(BaseModel):
    """Deliverect snooze/unsnooze request."""
    action: str  # "snooze" or "unsnooze"
    channelLinkId: str
    items: List[Dict[str, Any]]  # List of items with PLU and snooze details


@router.post("/menu/update")
async def handle_menu_update(
    payload: DeliverectMenuPushRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Handle menu update webhook from Deliverect.
    
    This endpoint receives menu updates from Deliverect and processes them
    to update our internal menu database.
    """
    try:
        logger.info(f"Received menu update for channel: {payload.channelLinkId}")
        
        # Convert Deliverect payload to dict for processing
        menu_data = payload.dict()
        
        # Process the menu data using existing utility
        processed_data = await process_deliverect_menu_async(menu_data)
        
        # Store in database using AsyncMenuDbStore
        menu_store = AsyncMenuDbStore(db)
        
        # Clear existing menu data for this location
        logger.info("Clearing existing menu data...")
        await menu_store.clear_menu_data()
        
        # Store categories
        if processed_data.get("categories"):
            logger.info(f"Storing {len(processed_data['categories'])} categories...")
            for category in processed_data["categories"]:
                await menu_store.add_category(
                    name=category["name"],
                    description=category.get("description"),
                    deliverect_id=category.get("deliverect_category_id")
                )
        
        # Store items
        if processed_data.get("items"):
            logger.info(f"Storing {len(processed_data['items'])} items...")
            for item in processed_data["items"]:
                await menu_store.add_item(
                    name=item["name"],
                    category_name=item.get("category_name"),
                    price=item["price"],
                    description=item.get("description"),
                    plu=item.get("plu"),
                    deliverect_id=item.get("deliverect_item_id"),
                    is_available=item.get("is_available", True),
                    image_url=item.get("image_url")
                )
        
        # Store modifier groups and modifiers
        if processed_data.get("modifier_groups"):
            logger.info(f"Storing {len(processed_data['modifier_groups'])} modifier groups...")
            for group in processed_data["modifier_groups"]:
                group_id = await menu_store.add_modifier_group(
                    name=group["name"],
                    min_selection=group.get("min_selection", 0),
                    max_selection=group.get("max_selection", 1),
                    deliverect_id=group.get("deliverect_group_id"),
                    plu=group.get("plu")
                )
                
                # Add modifiers to the group
                for modifier in group.get("modifiers", []):
                    await menu_store.add_modifier(
                        name=modifier["name"],
                        modifier_group_name=group["name"],
                        price_change=modifier.get("price_change", 0),
                        plu=modifier.get("plu"),
                        deliverect_id=modifier.get("deliverect_modifier_id"),
                        is_available=modifier.get("is_available", True)
                    )
        
        # Link items to modifier groups
        if processed_data.get("item_modifier_groups"):
            logger.info("Linking items to modifier groups...")
            for link in processed_data["item_modifier_groups"]:
                await menu_store.link_item_to_modifier_group(
                    item_plu=link["item_plu"],
                    modifier_group_name=link["modifier_group_name"]
                )
        
        # Commit all changes
        await db.commit()
        
        # Invalidate menu cache in background
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
        
        menu_store = AsyncMenuDbStore(db)
        
        for item in request.items:
            plu = item.get("plu")
            if not plu:
                continue
                
            if request.action == "snooze":
                # Mark item as unavailable
                snooze_until = item.get("snoozeUntil")  # Optional timestamp
                logger.info(f"Snoozing item with PLU {plu}")
                # TODO: Implement snooze functionality in menu store
                
            elif request.action == "unsnooze":
                # Mark item as available
                logger.info(f"Unsnoozing item with PLU {plu}")
                # TODO: Implement unsnooze functionality in menu store
        
        await db.commit()
        
        # Invalidate cache
        menu_cache.clear_all()
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(f"Error handling {request.action}: {str(e)}", exc_info=True)
        await db.rollback()
        return {"status": "FAILED"}


async def invalidate_menu_cache():
    """Invalidate the menu cache after a successful update."""
    try:
        logger.info("Invalidating menu cache...")
        menu_cache.clear_all()
        logger.info("Menu cache invalidated successfully")
    except Exception as e:
        logger.error(f"Error invalidating menu cache: {str(e)}")