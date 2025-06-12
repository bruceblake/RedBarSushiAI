"""
Menu items API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu items.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

# JSONResponse removed
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.schemas.menu import (
    MenuItemResponse,
    MenuItemListResponse,
)
from app.db import (
    get_items,
    count_items,
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get(
    "/items",
    response_model=MenuItemListResponse,
    summary="Get All Menu Items",
    description="Retrieve a list of all menu items with pagination.",
)
async def get_all_items(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    available_only: bool = Query(
        False, description="Filter to show only available items"
    ),
    db: AsyncSession = Depends(get_db),
) -> MenuItemListResponse:
    """
    Retrieve a list of all menu items with pagination and optional filtering.
    """
    try:
        items = await get_items(
            db,
            skip=skip,
            limit=limit,
            category_id=category_id,
            location_id=location_id,
            available_only=available_only,
        )
        total = await count_items(
            db,
            category_id=category_id,
            location_id=location_id,
            available_only=available_only,
        )

        return MenuItemListResponse(
            items=[MenuItemResponse.from_orm(item) for item in items], total=total
        )
    except Exception as e:
        logger.error(f"Error getting menu items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu items",
        )
