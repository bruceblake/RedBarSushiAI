"""
Menu categories API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu categories.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.schemas.menu import (
    MenuCategoryCreate, MenuCategoryUpdate,
    MenuCategoryResponse, MenuCategoryListResponse
)
from app.db import (
    get_categories, count_categories, get_category,
    create_category, update_category, delete_category
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get(
    "/categories",
    response_model=MenuCategoryListResponse,
    summary="Get All Menu Categories",
    description="Retrieve a list of all menu categories with pagination."
)
async def get_all_categories(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    db: AsyncSession = Depends(get_db)
) -> MenuCategoryListResponse:
    """
    Retrieve a list of all menu categories with pagination and optional location filtering.
    """
    try:
        categories = await get_categories(db, skip=skip, limit=limit, location_id=location_id)
        total = await count_categories(db, location_id=location_id)
        
        return MenuCategoryListResponse(
            categories=[MenuCategoryResponse.from_orm(cat) for cat in categories],
            total=total
        )
    except Exception as e:
        logger.error(f"Error getting menu categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu categories"
        )

@router.get(
    "/categories/{category_id}",
    response_model=MenuCategoryResponse,
    summary="Get Menu Category",
    description="Retrieve a specific menu category by ID."
)
async def get_category_by_id(
    category_id: str = Path(..., description="The ID of the category to retrieve"),
    db: AsyncSession = Depends(get_db)
) -> MenuCategoryResponse:
    """
    Retrieve a specific menu category by ID.
    """
    try:
        category = await get_category(db, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
            
        return MenuCategoryResponse.from_orm(category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting menu category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu category"
        )

@router.post(
    "/categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Category",
    description="Create a new menu category."
)
async def create_new_category(
    category: MenuCategoryCreate,
    location_id: Optional[str] = Query(None, description="Location ID to associate with category"),
    db: AsyncSession = Depends(get_db)
) -> MenuCategoryResponse:
    """
    Create a new menu category.
    """
    try:
        db_category = await create_category(db, category, location_id)
        return MenuCategoryResponse.from_orm(db_category)
    except Exception as e:
        logger.error(f"Error creating menu category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create menu category"
        )

@router.put(
    "/categories/{category_id}",
    response_model=MenuCategoryResponse,
    summary="Update Menu Category",
    description="Update an existing menu category."
)
async def update_existing_category(
    category_id: str = Path(..., description="The ID of the category to update"),
    category: MenuCategoryUpdate = None,
    db: AsyncSession = Depends(get_db)
) -> MenuCategoryResponse:
    """
    Update an existing menu category.
    """
    try:
        db_category = await update_category(db, category_id, category)
        if not db_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
            
        return MenuCategoryResponse.from_orm(db_category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating menu category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update menu category"
        )

@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Menu Category",
    description="Delete a menu category."
)
async def delete_existing_category(
    category_id: str = Path(..., description="The ID of the category to delete"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a menu category.
    """
    try:
        deleted = await delete_category(db, category_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting menu category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete menu category"
        )