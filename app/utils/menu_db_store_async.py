"""
Async menu database store for RedBarSushiAI.

This module provides async access to menu data stored in the database.
It serves as an adapter between database models and the application's menu handling.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.crud_menu_async import (
    get_categories, get_items, get_modifiers, 
    get_modifier_groups, get_variants,
    get_item_by_plu, get_modifier_by_plu
)
from app.models.menu_async import (
    MenuCategory, MenuItem, MenuModifier, MenuModifierGroup
)

# Configure logging
logger = logging.getLogger(__name__)

class AsyncMenuDbStore:
    """
    Async store for menu data from database.
    
    This class provides async access to menu data stored in the database,
    with caching for performance and a consistent interface.
    """
    
    def __init__(self):
        """Initialize the async menu database store."""
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def get_menu_item(self, db: AsyncSession, item_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        Get a menu item by ID.
        
        Args:
            db: Database session
            item_id: Item ID
            
        Returns:
            Menu item as a dictionary, or None if not found
        """
        # Query for the item
        stmt = select(MenuItem).where(MenuItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            return None
            
        # Convert to dictionary
        return item.to_dict()
        
    async def get_modifier_group(self, db: AsyncSession, group_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        Get a modifier group by ID.
        
        Args:
            db: Database session
            group_id: Group ID
            
        Returns:
            Modifier group as a dictionary, or None if not found
        """
        # Query for the group
        stmt = select(MenuModifierGroup).where(MenuModifierGroup.id == group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        
        if not group:
            return None
            
        # Convert to dictionary
        return group.to_dict()
        
    async def get_modifier(self, db: AsyncSession, modifier_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        Get a modifier by ID.
        
        Args:
            db: Database session
            modifier_id: Modifier ID
            
        Returns:
            Modifier as a dictionary, or None if not found
        """
        # Query for the modifier
        stmt = select(MenuModifier).where(MenuModifier.id == modifier_id)
        result = await db.execute(stmt)
        modifier = result.scalar_one_or_none()
        
        if not modifier:
            return None
            
        # Convert to dictionary
        return modifier.to_dict()
        
    async def get_categories(self, db: AsyncSession, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all menu categories.
        
        Args:
            db: Database session
            location_id: Optional location ID to filter by
            
        Returns:
            List of categories as dictionaries
        """
        # Use the imported crud function 
        from app.db.crud_menu_async import get_categories as crud_get_categories
        categories = await crud_get_categories(db, location_id=location_id)
        
        return [category.to_dict() for category in categories]
        
    async def get_items_by_category(self, db: AsyncSession, category_name: str) -> List[Dict[str, Any]]:
        """
        Get all items in a specific category.
        
        Args:
            db: Database session
            category_name: Category name
            
        Returns:
            List of items in the category as dictionaries
        """
        from app.db.crud_menu_async import get_items_by_category as crud_get_items_by_category
        
        # First find the category by name
        stmt = select(MenuCategory).where(MenuCategory.name.ilike(f"%{category_name}%"))
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()
        
        if not category:
            return []
            
        # Now get all items in that category using the CRUD function
        items = await crud_get_items_by_category(db, category.id)
        
        return [item.to_dict() for item in items]
        
    async def get_item_by_plu(self, plu: str, db: Optional[AsyncSession] = None) -> Optional[Dict[str, Any]]:
        """
        Get a menu item by PLU.
        
        Args:
            plu: PLU code
            db: Database session (required)
            
        Returns:
            Menu item as a dictionary, or None if not found
        """
        if not db:
            raise ValueError("Database session is required for get_item_by_plu")
            
        item = await get_item_by_plu(db, plu)
        if not item:
            return None
            
        return item.to_dict()
        
    async def get_modifier_by_plu(self, plu: str, db: Optional[AsyncSession] = None) -> Optional[Dict[str, Any]]:
        """
        Get a modifier by PLU.
        
        Args:
            plu: PLU code
            db: Database session (required)
            
        Returns:
            Modifier as a dictionary, or None if not found
        """
        if not db:
            raise ValueError("Database session is required for get_modifier_by_plu")
            
        modifier = await get_modifier_by_plu(db, plu)
        if not modifier:
            return None
            
        return modifier.to_dict()
        
        
# Create singleton instance
async_menu_db_store = AsyncMenuDbStore()