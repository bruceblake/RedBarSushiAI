"""
Menu API routes for modifiers and modifier groups.

This module provides FastAPI endpoints for managing menu modifiers and modifier groups.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_async import get_db
from app.db import (
    get_modifiers, count_modifiers, get_modifier, create_modifier, update_modifier,
    delete_modifier, snooze_modifier, unsnooze_modifier,
    get_modifier_groups, count_modifier_groups, get_modifier_group, 
    create_modifier_group, update_modifier_group, delete_modifier_group,
    add_modifier_to_group, remove_modifier_from_group,
    add_modifier_group_to_item, remove_modifier_group_from_item
)
from app.schemas.menu import (
    MenuModifierCreate, MenuModifierUpdate, MenuModifierResponse, MenuModifierListResponse,
    MenuModifierGroupCreate, MenuModifierGroupUpdate, MenuModifierGroupResponse, 
    MenuModifierGroupListResponse, SnoozeRequest, SnoozeResponse
)

# Create router
router = APIRouter()

# Modifier endpoints
@router.get(
    "/modifiers", 
    response_model=MenuModifierListResponse,
    summary="Get All Menu Modifiers",
    description="Retrieve a list of all menu modifiers with pagination and optional filtering."
)
async def get_all_modifiers(
    skip: int = 0, 
    limit: int = 100,
    group_id: Optional[str] = None,
    location_id: Optional[str] = None,
    available_only: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all modifiers with pagination and optional filtering.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        group_id: Optional modifier group ID to filter by
        location_id: Optional location ID to filter by
        available_only: If True, only return available modifiers
        db: Database session
        
    Returns:
        Dictionary containing modifiers list and total count
    """
    modifiers = await get_modifiers(
        db, skip=skip, limit=limit, group_id=group_id, 
        location_id=location_id, available_only=available_only
    )
    total = await count_modifiers(
        db, group_id=group_id, location_id=location_id, available_only=available_only
    )
    
    return {"modifiers": modifiers, "total": total}

