"""
Menu items API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu items.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.schemas.menu import (
    MenuItemCreate, MenuItemUpdate, MenuItemResponse, 
    MenuItemListResponse, SnoozeRequest, SnoozeResponse
)
from app.db.crud_menu_async import (
    get_items, count_items, get_item, get_items_by_category,
    create_item, update_item, delete_item, snooze_item, unsnooze_item
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get(
    "/items",
    response_model=MenuItemListResponse,
    summary="Get All Menu Items",
    description="Retrieve a list of all menu items with pagination."
)
async def get_all_items(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    available_only: bool = Query(False, description="Filter to show only available items"),
    db: AsyncSession = Depends(get_db)
) -> MenuItemListResponse:
    """
    Retrieve a list of all menu items with pagination and optional filtering.
    """
    try:
        items = await get_items(
            db, skip=skip, limit=limit, 
            category_id=category_id, location_id=location_id,
            available_only=available_only
        )
        total = await count_items(
            db, category_id=category_id, location_id=location_id,
            available_only=available_only
        )
        
        return MenuItemListResponse(
            items=[MenuItemResponse.from_orm(item) for item in items],
            total=total
        )
    except Exception as e:
        logger.error(f"Error getting menu items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu items"
        )

@router.get(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Get Menu Item",
    description="Retrieve a specific menu item by ID."
)
async def get_item_by_id(
    item_id: str = Path(..., description="The ID of the item to retrieve"),
    db: AsyncSession = Depends(get_db)
) -> MenuItemResponse:
    """
    Retrieve a specific menu item by ID.
    """
    try:
        item = await get_item(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found"
            )
            
        return MenuItemResponse.from_orm(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting menu item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu item"
        )

@router.get(
    "/categories/{category_id}/items",
    response_model=MenuItemListResponse,
    summary="Get Items by Category",
    description="Retrieve all menu items in a specific category."
)
async def get_items_in_category(
    category_id: str = Path(..., description="The ID of the category"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    available_only: bool = Query(False, description="Filter to show only available items"),
    db: AsyncSession = Depends(get_db)
) -> MenuItemListResponse:
    """
    Retrieve all menu items in a specific category.
    """
    try:
        items = await get_items_by_category(
            db, category_id, skip=skip, limit=limit, available_only=available_only
        )
        total = await count_items(db, category_id=category_id, available_only=available_only)
        
        return MenuItemListResponse(
            items=[MenuItemResponse.from_orm(item) for item in items],
            total=total
        )
    except Exception as e:
        logger.error(f"Error getting menu items for category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu items for category"
        )

@router.post(
    "/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Item",
    description="Create a new menu item."
)
async def create_new_item(
    item: MenuItemCreate,
    db: AsyncSession = Depends(get_db)
) -> MenuItemResponse:
    """
    Create a new menu item.
    """
    try:
        db_item = await create_item(db, item)
        return MenuItemResponse.from_orm(db_item)
    except Exception as e:
        logger.error(f"Error creating menu item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create menu item"
        )

@router.put(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Update Menu Item",
    description="Update an existing menu item."
)
async def update_existing_item(
    item_id: str = Path(..., description="The ID of the item to update"),
    item: MenuItemUpdate = None,
    db: AsyncSession = Depends(get_db)
) -> MenuItemResponse:
    """
    Update an existing menu item.
    """
    try:
        db_item = await update_item(db, item_id, item)
        if not db_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found"
            )
            
        return MenuItemResponse.from_orm(db_item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating menu item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update menu item"
        )

@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Menu Item",
    description="Delete a menu item."
)
async def delete_existing_item(
    item_id: str = Path(..., description="The ID of the item to delete"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a menu item.
    """
    try:
        deleted = await delete_item(db, item_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting menu item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete menu item"
        )

@router.post(
    "/items/{item_id}/snooze",
    response_model=SnoozeResponse,
    summary="Snooze Menu Item",
    description="Temporarily mark a menu item as unavailable."
)
async def snooze_menu_item(
    item_id: str = Path(..., description="The ID of the item to snooze"),
    snooze_request: SnoozeRequest = None,
    db: AsyncSession = Depends(get_db)
) -> SnoozeResponse:
    """
    Temporarily mark a menu item as unavailable (snooze) or make it available again (unsnooze).
    """
    try:
        # Default to simple snooze request if none provided
        if not snooze_request:
            snooze_request = SnoozeRequest(item_id=item_id)
            
        # Ensure item ID matches the path parameter
        if snooze_request.item_id != item_id:
            snooze_request.item_id = item_id
            
        # Snooze or unsnooze based on request
        if snooze_request.snooze:
            snoozed_until = datetime.now() + timedelta(minutes=snooze_request.duration_minutes or 60)
            result = await snooze_item(db, item_id, snoozed_until)
            action = "snoozed"
        else:
            result = await unsnooze_item(db, item_id)
            action = "unsnoozed"
            
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found"
            )
            
        # Build response
        return SnoozeResponse(
            item_id=result.id,
            name=result.name,
            snoozed=bool(result.snoozed_until and result.snoozed_until > datetime.now()),
            snoozed_until=result.snoozed_until,
            message=f"Item '{result.name}' successfully {action}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error snoozing/unsnoozing menu item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to snooze/unsnooze menu item"
        )