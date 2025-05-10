"""
Redis configuration for the FastAPI application.

This module provides async Redis using redis-py with async support.
"""

import logging
import os
from typing import Optional, Any, Dict, Union

import redis.asyncio as aioredis
from fastapi import Depends

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Global redis client instances
_redis_client: Optional[aioredis.Redis] = None
_memory_cache: Dict[str, Any] = {}
_memory_cache_timestamps: Dict[str, float] = {}

# Default cache durations
DEFAULT_REDIS_CACHE_DURATION = 300  # 5 minutes
DEFAULT_MEMORY_CACHE_DURATION = 60  # 1 minute

async def init_redis() -> Optional[aioredis.Redis]:
    """
    Initialize the Redis connection for caching.
    
    Returns:
        Optional[aioredis.Redis]: Redis client or None if not available
    """
    global _redis_client
    
    try:
        # Get Redis URL from environment or config
        redis_url = settings.REDIS_URL or settings.CELERY_BROKER_URL
        
        if not redis_url:
            if os.environ.get("RENDER", "").lower() == "true" or os.environ.get("RENDER_SERVICE_ID"):
                logger.warning("Running in Render environment but no Redis URL provided!")
            
            # Default if nothing is set
            redis_url = "redis://localhost:6379/0"
        
        # For Docker environment
        if os.environ.get("DOCKER") and "localhost" in redis_url:
            redis_url = redis_url.replace("localhost", "redis")
            
        # Ensure the URL has the proper redis:// prefix
        if not redis_url.startswith("redis://"):
            redis_url = f"redis://{redis_url}"
        
        # Create the Redis client with timeout
        logger.info(f"Connecting to Redis at {redis_url}")
        _redis_client = aioredis.Redis.from_url(
            redis_url,
            socket_timeout=2.0,  # Short timeout for basic operations
            socket_connect_timeout=5.0,  # Longer timeout for initial connection
            decode_responses=False  # We'll handle binary data explicitly
        )
        
        # Test the connection
        await _redis_client.ping()
        logger.info("Successfully connected to Redis")
        return _redis_client
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        _redis_client = None
        return None

async def get_redis() -> aioredis.Redis:
    """
    Get the Redis client.
    
    Returns:
        aioredis.Redis: Redis client
        
    Raises:
        Exception: If Redis is not available
    """
    global _redis_client
    
    if _redis_client is None:
        # Try to initialize Redis
        _redis_client = await init_redis()
        
    if _redis_client is None:
        # Still None after initialization attempt
        raise Exception("Redis client not available")
        
    return _redis_client

async def redis_get(key: str) -> Optional[bytes]:
    """
    Get a value from Redis with error handling.
    
    Args:
        key: Redis key
        
    Returns:
        Optional[bytes]: Value from Redis or None if not found/error
    """
    try:
        redis_client = await get_redis()
        return await redis_client.get(key)
    except Exception as e:
        logger.error(f"Error getting value from Redis for key {key}: {e}")
        return None

async def redis_set(key: str, value: Union[str, bytes], expire: int = DEFAULT_REDIS_CACHE_DURATION) -> bool:
    """
    Set a value in Redis with error handling.
    
    Args:
        key: Redis key
        value: Value to store
        expire: Expiration time in seconds (default: 5 minutes)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = await get_redis()
        # Ensure value is bytes
        if isinstance(value, str):
            value = value.encode('utf-8')
        await redis_client.set(key, value, ex=expire)
        return True
    except Exception as e:
        logger.error(f"Error setting value in Redis for key {key}: {e}")
        return False

async def redis_delete(key: str) -> bool:
    """
    Delete a key from Redis with error handling.
    
    Args:
        key: Redis key
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis_client = await get_redis()
        await redis_client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Error deleting key {key} from Redis: {e}")
        return False

# Memory cache operations for fallback when Redis is unavailable
def memory_cache_get(key: str) -> Optional[Any]:
    """
    Get a value from the memory cache.
    
    Args:
        key: Cache key
        
    Returns:
        Optional[Any]: Cached value or None if not found
    """
    import time
    
    if key not in _memory_cache:
        return None
        
    # Check expiration
    timestamp = _memory_cache_timestamps.get(key, 0)
    if time.time() - timestamp > DEFAULT_MEMORY_CACHE_DURATION:
        # Expired, remove from cache
        if key in _memory_cache:
            del _memory_cache[key]
        if key in _memory_cache_timestamps:
            del _memory_cache_timestamps[key]
        return None
        
    return _memory_cache.get(key)

def memory_cache_set(key: str, value: Any) -> bool:
    """
    Store a value in the memory cache.
    
    Args:
        key: Cache key
        value: Value to store
        
    Returns:
        bool: True if successful, False otherwise
    """
    import time
    
    try:
        _memory_cache[key] = value
        _memory_cache_timestamps[key] = time.time()
        
        # Cleanup memory cache if it gets too large
        if len(_memory_cache) > 100:
            # Sort items by timestamp
            items_to_keep = sorted(
                [(k, v) for k, v in _memory_cache_timestamps.items()],
                key=lambda x: x[1],  # Sort by timestamp
                reverse=True,
            )[:50]  # Keep only the 50 most recent
            
            # Create new cache dictionaries
            temp_cache = {}
            temp_timestamps = {}
            
            # Populate the temporary dictionaries
            for k, ts in items_to_keep:
                temp_cache[k] = _memory_cache.get(k)
                temp_timestamps[k] = ts
                
            # Clear and update the existing cache
            _memory_cache.clear()
            _memory_cache_timestamps.clear()
            _memory_cache.update(temp_cache)
            _memory_cache_timestamps.update(temp_timestamps)
            
            logger.info(f"Memory cache cleaned up, now storing {len(_memory_cache)} items")
            
        return True
    except Exception as e:
        logger.error(f"Error storing in memory cache: {e}")
        return False