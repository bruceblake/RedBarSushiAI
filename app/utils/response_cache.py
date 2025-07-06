"""
Response caching utilities for agents.

This module provides caching for agent responses to improve performance
and reduce redundant processing.
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional
from app.redis_async import get_redis

logger = logging.getLogger(__name__)


class ResponseCache:
    """Cache for agent responses."""
    
    def __init__(self, ttl: int = 1800):  # 30 minutes default
        """
        Initialize response cache.
        
        Args:
            ttl: Time to live for cached responses in seconds
        """
        self.ttl = ttl
        self.prefix = "response_cache:"
    
    def _make_key(self, agent_type: str, context: Dict[str, Any]) -> str:
        """Generate cache key from agent type and context."""
        data = {"agent_type": agent_type, "context": context}
        serialized = json.dumps(data, sort_keys=True)
        key_hash = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return f"{self.prefix}{agent_type}:{key_hash}"
    
    async def get(self, agent_type: str, context: Dict[str, Any]) -> Optional[str]:
        """Get cached response."""
        try:
            redis_client = await get_redis()
            key = self._make_key(agent_type, context)
            cached = await redis_client.get(key)
            return cached.decode() if cached else None
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None
    
    async def set(self, agent_type: str, context: Dict[str, Any], response: str) -> None:
        """Cache response."""
        try:
            redis_client = await get_redis()
            key = self._make_key(agent_type, context)
            await redis_client.setex(key, self.ttl, response)
        except Exception as e:
            logger.error(f"Error caching response: {e}")
    
    async def clear(self, agent_type: Optional[str] = None) -> None:
        """Clear cached responses."""
        try:
            redis_client = await get_redis()
            pattern = f"{self.prefix}{agent_type}:*" if agent_type else f"{self.prefix}*"
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing response cache: {e}")


# Global response cache instance
response_cache = ResponseCache()