"""
Enhanced menu caching utilities using the centralized cache service.

This module provides optimized caching for menu data with:
- Multi-tier caching (memory + Redis)
- Smart cache invalidation
- Batch operations for efficiency
- Cache warming strategies
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.services.cache_service import cache_service
from app.utils.enhanced_logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class MenuCacheManager:
    """Manages menu data caching with optimization strategies."""
    
    def __init__(self):
        """Initialize menu cache manager."""
        self.namespace = "menu"
        self.ttl = 3600  # 1 hour default TTL
    
    async def get_all_items(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Get all menu items with caching.
        
        Args:
            db: Database session
            
        Returns:
            List of menu items
        """
        # Check cache first
        cached_items = await cache_service.get("all_items", namespace=self.namespace)
        if cached_items is not None:
            logger.debug(f"Retrieved {len(cached_items)} items from cache")
            return cached_items
        
        # Load from database
        from app.db.crud_menu_async import get_all_menu_items
        items = await get_all_menu_items(db)
        
        # Process items for caching
        processed_items = []
        for item in items:
            item_dict = {
                "id": item.id,
                "plu": item.plu,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else 0.0,
                "category": item.category,
                "subcategory": item.subcategory,
                "available": item.available,
                "position": item.position,
                "modifiers": json.loads(item.modifiers) if item.modifiers else []
            }
            processed_items.append(item_dict)
        
        # Cache the results
        await cache_service.set(
            "all_items", 
            processed_items, 
            namespace=self.namespace,
            ttl=self.ttl
        )
        
        # Also cache individual items by PLU for quick lookup
        for item in processed_items:
            await cache_service.set(
                f"item_plu:{item['plu']}", 
                item,
                namespace=self.namespace,
                ttl=self.ttl
            )
        
        logger.info(f"Cached {len(processed_items)} menu items")
        return processed_items
    
    async def get_item_by_plu(self, plu: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Get menu item by PLU with caching.
        
        Args:
            plu: Item PLU code
            db: Database session
            
        Returns:
            Menu item or None
        """
        # Check cache first
        cached_item = await cache_service.get(f"item_plu:{plu}", namespace=self.namespace)
        if cached_item is not None:
            logger.debug(f"Retrieved item {plu} from cache")
            return cached_item
        
        # Load from database
        from app.db.crud_menu_async import get_item_by_plu
        item = await get_item_by_plu(db, plu)
        
        if item:
            item_dict = {
                "id": item.id,
                "plu": item.plu,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else 0.0,
                "category": item.category,
                "subcategory": item.subcategory,
                "available": item.available,
                "position": item.position,
                "modifiers": json.loads(item.modifiers) if item.modifiers else []
            }
            
            # Cache the item
            await cache_service.set(
                f"item_plu:{plu}",
                item_dict,
                namespace=self.namespace,
                ttl=self.ttl
            )
            
            return item_dict
        
        return None
    
    async def get_categories_with_items(self, db: AsyncSession) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get categories with their items, using cache.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary of categories with items
        """
        # Check cache first
        cached_categories = await cache_service.get("categories_with_items", namespace=self.namespace)
        if cached_categories is not None:
            logger.debug("Retrieved categories from cache")
            return cached_categories
        
        # Load from database
        from app.db.crud_menu_async import get_categories_with_items
        categories = await get_categories_with_items(db)
        
        # Process for caching
        processed_categories = {}
        for category, items in categories.items():
            processed_items = []
            for item in items:
                item_dict = {
                    "id": item.id,
                    "plu": item.plu,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.price) if item.price else 0.0,
                    "available": item.available,
                    "position": item.position
                }
                processed_items.append(item_dict)
            processed_categories[category] = processed_items
        
        # Cache the results
        await cache_service.set(
            "categories_with_items",
            processed_categories,
            namespace=self.namespace,
            ttl=self.ttl
        )
        
        logger.info(f"Cached {len(processed_categories)} categories")
        return processed_categories
    
    async def search_items(
        self, 
        query: str, 
        db: AsyncSession,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search menu items with caching of results.
        
        Args:
            query: Search query
            db: Database session
            category: Optional category filter
            
        Returns:
            List of matching items
        """
        # Generate cache key
        cache_key = f"search:{query.lower()}"
        if category:
            cache_key += f":cat:{category.lower()}"
        
        # Check cache
        cached_results = await cache_service.get(cache_key, namespace=self.namespace)
        if cached_results is not None:
            logger.debug(f"Retrieved search results from cache: {query}")
            return cached_results
        
        # Search database
        from app.db.crud_menu_async import search_menu_items
        items = await search_menu_items(db, query, category)
        
        # Process results
        results = []
        for item in items:
            item_dict = {
                "id": item.id,
                "plu": item.plu,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else 0.0,
                "category": item.category,
                "available": item.available,
                "score": getattr(item, 'search_score', 1.0)  # Include relevance score if available
            }
            results.append(item_dict)
        
        # Cache search results (shorter TTL for searches)
        await cache_service.set(
            cache_key,
            results,
            namespace=self.namespace,
            ttl=300  # 5 minutes for search results
        )
        
        return results
    
    async def get_menu_variants(self, plu: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Get menu item variants with caching.
        
        Args:
            plu: Item PLU code
            db: Database session
            
        Returns:
            List of variants
        """
        cache_key = f"variants:{plu}"
        
        # Check cache
        cached_variants = await cache_service.get(cache_key, namespace=self.namespace)
        if cached_variants is not None:
            return cached_variants
        
        # Load from database
        from app.db.crud_menu_async import get_item_variants
        variants = await get_item_variants(db, plu)
        
        # Process variants
        processed_variants = []
        for variant in variants:
            variant_dict = {
                "id": variant.id,
                "variant_name": variant.variant_name,
                "confidence_score": float(variant.confidence_score) if variant.confidence_score else 0.9
            }
            processed_variants.append(variant_dict)
        
        # Cache variants
        await cache_service.set(
            cache_key,
            processed_variants,
            namespace=self.namespace,
            ttl=self.ttl
        )
        
        return processed_variants
    
    async def invalidate_cache(self, specific_key: Optional[str] = None):
        """
        Invalidate menu cache.
        
        Args:
            specific_key: Specific cache key to invalidate, or None for all
        """
        if specific_key:
            await cache_service.delete(specific_key, namespace=self.namespace)
            logger.info(f"Invalidated cache key: {specific_key}")
        else:
            # Clear entire menu namespace
            await cache_service.clear_namespace(self.namespace)
            logger.info("Invalidated all menu cache")
    
    async def warm_cache(self, db: AsyncSession):
        """
        Warm menu cache by pre-loading frequently accessed data.
        
        Args:
            db: Database session
        """
        logger.info("Starting menu cache warming...")
        
        try:
            # Load all items
            items = await self.get_all_items(db)
            logger.info(f"Warmed cache with {len(items)} items")
            
            # Load categories
            categories = await self.get_categories_with_items(db)
            logger.info(f"Warmed cache with {len(categories)} categories")
            
            # Pre-cache popular searches
            popular_searches = ["roll", "sushi", "sashimi", "appetizer", "drink"]
            for search_term in popular_searches:
                results = await self.search_items(search_term, db)
                logger.debug(f"Pre-cached search: {search_term} ({len(results)} results)")
            
            logger.info("Menu cache warming completed successfully")
            
        except Exception as e:
            logger.error(f"Error warming menu cache: {e}")
            raise
    
    @cache_service.cached(namespace="menu", ttl=1800)
    async def get_item_with_modifiers(self, plu: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get menu item with full modifier information.
        
        This method is decorated to automatically cache results.
        
        Args:
            plu: Item PLU code
            db: Database session
            
        Returns:
            Item with modifier details
        """
        item = await self.get_item_by_plu(plu, db)
        if not item:
            return None
        
        # Load modifier details if any
        if item.get("modifiers"):
            from app.db.crud_menu_async import get_modifiers_by_ids
            modifier_ids = [m["id"] for m in item["modifiers"] if "id" in m]
            if modifier_ids:
                modifiers = await get_modifiers_by_ids(db, modifier_ids)
                item["modifier_details"] = [
                    {
                        "id": mod.id,
                        "name": mod.name,
                        "price_change": float(mod.price_change) if mod.price_change else 0.0,
                        "group_id": mod.modifier_group_id
                    }
                    for mod in modifiers
                ]
        
        return item


# Global menu cache manager
menu_cache = MenuCacheManager()


# Convenience functions
async def get_cached_menu_items(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all menu items with caching."""
    return await menu_cache.get_all_items(db)


async def get_cached_item_by_plu(plu: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """Get menu item by PLU with caching."""
    return await menu_cache.get_item_by_plu(plu, db)


async def search_cached_menu_items(
    query: str, 
    db: AsyncSession, 
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search menu items with caching."""
    return await menu_cache.search_items(query, db, category)


async def invalidate_menu_cache(specific_key: Optional[str] = None):
    """Invalidate menu cache."""
    await menu_cache.invalidate_cache(specific_key)


async def warm_menu_cache(db: AsyncSession):
    """Warm menu cache."""
    await menu_cache.warm_cache(db)