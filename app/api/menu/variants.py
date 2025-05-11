"""
Menu name variants API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu name variants, which map
natural language phrases to canonical item names and PLUs.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.schemas.menu import (
    MenuVariantCreate, MenuVariantUpdate, MenuVariantResponse, MenuVariantListResponse
)
from app.db.crud_menu_async import (
    get_variants, count_variants, get_variant, get_variant_by_phrase,
    create_variant, update_variant, delete_variant
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get(
    "/variants", 
    response_model=MenuVariantListResponse,
    summary="Get All Menu Name Variants",
    description="Retrieve a list of all menu name variants with pagination and optional filtering."
)
async def get_all_variants(
    skip: int = 0, 
    limit: int = 100,
    target_plu: Optional[str] = None,
    canonical_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all menu name variants with pagination and optional filtering.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        target_plu: Optional PLU to filter by
        canonical_name: Optional canonical name to filter by
        db: Database session
        
    Returns:
        Dictionary containing variants list and total count
    """
    variants = await get_variants(
        db, skip=skip, limit=limit, 
        target_plu=target_plu, canonical_name=canonical_name
    )
    total = await count_variants(
        db, target_plu=target_plu, canonical_name=canonical_name
    )
    
    return {"variants": variants, "total": total}

@router.get(
    "/variants/{variant_id}", 
    response_model=MenuVariantResponse,
    summary="Get Menu Name Variant by ID",
    description="Retrieve a specific menu name variant by its ID."
)
async def get_variant_by_id(
    variant_id: str = Path(..., title="The ID of the variant to retrieve"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a specific menu name variant by ID.
    
    Args:
        variant_id: ID of the variant to retrieve
        db: Database session
        
    Returns:
        Variant object
        
    Raises:
        HTTPException: If the variant is not found
    """
    db_variant = await get_variant(db, variant_id)
    if db_variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found"
        )
    return db_variant

@router.get(
    "/variants/phrase/{phrase}", 
    response_model=MenuVariantResponse,
    summary="Get Menu Name Variant by Phrase",
    description="Retrieve a specific menu name variant by its phrase (case-insensitive)."
)
async def get_variant_by_phrase_endpoint(
    phrase: str = Path(..., title="The phrase to search for"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a specific menu name variant by phrase.
    
    Args:
        phrase: Variant phrase to retrieve
        db: Database session
        
    Returns:
        Variant object
        
    Raises:
        HTTPException: If the variant is not found
    """
    db_variant = await get_variant_by_phrase(db, phrase)
    if db_variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with phrase '{phrase}' not found"
        )
    return db_variant

@router.post(
    "/variants", 
    response_model=MenuVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Name Variant",
    description="Create a new menu name variant."
)
async def create_new_variant(
    variant: MenuVariantCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Create a new menu name variant.
    
    Args:
        variant: Variant data
        db: Database session
        
    Returns:
        Created variant object
    """
    # Check if a variant with the same phrase already exists
    existing_variant = await get_variant_by_phrase(db, variant.variant_phrase)
    if existing_variant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Variant with phrase '{variant.variant_phrase}' already exists"
        )
        
    return await create_variant(db, variant)

@router.put(
    "/variants/{variant_id}", 
    response_model=MenuVariantResponse,
    summary="Update Menu Name Variant",
    description="Update an existing menu name variant by its ID."
)
async def update_existing_variant(
    variant: MenuVariantUpdate,
    variant_id: str = Path(..., title="The ID of the variant to update"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Update a menu name variant.
    
    Args:
        variant: Updated variant data
        variant_id: ID of the variant to update
        db: Database session
        
    Returns:
        Updated variant object
        
    Raises:
        HTTPException: If the variant is not found
    """
    # Check if updating the phrase to one that already exists
    if variant.variant_phrase:
        existing_variant = await get_variant_by_phrase(db, variant.variant_phrase)
        if existing_variant and str(existing_variant.id) != variant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another variant with phrase '{variant.variant_phrase}' already exists"
            )
    
    db_variant = await update_variant(db, variant_id, variant)
    if db_variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found"
        )
    return db_variant

@router.delete(
    "/variants/{variant_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Menu Name Variant",
    description="Delete a menu name variant by its ID."
)
async def delete_existing_variant(
    variant_id: str = Path(..., title="The ID of the variant to delete"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a menu name variant.
    
    Args:
        variant_id: ID of the variant to delete
        db: Database session
        
    Raises:
        HTTPException: If the variant is not found
    """
    success = await delete_variant(db, variant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found"
        )
        
@router.post(
    "/variants/bulk", 
    response_model=Dict[str, int],
    summary="Bulk Create Menu Name Variants",
    description="Create multiple menu name variants in a single request."
)
async def bulk_create_variants(
    variants: List[MenuVariantCreate],
    db: AsyncSession = Depends(get_db)
) -> Dict[str, int]:
    """
    Create multiple menu name variants in a single request.
    
    Args:
        variants: List of variant data to create
        db: Database session
        
    Returns:
        Dictionary with count of created variants
    """
    created_count = 0
    for variant in variants:
        # Check if a variant with the same phrase already exists
        existing_variant = await get_variant_by_phrase(db, variant.variant_phrase)
        if not existing_variant:
            await create_variant(db, variant)
            created_count += 1
            
    return {"created_count": created_count}