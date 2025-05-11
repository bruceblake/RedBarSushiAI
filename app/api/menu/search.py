"""
Menu search API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for searching menu items, categories, modifiers, 
and variants using various search criteria.
"""

import logging
from typing import Optional, Dict, Any, List, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, func, select

from app.db_async import get_db
from app.models.menu_async import MenuItem, MenuCategory, MenuModifier, MenuNameVariant
from app.schemas.menu import (
    MenuItemResponse, MenuCategoryResponse, 
    MenuModifierResponse, MenuVariantResponse
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Define a Pydantic model for search results
from pydantic import BaseModel
from datetime import datetime

class SearchResult(BaseModel):
    """Model for search results across different menu entities."""
    type: str  # 'item', 'category', 'modifier', or 'variant'
    id: str
    name: str
    description: Optional[str] = None
    plu: Optional[str] = None
    price: Optional[float] = None
    match_reason: str  # Why this result matched (e.g., 'name', 'description', etc.)
    relevance_score: float = 1.0
    
    class Config:
        orm_mode = True

class SearchResponse(BaseModel):
    """Model for search response with categorized results."""
    items: List[MenuItemResponse] = []
    categories: List[MenuCategoryResponse] = []
    modifiers: List[MenuModifierResponse] = []
    variants: List[MenuVariantResponse] = []
    total: int = 0

@router.get(
    "/search", 
    response_model=SearchResponse,
    summary="Search Menu",
    description="Search menu items, categories, modifiers, and variants by name and description."
)
async def search_menu(
    query: str = Query(..., description="Search query string"),
    include_items: bool = Query(True, description="Include items in search results"),
    include_categories: bool = Query(True, description="Include categories in search results"),
    include_modifiers: bool = Query(True, description="Include modifiers in search results"),
    include_variants: bool = Query(True, description="Include variants in search results"),
    limit: int = Query(20, description="Maximum number of results to return"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Search menu items, categories, modifiers, and variants by name and description.
    
    Args:
        query: Search query string
        include_items: Include items in search results
        include_categories: Include categories in search results
        include_modifiers: Include modifiers in search results
        include_variants: Include variants in search results
        limit: Maximum number of results to return
        db: Database session
        
    Returns:
        Dictionary containing search results categorized by entity type
    """
    # Prepare search pattern (adding wildcards)
    search_pattern = f"%{query}%"
    
    # Initialize result containers
    items = []
    categories = []
    modifiers = []
    variants = []
    total = 0
    
    # Search menu items if requested
    if include_items:
        items_query = (
            select(MenuItem)
            .where(
                or_(
                    MenuItem.name.ilike(search_pattern),
                    MenuItem.description.ilike(search_pattern),
                    MenuItem.plu.ilike(search_pattern)
                )
            )
            .limit(limit)
        )
        result = await db.execute(items_query)
        items = list(result.scalars().all())
        total += len(items)
    
    # Search categories if requested
    if include_categories:
        categories_query = (
            select(MenuCategory)
            .where(
                or_(
                    MenuCategory.name.ilike(search_pattern),
                    MenuCategory.description.ilike(search_pattern)
                )
            )
            .limit(limit)
        )
        result = await db.execute(categories_query)
        categories = list(result.scalars().all())
        total += len(categories)
    
    # Search modifiers if requested
    if include_modifiers:
        modifiers_query = (
            select(MenuModifier)
            .where(
                or_(
                    MenuModifier.name.ilike(search_pattern),
                    MenuModifier.plu.ilike(search_pattern)
                )
            )
            .limit(limit)
        )
        result = await db.execute(modifiers_query)
        modifiers = list(result.scalars().all())
        total += len(modifiers)
    
    # Search variants if requested
    if include_variants:
        variants_query = (
            select(MenuNameVariant)
            .where(
                or_(
                    MenuNameVariant.variant_phrase.ilike(search_pattern),
                    MenuNameVariant.canonical_name.ilike(search_pattern),
                    MenuNameVariant.target_plu.ilike(search_pattern)
                )
            )
            .limit(limit)
        )
        result = await db.execute(variants_query)
        variants = list(result.scalars().all())
        total += len(variants)
    
    # Return results
    return {
        "items": items,
        "categories": categories,
        "modifiers": modifiers,
        "variants": variants,
        "total": total
    }

@router.get(
    "/search/items", 
    response_model=List[MenuItemResponse],
    summary="Search Menu Items",
    description="Search menu items by name, description, or PLU."
)
async def search_items(
    query: str = Query(..., description="Search query string"),
    limit: int = Query(20, description="Maximum number of results to return"),
    db: AsyncSession = Depends(get_db)
) -> List[Any]:
    """
    Search menu items by name, description, or PLU.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        db: Database session
        
    Returns:
        List of matching menu items
    """
    # Prepare search pattern
    search_pattern = f"%{query}%"
    
    # Search items
    items_query = (
        select(MenuItem)
        .where(
            or_(
                MenuItem.name.ilike(search_pattern),
                MenuItem.description.ilike(search_pattern),
                MenuItem.plu.ilike(search_pattern)
            )
        )
        .limit(limit)
    )
    result = await db.execute(items_query)
    items = list(result.scalars().all())
    
    return items

@router.get(
    "/search/variants/match", 
    response_model=Optional[MenuVariantResponse],
    summary="Match Menu Name Variant",
    description="Find a matching menu name variant for a given phrase."
)
async def match_variant(
    phrase: str = Query(..., description="The phrase to match"),
    db: AsyncSession = Depends(get_db)
) -> Optional[Any]:
    """
    Find a matching menu name variant for a given phrase.
    
    This is useful for natural language matching of menu items.
    
    Args:
        phrase: The phrase to match
        db: Database session
        
    Returns:
        Matching menu name variant or None if no match found
    """
    # First try exact match (case-insensitive)
    exact_match_query = (
        select(MenuNameVariant)
        .where(func.lower(MenuNameVariant.variant_phrase) == phrase.lower())
        .limit(1)
    )
    result = await db.execute(exact_match_query)
    exact_match = result.scalar_one_or_none()
    
    if exact_match:
        return exact_match
    
    # Then try fuzzy match (contains)
    search_pattern = f"%{phrase}%"
    fuzzy_match_query = (
        select(MenuNameVariant)
        .where(MenuNameVariant.variant_phrase.ilike(search_pattern))
        .limit(1)
    )
    result = await db.execute(fuzzy_match_query)
    fuzzy_match = result.scalar_one_or_none()
    
    return fuzzy_match