@router.get(
    "/modifiers/{modifier_id}", 
    response_model=MenuModifierResponse,
    summary="Get Menu Modifier by ID",
    description="Retrieve a specific menu modifier by its ID."
)
async def get_modifier_by_id(
    modifier_id: str = Path(..., title="The ID of the modifier to retrieve"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a specific modifier by ID.
    
    Args:
        modifier_id: ID of the modifier to retrieve
        db: Database session
        
    Returns:
        Modifier object
        
    Raises:
        HTTPException: If the modifier is not found
    """
    db_modifier = await get_modifier(db, modifier_id)
    if db_modifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier with ID {modifier_id} not found"
        )
    return db_modifier

@router.post(
    "/modifiers", 
    response_model=MenuModifierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Modifier",
    description="Create a new menu modifier."
)
async def create_new_modifier(
    modifier: MenuModifierCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Create a new modifier.
    
    Args:
        modifier: Modifier data
        db: Database session
        
    Returns:
        Created modifier object
    """
    return await create_modifier(db, modifier)

@router.put(
    "/modifiers/{modifier_id}", 
    response_model=MenuModifierResponse,
    summary="Update Menu Modifier",
    description="Update an existing menu modifier by its ID."
)
async def update_existing_modifier(
    modifier: MenuModifierUpdate,
    modifier_id: str = Path(..., title="The ID of the modifier to update"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Update a modifier.
    
    Args:
        modifier: Updated modifier data
        modifier_id: ID of the modifier to update
        db: Database session
        
    Returns:
        Updated modifier object
        
    Raises:
        HTTPException: If the modifier is not found
    """
    db_modifier = await update_modifier(db, modifier_id, modifier)
    if db_modifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier with ID {modifier_id} not found"
        )
    return db_modifier

@router.delete(
    "/modifiers/{modifier_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Menu Modifier",
    description="Delete a menu modifier by its ID."
)
async def delete_existing_modifier(
    modifier_id: str = Path(..., title="The ID of the modifier to delete"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a modifier.
    
    Args:
        modifier_id: ID of the modifier to delete
        db: Database session
        
    Raises:
        HTTPException: If the modifier is not found
    """
    success = await delete_modifier(db, modifier_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier with ID {modifier_id} not found"
        )

@router.post(
    "/modifiers/{modifier_id}/snooze", 
    response_model=SnoozeResponse,
    summary="Snooze Menu Modifier",
    description="Temporarily mark a menu modifier as unavailable."
)
async def snooze_modifier_by_id(
    snooze_request: SnoozeRequest,
    modifier_id: str = Path(..., title="The ID of the modifier to snooze/unsnooze"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Snooze or unsnooze a modifier.
    
    Args:
        snooze_request: Snooze request data
        modifier_id: ID of the modifier to snooze/unsnooze
        db: Database session
        
    Returns:
        Dictionary with snooze status
        
    Raises:
        HTTPException: If the modifier is not found
    """
    # Get the modifier
    db_modifier = await get_modifier(db, modifier_id)
    if db_modifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier with ID {modifier_id} not found"
        )
    
    # Snooze or unsnooze the modifier
    if snooze_request.snooze:
        # Calculate snooze until time
        snooze_until = datetime.now() + timedelta(minutes=snooze_request.duration_minutes)
        db_modifier = await snooze_modifier(db, modifier_id, snooze_until)
        message = f"Modifier '{db_modifier.name}' snoozed for {snooze_request.duration_minutes} minutes"
    else:
        db_modifier = await unsnooze_modifier(db, modifier_id)
        message = f"Modifier '{db_modifier.name}' is now available"
    
    # Return response
    return {
        "item_id": str(db_modifier.id),
        "name": db_modifier.name,
        "snoozed": db_modifier.snoozed_until is not None and db_modifier.snoozed_until > datetime.now(),
        "snoozed_until": db_modifier.snoozed_until,
        "message": message
    }

# Modifier Group endpoints
@router.get(
    "/modifier_groups", 
    response_model=MenuModifierGroupListResponse,
    summary="Get All Menu Modifier Groups",
    description="Retrieve a list of all menu modifier groups with pagination and optional filtering."
)
async def get_all_modifier_groups(
    skip: int = 0, 
    limit: int = 100,
    item_id: Optional[str] = None,
    location_id: Optional[str] = None,
    include_modifiers: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all modifier groups with pagination and optional filtering.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        item_id: Optional item ID to filter by
        location_id: Optional location ID to filter by
        include_modifiers: If True, include related modifiers in the result
        db: Database session
        
    Returns:
        Dictionary containing modifier groups list and total count
    """
    groups = await get_modifier_groups(
        db, skip=skip, limit=limit, item_id=item_id,
        location_id=location_id, include_modifiers=include_modifiers
    )
    total = await count_modifier_groups(
        db, item_id=item_id, location_id=location_id
    )
    
    return {"modifier_groups": groups, "total": total}

@router.get(
    "/modifier_groups/{group_id}", 
    response_model=MenuModifierGroupResponse,
    summary="Get Menu Modifier Group by ID",
    description="Retrieve a specific menu modifier group by its ID."
)
async def get_modifier_group_by_id(
    group_id: str = Path(..., title="The ID of the modifier group to retrieve"),
    include_modifiers: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a specific modifier group by ID.
    
    Args:
        group_id: ID of the modifier group to retrieve
        include_modifiers: If True, include related modifiers in the result
        db: Database session
        
    Returns:
        Modifier group object
        
    Raises:
        HTTPException: If the modifier group is not found
    """
    db_group = await get_modifier_group(db, group_id, include_modifiers=include_modifiers)
    if db_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier group with ID {group_id} not found"
        )
    return db_group

@router.post(
    "/modifier_groups", 
    response_model=MenuModifierGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Modifier Group",
    description="Create a new menu modifier group."
)
async def create_new_modifier_group(
    group: MenuModifierGroupCreate,
    location_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Create a new modifier group.
    
    Args:
        group: Modifier group data
        location_id: Optional location ID to associate with
        db: Database session
        
    Returns:
        Created modifier group object
    """
    return await create_modifier_group(db, group, location_id=location_id)

@router.put(
    "/modifier_groups/{group_id}", 
    response_model=MenuModifierGroupResponse,
    summary="Update Menu Modifier Group",
    description="Update an existing menu modifier group by its ID."
)
async def update_existing_modifier_group(
    group: MenuModifierGroupUpdate,
    group_id: str = Path(..., title="The ID of the modifier group to update"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Update a modifier group.
    
    Args:
        group: Updated modifier group data
        group_id: ID of the modifier group to update
        db: Database session
        
    Returns:
        Updated modifier group object
        
    Raises:
        HTTPException: If the modifier group is not found
    """
    db_group = await update_modifier_group(db, group_id, group)
    if db_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier group with ID {group_id} not found"
        )
    return db_group

@router.delete(
    "/modifier_groups/{group_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Menu Modifier Group",
    description="Delete a menu modifier group by its ID."
)
async def delete_existing_modifier_group(
    group_id: str = Path(..., title="The ID of the modifier group to delete"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a modifier group.
    
    Args:
        group_id: ID of the modifier group to delete
        db: Database session
        
    Raises:
        HTTPException: If the modifier group is not found
    """
    success = await delete_modifier_group(db, group_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier group with ID {group_id} not found"
        )

# Association management endpoints
@router.post(
    "/modifier_groups/{group_id}/modifiers/{modifier_id}",
    response_model=MenuModifierGroupResponse,
    summary="Add Modifier to Group",
    description="Add a modifier to a modifier group."
)
async def add_modifier_to_group_endpoint(
    group_id: str = Path(..., title="The ID of the modifier group"),
    modifier_id: str = Path(..., title="The ID of the modifier to add"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Add a modifier to a modifier group.
    
    Args:
        group_id: ID of the modifier group
        modifier_id: ID of the modifier to add
        db: Database session
        
    Returns:
        Updated modifier group object
        
    Raises:
        HTTPException: If either the modifier group or modifier is not found
    """
    db_group = await add_modifier_to_group(db, group_id, modifier_id)
    if db_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Modifier group or modifier not found"
        )
    return db_group

@router.delete(
    "/modifier_groups/{group_id}/modifiers/{modifier_id}",
    response_model=MenuModifierGroupResponse,
    summary="Remove Modifier from Group",
    description="Remove a modifier from a modifier group."
)
async def remove_modifier_from_group_endpoint(
    group_id: str = Path(..., title="The ID of the modifier group"),
    modifier_id: str = Path(..., title="The ID of the modifier to remove"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Remove a modifier from a modifier group.
    
    Args:
        group_id: ID of the modifier group
        modifier_id: ID of the modifier to remove
        db: Database session
        
    Returns:
        Updated modifier group object
        
    Raises:
        HTTPException: If the modifier group is not found
    """
    db_group = await remove_modifier_from_group(db, group_id, modifier_id)
    if db_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modifier group with ID {group_id} not found"
        )
    return db_group

@router.post(
    "/items/{item_id}/modifier_groups/{group_id}",
    summary="Add Modifier Group to Item",
    description="Add a modifier group to a menu item."
)
async def add_modifier_group_to_item_endpoint(
    item_id: str = Path(..., title="The ID of the menu item"),
    group_id: str = Path(..., title="The ID of the modifier group to add"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Add a modifier group to a menu item.
    
    Args:
        item_id: ID of the menu item
        group_id: ID of the modifier group to add
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If either the menu item or modifier group is not found
    """
    db_item = await add_modifier_group_to_item(db, item_id, group_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item or modifier group not found"
        )
    return {"message": f"Modifier group added to item '{db_item.name}'"}

@router.delete(
    "/items/{item_id}/modifier_groups/{group_id}",
    summary="Remove Modifier Group from Item",
    description="Remove a modifier group from a menu item."
)
async def remove_modifier_group_from_item_endpoint(
    item_id: str = Path(..., title="The ID of the menu item"),
    group_id: str = Path(..., title="The ID of the modifier group to remove"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Remove a modifier group from a menu item.
    
    Args:
        item_id: ID of the menu item
        group_id: ID of the modifier group to remove
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If the menu item is not found
    """
    db_item = await remove_modifier_group_from_item(db, item_id, group_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item with ID {item_id} not found"
        )
    return {"message": f"Modifier group removed from item '{db_item.name}'"}