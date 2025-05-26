"""
Enhanced menu matching with Redis caching for RedBarSushiAI - async version.
This module enhances menu_matcher_db_async.py with Redis caching for faster lookups.
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.menu_matcher_db_async import AsyncMenuMatcher as BaseAsyncMenuMatcher
# Ensure we're not importing from the old menu_matcher_db module:
# Avoid: from app.utils.menu_matcher_db import MenuMatcher
from app.utils.menu_cache_sdk import menu_cache, with_menu_cache

logger = logging.getLogger(__name__)

class AsyncCachedMenuMatcher(BaseAsyncMenuMatcher):
    """
    Enhanced AsyncMenuMatcher with Redis caching for faster lookups.
    This class wraps the original AsyncMenuMatcher, adding caching for performance.
    """
    
    def __init__(self, db: AsyncSession, location_id: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize the cached menu matcher.
        
        Args:
            db: AsyncSession for database access
            location_id: Optional location ID to filter menu items
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        super().__init__(db, location_id)
        self.cache_ttl = cache_ttl
        self.cache_key_prefix = f"menu:async:{location_id or 'default'}:"
        
    async def initialize(self) -> bool:
        """
        Load menu data from cache or database.
        
        Returns:
            True if initialization successful, False otherwise
        """
        # Try to get from cache first
        cached_data = menu_cache.get_all_menu()
        
        if cached_data:
            try:
                # cached_data is already a dict from get_all_menu()
                self.menu_data = cached_data
                self.items = cached_data.get("items", [])
                self.modifiers = cached_data.get("modifiers", [])
                self.modifier_groups = cached_data.get("modifier_groups", [])
                self.variants = cached_data.get("variants", [])
                logger.info(f"AsyncCachedMenuMatcher loaded from cache with {len(self.items)} items")
                return True
            except Exception as e:
                logger.error(f"Error loading menu data from cache: {e}")
                # Fall through to database loading
        
        # Load from database
        try:
            # Call parent implementation to load from DB
            success = await super().initialize()
            
            if success and self.menu_data:
                # Store in cache for next time
                try:
                    menu_cache.set_all_menu(self.menu_data, ttl=self.cache_ttl)
                    logger.info(f"Stored menu data in cache")
                except Exception as e:
                    logger.error(f"Error storing menu data in cache: {e}")
            
            return success
        except Exception as e:
            logger.error(f"Error in cached menu initialization: {e}")
            return False
            
    async def match_item(self, description: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Match a natural language description to a menu item with caching.
        
        Args:
            description: Natural language description of the item
            
        Returns:
            Tuple of (best matching item or None, confidence score)
        """
        # Skip individual match caching for now since menu_cache doesn't have a generic get method
        # TODO: Implement proper caching using redis client directly
        
        # No cache hit, use normal matching
        item, score = await super().match_item(description)
        
        # Skip caching individual results for now
        # TODO: Implement proper caching using redis client directly
        
        return item, score

# Create a singleton instance for easy import
cached_async_menu_matcher = None

async def get_cached_async_menu_matcher(db: AsyncSession, location_id: Optional[str] = None) -> AsyncCachedMenuMatcher:
    """
    Get or create the cached menu matcher singleton.
    
    Args:
        db: AsyncSession for database access
        location_id: Optional location ID to filter menu items
        
    Returns:
        AsyncCachedMenuMatcher instance
    """
    global cached_async_menu_matcher
    
    if cached_async_menu_matcher is None:
        cached_async_menu_matcher = AsyncCachedMenuMatcher(db, location_id)
        await cached_async_menu_matcher.initialize()
        
    return cached_async_menu_matcher