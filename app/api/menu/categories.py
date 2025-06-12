"""
Menu categories API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu categories.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

# JSONResponse removed
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.schemas.menu import (
    MenuCategoryResponse,
    MenuCategoryListResponse,
)
from app.db import (
    get_categories,
    count_categories,
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get(
    "/categories",
    response_model=MenuCategoryListResponse,
    summary="Get All Menu Categories",
    description="Retrieve a list of all menu categories with pagination.",
)
async def get_all_categories(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    db: AsyncSession = Depends(get_db),
) -> MenuCategoryListResponse:
    """
    Retrieve a list of all menu categories with pagination and optional location filtering.
    """
    try:
        categories = await get_categories(
            db, skip=skip, limit=limit, location_id=location_id
        )
        total = await count_categories(db, location_id=location_id)

        return MenuCategoryListResponse(
            categories=[MenuCategoryResponse.from_orm(cat) for cat in categories],
            total=total,
        )
    except Exception as e:
        logger.error(f"Error getting menu categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu categories",
        )
