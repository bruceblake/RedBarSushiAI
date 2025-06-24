"""
Centralized caching service with multi-tier caching strategy.

This module provides a unified caching interface with:
- L1: In-memory cache (fastest, limited size)
- L2: Redis cache (fast, distributed)
- Smart cache warming and invalidation
- TTL management and cache statistics
"""

import json
import asyncio
import time
from typing import Any, Optional, Dict, List, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import hashlib

from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.redis_async import get_redis, redis_set, redis_get, redis_delete

logger = get_logger(__name__)


class CacheTier:
    """Enumeration of cache tiers."""
    MEMORY = "memory"
    REDIS = "redis"


class CacheStats:
    """Track cache performance statistics."""
    
    def __init__(self):
        self.hits = {"memory": 0, "redis": 0}
        self.misses = 0
        self.sets = 0
        self.evictions = 0
        self.errors = 0
        self.start_time = time.time()
    
    def record_hit(self, tier: str):
        """Record a cache hit."""
        self.hits[tier] = self.hits.get(tier, 0) + 1
    
    def record_miss(self):
        """Record a cache miss."""
        self.misses += 1
    
    def record_set(self):
        """Record a cache set operation."""
        self.sets += 1
    
    def record_eviction(self):
        """Record a cache eviction."""
        self.evictions += 1
    
    def record_error(self):
        """Record a cache error."""
        self.errors += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = sum(self.hits.values()) + self.misses
        hit_rate = sum(self.hits.values()) / total_requests if total_requests > 0 else 0
        uptime = time.time() - self.start_time
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate * 100, 2),
            "sets": self.sets,
            "evictions": self.evictions,
            "errors": self.errors,
            "uptime_seconds": round(uptime, 2)
        }


