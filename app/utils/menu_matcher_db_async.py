"""
Async menu matcher for database operations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.menu_async import MenuItem, MenuModifier, MenuModifierGroup
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class AsyncMenuMatcher:
    """
    Base async menu matcher that provides menu item lookup functionality.
    """
    
    def __init__(self, db: AsyncSession, location_id: Optional[str] = None):
        """Initialize the menu matcher with database session."""
        self.db = db
        self.location_id = location_id
        self.menu_items = {}
        self.modifiers = {}
        self.modifier_groups = {}
        
    async def initialize(self) -> bool:
        """Load menu data from database."""
        try:
            # Load menu items
            query = select(MenuItem)
            if self.location_id:
                query = query.filter(MenuItem.location_id == self.location_id)
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            for item in items:
                self.menu_items[item.plu] = {
                    'name': item.name,
                    'description': item.description,
                    'price': item.price,
                    'plu': item.plu,
                    'is_available': item.is_available,
                    'category_id': item.category_id
                }
            
            # Load modifiers
            mod_query = select(MenuModifier)
            mod_result = await self.db.execute(mod_query)
            mods = mod_result.scalars().all()
            
            for mod in mods:
                self.modifiers[mod.plu] = {
                    'name': mod.name,
                    'price_change': mod.price_change,
                    'plu': mod.plu,
                    'is_available': mod.is_available
                }
            
            logger.info(f"Loaded {len(self.menu_items)} items and {len(self.modifiers)} modifiers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize menu matcher: {e}")
            return False
    
    async def find_menu_item(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Find a menu item by name."""
        item_name_lower = item_name.lower()
        
        # Exact match
        for plu, item in self.menu_items.items():
            if item['name'].lower() == item_name_lower:
                return item
        
        # Partial match
        for plu, item in self.menu_items.items():
            if item_name_lower in item['name'].lower():
                return item
        
        return None
    
    async def find_modifier(self, modifier_name: str) -> Optional[Dict[str, Any]]:
        """Find a modifier by name."""
        modifier_name_lower = modifier_name.lower()
        
        # Exact match
        for plu, modifier in self.modifiers.items():
            if modifier['name'].lower() == modifier_name_lower:
                return modifier
        
        # Partial match
        for plu, modifier in self.modifiers.items():
            if modifier_name_lower in modifier['name'].lower():
                return modifier
        
        return None
    
    async def get_item_modifiers(self, item_plu: str) -> List[Dict[str, Any]]:
        """Get available modifiers for an item."""
        # This would normally query ItemModifierGroup relationships
        # For now, return empty list
        return []
    
    async def find_all_matching_items(
        self, 
        query: str, 
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find all menu items matching a query with confidence scores.
        
        Args:
            query: The search query
            threshold: Minimum confidence threshold
            
        Returns:
            List of matching items with confidence scores
        """
        query_lower = query.lower().strip()
        matches = []
        
        for plu, item in self.menu_items.items():
            item_name_lower = item['name'].lower()
            confidence = 0.0
            
            # Exact match
            if item_name_lower == query_lower:
                confidence = 1.0
            # Query is full item name
            elif query_lower in item_name_lower:
                # Calculate confidence based on match position and length
                match_ratio = len(query_lower) / len(item_name_lower)
                position_score = 1.0 if item_name_lower.startswith(query_lower) else 0.8
                confidence = match_ratio * position_score
            # Item name contains all query words
            else:
                query_words = query_lower.split()
                item_words = item_name_lower.split()
                matching_words = sum(1 for qw in query_words if any(qw in iw for iw in item_words))
                if matching_words > 0:
                    confidence = matching_words / len(query_words) * 0.7
            
            if confidence >= threshold:
                match_data = item.copy()
                match_data['confidence'] = confidence
                match_data['id'] = plu
                matches.append(match_data)
        
        # Sort by confidence descending
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        logger.info(
            f"Found {len(matches)} matches for '{query}' with threshold {threshold}"
        )
        
        return matches