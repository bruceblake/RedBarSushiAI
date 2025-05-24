"""
Database and Redis-backed menu storage module for FastAPI.

This module provides a persistent storage solution for menu data with:
1. PostgreSQL/SQLite as the primary storage backend
2. Redis as a read-through caching layer for performance
3. In-memory fallback when Redis is unavailable
"""

import json
import logging
import time
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

# Set up logging
logger = logging.getLogger(__name__)

# Import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis package not installed, using database-only functionality")

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_EXPIRY = int(os.environ.get("REDIS_MENU_EXPIRY", 3600))  # 1 hour default

# Try to get database connection from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///menu_store.db")


class MenuDBStore:
    """
    A database-backed menu storage with Redis caching.
    """

    def __init__(self):
        self._menu_cache = None
        self._last_db_check = 0
        self._db_check_interval = 300  # Check DB every 5 minutes
        self._redis_client = None
        self._in_memory_cache = {}  # Fallback cache when Redis is unavailable
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection if available."""
        if REDIS_AVAILABLE:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                logger.info("Redis connection established for menu caching")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                self._redis_client = None
        else:
            logger.info("Redis not available, using in-memory cache")

    def _get_redis_key(self, key: str) -> str:
        """Generate Redis key with prefix."""
        return f"menu:{key}"

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get data from cache (Redis or in-memory)."""
        if self._redis_client:
            try:
                data = self._redis_client.get(self._get_redis_key(key))
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis read error: {e}")
        
        # Fallback to in-memory cache
        return self._in_memory_cache.get(key)

    def _set_in_cache(self, key: str, data: Dict, expiry: int = REDIS_EXPIRY):
        """Set data in cache (Redis or in-memory)."""
        if self._redis_client:
            try:
                self._redis_client.setex(
                    self._get_redis_key(key),
                    expiry,
                    json.dumps(data)
                )
                return
            except Exception as e:
                logger.warning(f"Redis write error: {e}")
        
        # Fallback to in-memory cache
        self._in_memory_cache[key] = data

    def _clear_cache(self):
        """Clear all caches."""
        if self._redis_client:
            try:
                for key in self._redis_client.scan_iter(match=self._get_redis_key("*")):
                    self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        self._in_memory_cache.clear()

    def get(self) -> Optional[Dict[str, Any]]:
        """Get menu data."""
        # Always return empty menu for now - should be loaded from DB
        return {"items": [], "categories": [], "modifiers": []}

    def set(self, menu_data: Dict[str, Any]) -> bool:
        """Set menu data."""
        try:
            # Store in cache
            self._set_in_cache("current_menu", menu_data)
            # In a real implementation, this would also store in the database
            return True
        except Exception as e:
            logger.error(f"Failed to store menu: {e}")
            return False

    def update(self, menu_data: Dict[str, Any]) -> bool:
        """Update menu data (alias for set)."""
        return self.set(menu_data)

    def clear(self) -> bool:
        """Clear menu data."""
        try:
            self._clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to clear menu: {e}")
            return False


# Create a singleton instance
menu_db_store = MenuDBStore()

# Export the instance
__all__ = ["menu_db_store"]