class MemoryCache:
    """In-memory LRU cache implementation."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize memory cache.
        
        Args:
            max_size: Maximum number of items to store
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._expiry_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache."""
        async with self._lock:
            if key not in self._cache:
                return None
            
            # Check expiry
            if time.time() > self._expiry_times.get(key, float('inf')):
                del self._cache[key]
                del self._access_times[key]
                del self._expiry_times[key]
                return None
            
            # Update access time
            self._access_times[key] = time.time()
            return self._cache[key]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in memory cache."""
        async with self._lock:
            # Use provided TTL or default
            ttl = ttl or self.default_ttl
            
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_lru()
            
            self._cache[key] = value
            self._access_times[key] = time.time()
            self._expiry_times[key] = time.time() + ttl
    
    async def delete(self, key: str) -> bool:
        """Delete key from memory cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._access_times[key]
                del self._expiry_times[key]
                return True
            return False
    
    async def clear(self):
        """Clear all items from memory cache."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._expiry_times.clear()
    
    async def _evict_lru(self):
        """Evict least recently used item."""
        if not self._access_times:
            return
        
        # Find LRU key
        lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        
        # Remove it
        del self._cache[lru_key]
        del self._access_times[lru_key]
        del self._expiry_times[lru_key]


class CacheService:
    """Centralized caching service with multi-tier support."""
    
    def __init__(self):
        """Initialize cache service."""
        # Memory cache configuration
        self.memory_cache = MemoryCache(
            max_size=getattr(settings, 'CACHE_MEMORY_MAX_SIZE', 1000),
            default_ttl=getattr(settings, 'CACHE_MEMORY_DEFAULT_TTL', 300)
        )
        
        # Cache statistics
        self.stats = CacheStats()
        
        # Default TTLs for different cache types
        self.default_ttls = {
            "menu": 3600,  # 1 hour for menu data
            "ai_response": 300,  # 5 minutes for AI responses
            "session": 1800,  # 30 minutes for session data
            "computation": 600,  # 10 minutes for computed results
        }
    
    def _generate_key(self, namespace: str, key: str) -> str:
        """Generate namespaced cache key."""
        return f"{namespace}:{key}"
    
    async def get(
        self, 
        key: str, 
        namespace: str = "default",
        check_memory: bool = True,
        check_redis: bool = True
    ) -> Optional[Any]:
        """
        Get value from cache, checking multiple tiers.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            check_memory: Whether to check memory cache
            check_redis: Whether to check Redis cache
            
        Returns:
            Cached value or None
        """
        full_key = self._generate_key(namespace, key)
        
        # Check L1 (memory) cache
        if check_memory:
            value = await self.memory_cache.get(full_key)
            if value is not None:
                self.stats.record_hit(CacheTier.MEMORY)
                logger.debug(f"Cache hit (memory): {full_key}")
                return value
        
        # Check L2 (Redis) cache
        if check_redis:
            try:
                redis_value = await redis_get(full_key)
                if redis_value:
                    # Deserialize from Redis
                    value = json.loads(redis_value.decode('utf-8'))
                    self.stats.record_hit(CacheTier.REDIS)
                    logger.debug(f"Cache hit (Redis): {full_key}")
                    
                    # Promote to memory cache
                    if check_memory:
                        await self.memory_cache.set(full_key, value)
                    
                    return value
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
                self.stats.record_error()
        
        # Cache miss
        self.stats.record_miss()
        logger.debug(f"Cache miss: {full_key}")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[int] = None,
        set_memory: bool = True,
        set_redis: bool = True
    ) -> bool:
        """
        Set value in cache across multiple tiers.
        
        Args:
            key: Cache key
            value: Value to cache
            namespace: Cache namespace
            ttl: Time to live in seconds
            set_memory: Whether to set in memory cache
            set_redis: Whether to set in Redis cache
            
        Returns:
            Success status
        """
        full_key = self._generate_key(namespace, key)
        
        # Determine TTL
        if ttl is None:
            ttl = self.default_ttls.get(namespace, 300)
        
        success = True
        
        # Set in L1 (memory) cache
        if set_memory:
            try:
                await self.memory_cache.set(full_key, value, ttl)
                logger.debug(f"Cache set (memory): {full_key}, TTL: {ttl}s")
            except Exception as e:
                logger.error(f"Memory cache set error: {e}")
                success = False
        
        # Set in L2 (Redis) cache
        if set_redis:
            try:
                # Serialize for Redis
                redis_value = json.dumps(value)
                await redis_set(full_key, redis_value, expire=ttl)
                logger.debug(f"Cache set (Redis): {full_key}, TTL: {ttl}s")
            except Exception as e:
                logger.error(f"Redis cache set error: {e}")
                success = False
        
        if success:
            self.stats.record_set()
        else:
            self.stats.record_error()
        
        return success
    
    async def delete(
        self,
        key: str,
        namespace: str = "default",
        delete_memory: bool = True,
        delete_redis: bool = True
    ) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            delete_memory: Whether to delete from memory cache
            delete_redis: Whether to delete from Redis cache
            
        Returns:
            Success status
        """
        full_key = self._generate_key(namespace, key)
        success = True
        
        # Delete from memory cache
        if delete_memory:
            await self.memory_cache.delete(full_key)
        
        # Delete from Redis cache
        if delete_redis:
            success = await redis_delete(full_key)
        
        logger.debug(f"Cache delete: {full_key}")
        return success
    
    async def clear_namespace(self, namespace: str) -> bool:
        """
        Clear all cache entries in a namespace.
        
        Args:
            namespace: Cache namespace to clear
            
        Returns:
            Success status
        """
        try:
            # Clear from Redis (pattern-based)
            redis_client = await get_redis()
            pattern = f"{namespace}:*"
            
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries for namespace: {namespace}")
            
            # Clear from memory cache
            # Note: This is less efficient as we need to check all keys
            keys_to_delete = [
                k for k in self.memory_cache._cache.keys() 
                if k.startswith(f"{namespace}:")
            ]
            
            for key in keys_to_delete:
                await self.memory_cache.delete(key)
            
            logger.info(f"Cleared {len(keys_to_delete)} memory cache entries for namespace: {namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing namespace {namespace}: {e}")
            return False
    
    def cached(
        self,
        namespace: str = "default",
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
    ):
        """
        Decorator for caching function results.
        
        Args:
            namespace: Cache namespace
            ttl: Time to live in seconds
            key_func: Function to generate cache key from arguments
            
        Usage:
            @cache_service.cached(namespace="menu", ttl=3600)
            async def get_menu_items():
                # Expensive operation
                return items
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    if args:
                        key_parts.extend(str(arg) for arg in args)
                    if kwargs:
                        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    
                    # Hash for consistent key length
                    key_str = ":".join(key_parts)
                    cache_key = hashlib.md5(key_str.encode()).hexdigest()
                
                # Check cache
                cached_value = await self.get(cache_key, namespace=namespace)
                if cached_value is not None:
                    return cached_value
                
                # Call function
                result = await func(*args, **kwargs)
                
                # Cache result
                await self.set(cache_key, result, namespace=namespace, ttl=ttl)
                
                return result
            
            return wrapper
        return decorator
    
    async def warm_cache(self, warming_funcs: List[Callable]):
        """
        Warm cache by calling specified functions.
        
        Args:
            warming_funcs: List of async functions to call for cache warming
        """
        logger.info("Starting cache warming...")
        
        tasks = []
        for func in warming_funcs:
            tasks.append(func())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = len(results) - success_count
        
        logger.info(
            f"Cache warming completed. Success: {success_count}, Errors: {error_count}"
        )
        
        return success_count, error_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.stats.get_stats()
        
        # Add memory cache info
        stats["memory_cache"] = {
            "size": len(self.memory_cache._cache),
            "max_size": self.memory_cache.max_size,
            "utilization": round(
                len(self.memory_cache._cache) / self.memory_cache.max_size * 100, 2
            )
        }
        
        return stats


# Global cache service instance
cache_service = CacheService()


# Convenience functions
async def cache_get(key: str, namespace: str = "default") -> Optional[Any]:
    """Get value from cache."""
    return await cache_service.get(key, namespace)


async def cache_set(
    key: str, 
    value: Any, 
    namespace: str = "default", 
    ttl: Optional[int] = None
) -> bool:
    """Set value in cache."""
    return await cache_service.set(key, value, namespace, ttl)


async def cache_delete(key: str, namespace: str = "default") -> bool:
    """Delete value from cache."""
    return await cache_service.delete(key, namespace)


# Cache warming functions for menu data
async def warm_menu_cache():
    """Warm menu cache with frequently accessed data."""
    try:
        from app.db.crud_menu_async import (
            get_all_menu_items,
            get_categories_with_items
        )
        from app.dependencies import get_db
        
        # Get database session
        async for db in get_db():
            # Cache all menu items
            items = await get_all_menu_items(db)
            await cache_service.set("all_items", items, namespace="menu", ttl=3600)
            
            # Cache categories with items
            categories = await get_categories_with_items(db)
            await cache_service.set("categories", categories, namespace="menu", ttl=3600)
            
            logger.info(f"Warmed menu cache with {len(items)} items and {len(categories)} categories")
            break
            
    except Exception as e:
        logger.error(f"Error warming menu cache: {e}")
        raise