"""
Async CRUD operations for menu-related models.

This module provides asynchronous create, read, update, and delete operations
for menu categories, items, modifiers, and variants.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu_async import (
    MenuCategory, MenuItem, MenuModifier, MenuModifierGroup, 
    item_modifier_group, group_modifier, MenuNameVariant
)
from app.schemas.menu import (
    MenuCategoryCreate, MenuCategoryUpdate,
    MenuItemCreate, MenuItemUpdate,
    MenuModifierCreate, MenuModifierUpdate,
    MenuModifierGroupCreate, MenuModifierGroupUpdate,
    MenuVariantCreate, MenuVariantUpdate
)

logger = logging.getLogger(__name__)

# Variant CRUD operations
async def get_variants(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    target_plu: Optional[str] = None,
    canonical_name: Optional[str] = None
) -> List[MenuNameVariant]:
    """
    Get all menu name variants with pagination and optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        target_plu: Optional PLU to filter by
        canonical_name: Optional canonical name to filter by
        
    Returns:
        List of MenuNameVariant objects
    """
    query = select(MenuNameVariant).offset(skip).limit(limit).order_by(MenuNameVariant.variant_phrase)
    
    # Add filters if provided
    if target_plu:
        query = query.where(MenuNameVariant.target_plu == target_plu)
        
    if canonical_name:
        query = query.where(MenuNameVariant.canonical_name == canonical_name)
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_variants(
    db: AsyncSession,
    target_plu: Optional[str] = None,
    canonical_name: Optional[str] = None
) -> int:
    """
    Count all menu name variants with optional filtering.
    
    Args:
        db: Database session
        target_plu: Optional PLU to filter by
        canonical_name: Optional canonical name to filter by
        
    Returns:
        Total count of variants
    """
    query = select(func.count()).select_from(MenuNameVariant)
    
    # Add filters if provided
    if target_plu:
        query = query.where(MenuNameVariant.target_plu == target_plu)
        
    if canonical_name:
        query = query.where(MenuNameVariant.canonical_name == canonical_name)
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_variant(db: AsyncSession, variant_id: str) -> Optional[MenuNameVariant]:
    """
    Get a specific menu name variant by ID.
    
    Args:
        db: Database session
        variant_id: Variant ID to retrieve
        
    Returns:
        MenuNameVariant object or None if not found
    """
    query = select(MenuNameVariant).where(MenuNameVariant.id == variant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_variant_by_phrase(
    db: AsyncSession, variant_phrase: str
) -> Optional[MenuNameVariant]:
    """
    Get a specific menu name variant by phrase.
    
    Args:
        db: Database session
        variant_phrase: Variant phrase to retrieve
        
    Returns:
        MenuNameVariant object or None if not found
    """
    # Convert to lowercase for case-insensitive comparison
    phrase = variant_phrase.lower()
    query = select(MenuNameVariant).where(func.lower(MenuNameVariant.variant_phrase) == phrase)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_variant(db: AsyncSession, variant: MenuVariantCreate) -> MenuNameVariant:
    """
    Create a new menu name variant.
    
    Args:
        db: Database session
        variant: Variant data to create
        
    Returns:
        Created MenuNameVariant object
    """
    db_variant = MenuNameVariant(
        variant_phrase=variant.variant_phrase,
        canonical_name=variant.canonical_name,
        target_plu=variant.target_plu
    )
    db.add(db_variant)
    await db.commit()
    await db.refresh(db_variant)
    return db_variant

async def update_variant(
    db: AsyncSession, variant_id: str, variant: MenuVariantUpdate
) -> Optional[MenuNameVariant]:
    """
    Update an existing menu name variant.
    
    Args:
        db: Database session
        variant_id: ID of variant to update
        variant: Updated variant data
        
    Returns:
        Updated MenuNameVariant object or None if not found
    """
    # Get the variant
    db_variant = await get_variant(db, variant_id)
    if not db_variant:
        return None
        
    # Update attributes that are provided
    update_data = variant.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_variant, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_variant)
    return db_variant

async def delete_variant(db: AsyncSession, variant_id: str) -> bool:
    """
    Delete a menu name variant.
    
    Args:
        db: Database session
        variant_id: ID of variant to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the variant
    db_variant = await get_variant(db, variant_id)
    if not db_variant:
        return False
        
    # Delete the variant
    await db.delete(db_variant)
    await db.commit()
    return True

