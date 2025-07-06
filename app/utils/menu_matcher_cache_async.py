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
from app.redis_async import cache_menu_data, get_cached_menu_data, clear_menu_cache

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
        self.menu_data = None  # Initialize menu_data attribute
        
    async def initialize(self) -> bool:
        """
        Load menu data from cache or database.
        
        Returns:
            True if initialization successful, False otherwise
        """
        # Try to get from cache first
        cached_data = await get_cached_menu_data()
        
        if cached_data:
            try:
                # cached_data is already a dict from get_cached_menu_data()
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
            
            if success:
                # Load the menu data for caching
                from app.utils.menu_utils_db_async import load_menu_data
                self.menu_data = await load_menu_data(self.db, location_id=self.location_id)
                
                if self.menu_data:
                    # Store in cache for next time
                    try:
                        await cache_menu_data(self.menu_data, ttl=self.cache_ttl)
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
        # Use the base class's find_menu_item method
        item = await self.find_menu_item(description)
        
        if item:
            # Calculate a simple confidence score based on how well the description matches
            item_name_lower = item['name'].lower()
            description_lower = description.lower()
            
            if item_name_lower == description_lower:
                score = 1.0  # Exact match
            elif description_lower in item_name_lower:
                score = 0.8  # Description is contained in item name
            elif all(word in item_name_lower for word in description_lower.split()):
                score = 0.7  # All words from description are in item name
            else:
                score = 0.5  # Partial match
                
            return item, score
        
        return None, 0.0

# Module-level cache management functions
async def clear_cached_menu_matcher():
    """Clear the cached menu matcher instance and menu data cache."""
    global cached_async_menu_matcher
    
    try:
        # Clear the singleton instance
        if cached_async_menu_matcher:
            logger.info("Clearing cached menu matcher singleton")
            cached_async_menu_matcher = None
        
        # Clear the Redis cache
        await clear_menu_cache()
        
        # Clear memory cache
        menu_cache.clear_all()
        
        logger.info("Cleared all menu caches successfully")
    except Exception as e:
        logger.error(f"Error clearing menu matcher cache: {e}")

# Create a singleton instance for easy import
cached_async_menu_matcher = None

async def get_cached_async_menu_matcher(db: AsyncSession, location_id: Optional[str] = None, force_refresh: bool = False) -> AsyncCachedMenuMatcher:
    """
    Get or create the cached menu matcher singleton.
    
    Args:
        db: AsyncSession for database access
        location_id: Optional location ID to filter menu items
        force_refresh: Force creation of a new matcher instance
        
    Returns:
        AsyncCachedMenuMatcher instance
    """
    global cached_async_menu_matcher
    
    # Force refresh or create new if db is provided
    if force_refresh or db is not None:
        logger.info(f"Creating new menu matcher with database session (force_refresh={force_refresh})")
        cached_async_menu_matcher = AsyncCachedMenuMatcher(db, location_id)
        success = await cached_async_menu_matcher.initialize()
        if not success:
            logger.error("Failed to initialize menu matcher")
    elif cached_async_menu_matcher is None:
        logger.error("No database session provided and no cached matcher available")
        raise ValueError("Database session required to initialize menu matcher")
        
    return cached_async_menu_matcher




# Alias for backward compatibility
AsyncMenuMatcher = AsyncCachedMenuMatcher