# Category CRUD operations
async def get_categories(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    location_id: Optional[str] = None
) -> List[MenuCategory]:
    """
    Get all menu categories with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        location_id: Optional location ID to filter by
        
    Returns:
        List of MenuCategory objects
    """
    query = select(MenuCategory).offset(skip).limit(limit).order_by(MenuCategory.name)
    
    # Add location filter if provided
    if location_id:
        query = query.where(MenuCategory.location_id == location_id)
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_categories(db: AsyncSession, location_id: Optional[str] = None) -> int:
    """
    Count all menu categories.
    
    Args:
        db: Database session
        location_id: Optional location ID to filter by
        
    Returns:
        Total count of categories
    """
    query = select(func.count()).select_from(MenuCategory)
    
    # Add location filter if provided
    if location_id:
        query = query.where(MenuCategory.location_id == location_id)
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_category(db: AsyncSession, category_id: str) -> Optional[MenuCategory]:
    """
    Get a specific menu category by ID.
    
    Args:
        db: Database session
        category_id: Category ID to retrieve
        
    Returns:
        MenuCategory object or None if not found
    """
    query = select(MenuCategory).where(MenuCategory.id == category_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_category_by_deliverect_id(
    db: AsyncSession, deliverect_id: str
) -> Optional[MenuCategory]:
    """
    Get a specific menu category by Deliverect ID.
    
    Args:
        db: Database session
        deliverect_id: Deliverect category ID to retrieve
        
    Returns:
        MenuCategory object or None if not found
    """
    query = select(MenuCategory).where(MenuCategory.deliverect_category_id == deliverect_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_category(
    db: AsyncSession, category: MenuCategoryCreate, location_id: Optional[str] = None
) -> MenuCategory:
    """
    Create a new menu category.
    
    Args:
        db: Database session
        category: Category data to create
        location_id: Optional location ID to associate with
        
    Returns:
        Created MenuCategory object
    """
    db_category = MenuCategory(
        name=category.name,
        description=category.description,
        deliverect_category_id=category.deliverect_category_id,
        location_id=location_id
    )
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category

async def update_category(
    db: AsyncSession, category_id: str, category: MenuCategoryUpdate
) -> Optional[MenuCategory]:
    """
    Update an existing menu category.
    
    Args:
        db: Database session
        category_id: ID of category to update
        category: Updated category data
        
    Returns:
        Updated MenuCategory object or None if not found
    """
    # Get the category
    db_category = await get_category(db, category_id)
    if not db_category:
        return None
        
    # Update attributes that are provided
    update_data = category.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_category)
    return db_category

async def delete_category(db: AsyncSession, category_id: str) -> bool:
    """
    Delete a menu category.
    
    Args:
        db: Database session
        category_id: ID of category to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the category
    db_category = await get_category(db, category_id)
    if not db_category:
        return False
        
    # Delete the category
    await db.delete(db_category)
    await db.commit()
    return True

# Item CRUD operations
async def get_items(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    category_id: Optional[str] = None,
    location_id: Optional[str] = None,
    available_only: bool = False
) -> List[MenuItem]:
    """
    Get all menu items with pagination and optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        category_id: Optional category ID to filter by
        location_id: Optional location ID to filter by
        available_only: If True, only return available items
        
    Returns:
        List of MenuItem objects
    """
    query = select(MenuItem).offset(skip).limit(limit).order_by(MenuItem.name)
    
    # Add filters if provided
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
        
    if location_id:
        query = query.where(MenuItem.location_id == location_id)
        
    if available_only:
        # Only return items that are available and not snoozed
        query = query.where(MenuItem.is_available == True)
        # Check that the item is not snoozed or the snooze has expired
        query = query.where(
            (MenuItem.snoozed_until == None) | 
            (MenuItem.snoozed_until < datetime.now())
        )
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_items(
    db: AsyncSession,
    category_id: Optional[str] = None,
    location_id: Optional[str] = None,
    available_only: bool = False
) -> int:
    """
    Count all menu items with optional filtering.
    
    Args:
        db: Database session
        category_id: Optional category ID to filter by
        location_id: Optional location ID to filter by
        available_only: If True, only count available items
        
    Returns:
        Total count of items
    """
    query = select(func.count()).select_from(MenuItem)
    
    # Add filters if provided
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
        
    if location_id:
        query = query.where(MenuItem.location_id == location_id)
        
    if available_only:
        # Only count items that are available and not snoozed
        query = query.where(MenuItem.is_available == True)
        # Check that the item is not snoozed or the snooze has expired
        query = query.where(
            (MenuItem.snoozed_until == None) | 
            (MenuItem.snoozed_until < datetime.now())
        )
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_items_by_category(
    db: AsyncSession,
    category_id: str,
    skip: int = 0,
    limit: int = 100,
    available_only: bool = False
) -> List[MenuItem]:
    """
    Get all menu items in a specific category.
    
    Args:
        db: Database session
        category_id: Category ID to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
        available_only: If True, only return available items
        
    Returns:
        List of MenuItem objects
    """
    query = (
        select(MenuItem)
        .where(MenuItem.category_id == category_id)
        .offset(skip)
        .limit(limit)
        .order_by(MenuItem.name)
    )
    
    if available_only:
        # Only return items that are available and not snoozed
        query = query.where(MenuItem.is_available == True)
        # Check that the item is not snoozed or the snooze has expired
        query = query.where(
            (MenuItem.snoozed_until == None) | 
            (MenuItem.snoozed_until < datetime.now())
        )
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_item(db: AsyncSession, item_id: str) -> Optional[MenuItem]:
    """
    Get a specific menu item by ID.
    
    Args:
        db: Database session
        item_id: Item ID to retrieve
        
    Returns:
        MenuItem object or None if not found
    """
    query = select(MenuItem).where(MenuItem.id == item_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_item_by_plu(db: AsyncSession, plu: str) -> Optional[MenuItem]:
    """
    Get a specific menu item by PLU.
    
    Args:
        db: Database session
        plu: PLU to retrieve
        
    Returns:
        MenuItem object or None if not found
    """
    query = select(MenuItem).where(MenuItem.plu == plu)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_item_by_deliverect_id(db: AsyncSession, deliverect_id: str) -> Optional[MenuItem]:
    """
    Get a specific menu item by Deliverect ID.
    
    Args:
        db: Database session
        deliverect_id: Deliverect item ID to retrieve
        
    Returns:
        MenuItem object or None if not found
    """
    query = select(MenuItem).where(MenuItem.deliverect_item_id == deliverect_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_item(db: AsyncSession, item: MenuItemCreate) -> MenuItem:
    """
    Create a new menu item.
    
    Args:
        db: Database session
        item: Item data to create
        
    Returns:
        Created MenuItem object
    """
    db_item = MenuItem(
        name=item.name,
        description=item.description,
        price=item.price,
        plu=item.plu,
        deliverect_item_id=item.deliverect_item_id,
        is_available=item.is_available,
        is_combo=item.is_combo,
        is_variant=item.is_variant,
        image_url=item.image_url,
        category_id=item.category_id,
        properties=item.properties
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def update_item(db: AsyncSession, item_id: str, item: MenuItemUpdate) -> Optional[MenuItem]:
    """
    Update an existing menu item.
    
    Args:
        db: Database session
        item_id: ID of item to update
        item: Updated item data
        
    Returns:
        Updated MenuItem object or None if not found
    """
    # Get the item
    db_item = await get_item(db, item_id)
    if not db_item:
        return None
        
    # Update attributes that are provided
    update_data = item.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def delete_item(db: AsyncSession, item_id: str) -> bool:
    """
    Delete a menu item.
    
    Args:
        db: Database session
        item_id: ID of item to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the item
    db_item = await get_item(db, item_id)
    if not db_item:
        return False
        
    # Delete the item
    await db.delete(db_item)
    await db.commit()
    return True

async def snooze_item(db: AsyncSession, item_id: str, snoozed_until: datetime) -> Optional[MenuItem]:
    """
    Snooze a menu item until a specified time.
    
    Args:
        db: Database session
        item_id: ID of item to snooze
        snoozed_until: Datetime until which the item should be snoozed
        
    Returns:
        Updated MenuItem object or None if not found
    """
    # Get the item
    db_item = await get_item(db, item_id)
    if not db_item:
        return None
        
    # Set snooze until time
    db_item.snoozed_until = snoozed_until
    
    # Commit the changes
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def unsnooze_item(db: AsyncSession, item_id: str) -> Optional[MenuItem]:
    """
    Unsnooze a menu item.
    
    Args:
        db: Database session
        item_id: ID of item to unsnooze
        
    Returns:
        Updated MenuItem object or None if not found
    """
    # Get the item
    db_item = await get_item(db, item_id)
    if not db_item:
        return None
        
    # Remove snooze until time
    db_item.snoozed_until = None
    
    # Commit the changes
    await db.commit()
    await db.refresh(db_item)
    return db_item

# Modifier CRUD Operations
async def get_modifiers(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    group_id: Optional[str] = None,
    location_id: Optional[str] = None,
    available_only: bool = False
) -> List[MenuModifier]:
    """
    Get all menu modifiers with pagination and optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        group_id: Optional modifier group ID to filter by
        location_id: Optional location ID to filter by
        available_only: If True, only return available modifiers
        
    Returns:
        List of MenuModifier objects
    """
    query = select(MenuModifier).offset(skip).limit(limit).order_by(MenuModifier.name)
    
    # Add filters if provided
    if group_id:
        # For group filters, need to use a more complex query with join
        query = (
            select(MenuModifier)
            .join(GroupModifier)
            .where(GroupModifier.c.modifier_group_id == group_id)
            .offset(skip)
            .limit(limit)
            .order_by(MenuModifier.name)
        )
        
    if location_id:
        query = query.where(MenuModifier.location_id == location_id)
        
    if available_only:
        # Only return modifiers that are available and not snoozed
        query = query.where(MenuModifier.is_available == True)
        query = query.where(
            (MenuModifier.snoozed_until == None) | 
            (MenuModifier.snoozed_until < datetime.now())
        )
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_modifiers(
    db: AsyncSession,
    group_id: Optional[str] = None,
    location_id: Optional[str] = None,
    available_only: bool = False
) -> int:
    """
    Count all menu modifiers with optional filtering.
    
    Args:
        db: Database session
        group_id: Optional modifier group ID to filter by
        location_id: Optional location ID to filter by
        available_only: If True, only count available modifiers
        
    Returns:
        Total count of modifiers
    """
    if group_id:
        # For group filters, need to use a more complex query with join
        query = (
            select(func.count())
            .select_from(MenuModifier)
            .join(GroupModifier)
            .where(GroupModifier.c.modifier_group_id == group_id)
        )
    else:
        query = select(func.count()).select_from(MenuModifier)
    
    # Add filters if provided
    if location_id:
        query = query.where(MenuModifier.location_id == location_id)
        
    if available_only:
        # Only count modifiers that are available and not snoozed
        query = query.where(MenuModifier.is_available == True)
        query = query.where(
            (MenuModifier.snoozed_until == None) | 
            (MenuModifier.snoozed_until < datetime.now())
        )
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_modifier(db: AsyncSession, modifier_id: str) -> Optional[MenuModifier]:
    """
    Get a specific menu modifier by ID.
    
    Args:
        db: Database session
        modifier_id: Modifier ID to retrieve
        
    Returns:
        MenuModifier object or None if not found
    """
    query = select(MenuModifier).where(MenuModifier.id == modifier_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_modifier_by_plu(db: AsyncSession, plu: str) -> Optional[MenuModifier]:
    """
    Get a specific menu modifier by PLU.
    
    Args:
        db: Database session
        plu: PLU to retrieve
        
    Returns:
        MenuModifier object or None if not found
    """
    query = select(MenuModifier).where(MenuModifier.plu == plu)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_modifier_by_deliverect_id(
    db: AsyncSession, deliverect_id: str
) -> Optional[MenuModifier]:
    """
    Get a specific menu modifier by Deliverect ID.
    
    Args:
        db: Database session
        deliverect_id: Deliverect modifier ID to retrieve
        
    Returns:
        MenuModifier object or None if not found
    """
    query = select(MenuModifier).where(MenuModifier.deliverect_modifier_id == deliverect_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_modifier(db: AsyncSession, modifier: MenuModifierCreate) -> MenuModifier:
    """
    Create a new menu modifier.
    
    Args:
        db: Database session
        modifier: Modifier data to create
        
    Returns:
        Created MenuModifier object
    """
    db_modifier = MenuModifier(
        name=modifier.name,
        price_change=modifier.price_change,
        plu=modifier.plu,
        deliverect_modifier_id=modifier.deliverect_modifier_id,
        is_available=modifier.is_available,
        modifier_group_id=modifier.modifier_group_id
    )
    db.add(db_modifier)
    await db.commit()
    await db.refresh(db_modifier)
    return db_modifier

async def update_modifier(
    db: AsyncSession, modifier_id: str, modifier: MenuModifierUpdate
) -> Optional[MenuModifier]:
    """
    Update an existing menu modifier.
    
    Args:
        db: Database session
        modifier_id: ID of modifier to update
        modifier: Updated modifier data
        
    Returns:
        Updated MenuModifier object or None if not found
    """
    # Get the modifier
    db_modifier = await get_modifier(db, modifier_id)
    if not db_modifier:
        return None
        
    # Update attributes that are provided
    update_data = modifier.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_modifier, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_modifier)
    return db_modifier

async def delete_modifier(db: AsyncSession, modifier_id: str) -> bool:
    """
    Delete a menu modifier.
    
    Args:
        db: Database session
        modifier_id: ID of modifier to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the modifier
    db_modifier = await get_modifier(db, modifier_id)
    if not db_modifier:
        return False
        
    # Delete the modifier
    await db.delete(db_modifier)
    await db.commit()
    return True

async def snooze_modifier(
    db: AsyncSession, modifier_id: str, snoozed_until: datetime
) -> Optional[MenuModifier]:
    """
    Snooze a menu modifier until a specified time.
    
    Args:
        db: Database session
        modifier_id: ID of modifier to snooze
        snoozed_until: Datetime until which the modifier should be snoozed
        
    Returns:
        Updated MenuModifier object or None if not found
    """
    # Get the modifier
    db_modifier = await get_modifier(db, modifier_id)
    if not db_modifier:
        return None
        
    # Set snooze until time
    db_modifier.snoozed_until = snoozed_until
    
    # Commit the changes
    await db.commit()
    await db.refresh(db_modifier)
    return db_modifier

async def unsnooze_modifier(db: AsyncSession, modifier_id: str) -> Optional[MenuModifier]:
    """
    Unsnooze a menu modifier.
    
    Args:
        db: Database session
        modifier_id: ID of modifier to unsnooze
        
    Returns:
        Updated MenuModifier object or None if not found
    """
    # Get the modifier
    db_modifier = await get_modifier(db, modifier_id)
    if not db_modifier:
        return None
        
    # Remove snooze until time
    db_modifier.snoozed_until = None
    
    # Commit the changes
    await db.commit()
    await db.refresh(db_modifier)
    return db_modifier

# Modifier Group CRUD Operations
async def get_modifier_groups(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    item_id: Optional[str] = None,
    location_id: Optional[str] = None,
    include_modifiers: bool = False
) -> List[MenuModifierGroup]:
    """
    Get all menu modifier groups with pagination and optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        item_id: Optional item ID to filter by (groups associated with the item)
        location_id: Optional location ID to filter by
        include_modifiers: If True, include related modifiers in the result
        
    Returns:
        List of MenuModifierGroup objects
    """
    if include_modifiers:
        query = select(MenuModifierGroup).options(selectinload(MenuModifierGroup.modifiers))
    else:
        query = select(MenuModifierGroup)
    
    query = query.offset(skip).limit(limit).order_by(MenuModifierGroup.name)
    
    # Add filters if provided
    if item_id:
        # For item filters, need to use a more complex query with join
        if include_modifiers:
            query = (
                select(MenuModifierGroup)
                .options(selectinload(MenuModifierGroup.modifiers))
                .join(item_modifier_group)
                .where(item_modifier_group.c.menu_item_id == item_id)
                .offset(skip)
                .limit(limit)
                .order_by(MenuModifierGroup.name)
            )
        else:
            query = (
                select(MenuModifierGroup)
                .join(item_modifier_group)
                .where(item_modifier_group.c.menu_item_id == item_id)
                .offset(skip)
                .limit(limit)
                .order_by(MenuModifierGroup.name)
            )
        
    if location_id:
        query = query.where(MenuModifierGroup.location_id == location_id)
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_modifier_groups(
    db: AsyncSession,
    item_id: Optional[str] = None,
    location_id: Optional[str] = None
) -> int:
    """
    Count all menu modifier groups with optional filtering.
    
    Args:
        db: Database session
        item_id: Optional item ID to filter by (groups associated with the item)
        location_id: Optional location ID to filter by
        
    Returns:
        Total count of modifier groups
    """
    if item_id:
        # For item filters, need to use a more complex query with join
        query = (
            select(func.count())
            .select_from(MenuModifierGroup)
            .join(item_modifier_group)
            .where(item_modifier_group.c.menu_item_id == item_id)
        )
    else:
        query = select(func.count()).select_from(MenuModifierGroup)
    
    # Add filters if provided
    if location_id:
        query = query.where(MenuModifierGroup.location_id == location_id)
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_modifier_group(
    db: AsyncSession, group_id: str, include_modifiers: bool = False
) -> Optional[MenuModifierGroup]:
    """
    Get a specific menu modifier group by ID.
    
    Args:
        db: Database session
        group_id: Group ID to retrieve
        include_modifiers: If True, include related modifiers in the result
        
    Returns:
        MenuModifierGroup object or None if not found
    """
    if include_modifiers:
        query = (
            select(MenuModifierGroup)
            .options(selectinload(MenuModifierGroup.modifiers))
            .where(MenuModifierGroup.id == group_id)
        )
    else:
        query = select(MenuModifierGroup).where(MenuModifierGroup.id == group_id)
        
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_modifier_group_by_plu(
    db: AsyncSession, plu: str, include_modifiers: bool = False
) -> Optional[MenuModifierGroup]:
    """
    Get a specific menu modifier group by PLU.
    
    Args:
        db: Database session
        plu: PLU to retrieve
        include_modifiers: If True, include related modifiers in the result
        
    Returns:
        MenuModifierGroup object or None if not found
    """
    if include_modifiers:
        query = (
            select(MenuModifierGroup)
            .options(selectinload(MenuModifierGroup.modifiers))
            .where(MenuModifierGroup.plu == plu)
        )
    else:
        query = select(MenuModifierGroup).where(MenuModifierGroup.plu == plu)
        
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_modifier_group_by_deliverect_id(
    db: AsyncSession, deliverect_id: str, include_modifiers: bool = False
) -> Optional[MenuModifierGroup]:
    """
    Get a specific menu modifier group by Deliverect ID.
    
    Args:
        db: Database session
        deliverect_id: Deliverect group ID to retrieve
        include_modifiers: If True, include related modifiers in the result
        
    Returns:
        MenuModifierGroup object or None if not found
    """
    if include_modifiers:
        query = (
            select(MenuModifierGroup)
            .options(selectinload(MenuModifierGroup.modifiers))
            .where(MenuModifierGroup.deliverect_group_id == deliverect_id)
        )
    else:
        query = select(MenuModifierGroup).where(MenuModifierGroup.deliverect_group_id == deliverect_id)
        
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_modifier_group(
    db: AsyncSession, group: MenuModifierGroupCreate, location_id: Optional[str] = None
) -> MenuModifierGroup:
    """
    Create a new menu modifier group.
    
    Args:
        db: Database session
        group: Group data to create
        location_id: Optional location ID to associate with
        
    Returns:
        Created MenuModifierGroup object
    """
    db_group = MenuModifierGroup(
        name=group.name,
        min_selection=group.min_selection,
        max_selection=group.max_selection,
        multi_max=group.multi_max,
        plu=group.plu,
        is_variant_group=group.is_variant_group,
        deliverect_group_id=group.deliverect_group_id,
        location_id=location_id
    )
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    return db_group

async def update_modifier_group(
    db: AsyncSession, group_id: str, group: MenuModifierGroupUpdate
) -> Optional[MenuModifierGroup]:
    """
    Update an existing menu modifier group.
    
    Args:
        db: Database session
        group_id: ID of group to update
        group: Updated group data
        
    Returns:
        Updated MenuModifierGroup object or None if not found
    """
    # Get the group
    db_group = await get_modifier_group(db, group_id)
    if not db_group:
        return None
        
    # Update attributes that are provided
    update_data = group.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_group, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_group)
    return db_group

async def delete_modifier_group(db: AsyncSession, group_id: str) -> bool:
    """
    Delete a menu modifier group.
    
    Args:
        db: Database session
        group_id: ID of group to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the group
    db_group = await get_modifier_group(db, group_id)
    if not db_group:
        return False
        
    # Delete the group
    await db.delete(db_group)
    await db.commit()
    return True

# Association Management Operations
async def add_modifier_to_group(
    db: AsyncSession, group_id: str, modifier_id: str
) -> Optional[MenuModifierGroup]:
    """
    Add a modifier to a modifier group.
    
    Args:
        db: Database session
        group_id: ID of group to add modifier to
        modifier_id: ID of modifier to add
        
    Returns:
        Updated MenuModifierGroup object or None if not found
    """
    # Get the group and modifier
    db_group = await get_modifier_group(db, group_id, include_modifiers=True)
    db_modifier = await get_modifier(db, modifier_id)
    
    if not db_group or not db_modifier:
        return None
        
    # Add modifier to group if not already present
    if db_modifier not in db_group.modifiers:
        db_group.modifiers.append(db_modifier)
        await db.commit()
        await db.refresh(db_group)
        
    return db_group

async def remove_modifier_from_group(
    db: AsyncSession, group_id: str, modifier_id: str
) -> Optional[MenuModifierGroup]:
    """
    Remove a modifier from a modifier group.
    
    Args:
        db: Database session
        group_id: ID of group to remove modifier from
        modifier_id: ID of modifier to remove
        
    Returns:
        Updated MenuModifierGroup object or None if not found
    """
    # Get the group
    db_group = await get_modifier_group(db, group_id, include_modifiers=True)
    
    if not db_group:
        return None
        
    # Find the modifier in the group
    for modifier in db_group.modifiers:
        if str(modifier.id) == modifier_id:
            db_group.modifiers.remove(modifier)
            await db.commit()
            await db.refresh(db_group)
            break
            
    return db_group

async def add_modifier_group_to_item(
    db: AsyncSession, item_id: str, group_id: str
) -> Optional[MenuItem]:
    """
    Add a modifier group to a menu item.
    
    Args:
        db: Database session
        item_id: ID of item to add group to
        group_id: ID of group to add
        
    Returns:
        Updated MenuItem object or None if not found
    """
    # Get the item and group with relationships loaded
    query_item = select(MenuItem).options(selectinload(MenuItem.modifier_groups)).where(MenuItem.id == item_id)
    result_item = await db.execute(query_item)
    db_item = result_item.scalar_one_or_none()
    
    db_group = await get_modifier_group(db, group_id)
    
    if not db_item or not db_group:
        return None
        
    # Add group to item if not already present
    if db_group not in db_item.modifier_groups:
        db_item.modifier_groups.append(db_group)
        await db.commit()
        await db.refresh(db_item)
        
    return db_item

async def remove_modifier_group_from_item(
    db: AsyncSession, item_id: str, group_id: str
) -> Optional[MenuItem]:
    """
    Remove a modifier group from a menu item.
    
    Args:
        db: Database session
        item_id: ID of item to remove group from
        group_id: ID of group to remove
        
    Returns:
        Updated MenuItem object or None if not found
    """
    # Get the item with relationships loaded
    query_item = select(MenuItem).options(selectinload(MenuItem.modifier_groups)).where(MenuItem.id == item_id)
    result_item = await db.execute(query_item)
    db_item = result_item.scalar_one_or_none()
    
    if not db_item:
        return None
        
    # Find the group in the item
    for group in db_item.modifier_groups:
        if str(group.id) == group_id:
            db_item.modifier_groups.remove(group)
            await db.commit()
            await db.refresh(db_item)
            break
            
    return db_item