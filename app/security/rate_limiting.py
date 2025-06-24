"""
Rate limiting for RedBarSushiAI.

This module provides comprehensive rate limiting for API endpoints,
WebSocket connections, and resource usage to prevent abuse and ensure
system stability.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from app.config import settings
from app.redis_async import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Types of rate limiting."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int
    window_seconds: int
    burst_size: Optional[int] = None
    limit_type: RateLimitType = RateLimitType.SLIDING_WINDOW
    key_prefix: str = "rate_limit"
    error_message: str = "Rate limit exceeded"


class RateLimiter:
    """Base rate limiter class."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter."""
        self.config = config
        
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        raise NotImplementedError
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """In-memory rate limiter for single instance."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize in-memory rate limiter."""
        super().__init__(config)
        self.requests: Dict[str, list] = defaultdict(list)
        self.tokens: Dict[str, float] = defaultdict(lambda: float(config.max_requests))
        self.last_update: Dict[str, float] = defaultdict(time.time)
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        if self.config.limit_type == RateLimitType.SLIDING_WINDOW:
            return await self._sliding_window_check(key)
        elif self.config.limit_type == RateLimitType.TOKEN_BUCKET:
            return await self._token_bucket_check(key)
        else:
            return await self._fixed_window_check(key)
    
    async def _sliding_window_check(self, key: str) -> bool:
        """Sliding window rate limit check."""
        current_time = time.time()
        window_start = current_time - self.config.window_seconds
        
        # Remove old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]
        
        # Check limit
        if len(self.requests[key]) < self.config.max_requests:
            self.requests[key].append(current_time)
            return True
        
        return False
    
    async def _token_bucket_check(self, key: str) -> bool:
        """Token bucket rate limit check."""
        current_time = time.time()
        
        # Refill tokens
        time_passed = current_time - self.last_update[key]
        tokens_to_add = time_passed * (self.config.max_requests / self.config.window_seconds)
        
        self.tokens[key] = min(
            self.config.max_requests,
            self.tokens[key] + tokens_to_add
        )
        self.last_update[key] = current_time
        
        # Check if token available
        if self.tokens[key] >= 1:
            self.tokens[key] -= 1
            return True
        
        return False
    
    async def _fixed_window_check(self, key: str) -> bool:
        """Fixed window rate limit check."""
        current_time = time.time()
        window_key = int(current_time // self.config.window_seconds)
        full_key = f"{key}:{window_key}"
        
        if full_key not in self.requests:
            self.requests[full_key] = []
        
        if len(self.requests[full_key]) < self.config.max_requests:
            self.requests[full_key].append(current_time)
            return True
        
        return False
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        self.requests[key] = []
        self.tokens[key] = float(self.config.max_requests)
        self.last_update[key] = time.time()


class RedisRateLimiter(RateLimiter):
    """Redis-based rate limiter for distributed systems."""
    
    def __init__(self, config: RateLimitConfig, redis_client: Optional[redis.Redis] = None):
        """Initialize Redis rate limiter."""
        super().__init__(config)
        self.redis_client = redis_client
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis_client:
            return self.redis_client
        return await get_redis_client()
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        if self.config.limit_type == RateLimitType.SLIDING_WINDOW:
            return await self._sliding_window_check(key)
        elif self.config.limit_type == RateLimitType.TOKEN_BUCKET:
            return await self._token_bucket_check(key)
        else:
            return await self._fixed_window_check(key)
    
    async def _sliding_window_check(self, key: str) -> bool:
        """Sliding window rate limit check using Redis."""
        redis_client = await self._get_redis()
        full_key = f"{self.config.key_prefix}:{key}"
        current_time = time.time()
        window_start = current_time - self.config.window_seconds
        
        # Use Redis sorted set for sliding window
        pipe = redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(full_key, 0, window_start)
        
        # Count current entries
        pipe.zcard(full_key)
        
        # Add new entry if under limit
        pipe.zadd(full_key, {str(current_time): current_time})
        
        # Set expiry
        pipe.expire(full_key, self.config.window_seconds + 60)
        
        results = await pipe.execute()
        current_count = results[1]
        
        return current_count < self.config.max_requests
    
    async def _token_bucket_check(self, key: str) -> bool:
        """Token bucket rate limit check using Redis."""
        redis_client = await self._get_redis()
        
        # Lua script for atomic token bucket
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or current_time
        
        -- Refill tokens
        local time_passed = current_time - last_refill
        local tokens_to_add = time_passed * refill_rate
        tokens = math.min(max_tokens, tokens + tokens_to_add)
        
        -- Check if token available
        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', current_time)
            redis.call('EXPIRE', key, ARGV[4])
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', current_time)
            redis.call('EXPIRE', key, ARGV[4])
            return 0
        end
        """
        
        full_key = f"{self.config.key_prefix}:bucket:{key}"
        refill_rate = self.config.max_requests / self.config.window_seconds
        
        result = await redis_client.eval(
            lua_script,
            1,
            full_key,
            self.config.max_requests,
            refill_rate,
            time.time(),
            self.config.window_seconds + 60
        )
        
        return bool(result)
    
    async def _fixed_window_check(self, key: str) -> bool:
        """Fixed window rate limit check using Redis."""
        redis_client = await self._get_redis()
        current_time = time.time()
        window_key = int(current_time // self.config.window_seconds)
        full_key = f"{self.config.key_prefix}:fixed:{key}:{window_key}"
        
        # Increment counter
        count = await redis_client.incr(full_key)
        
        # Set expiry on first request
        if count == 1:
            await redis_client.expire(full_key, self.config.window_seconds + 60)
        
        return count <= self.config.max_requests
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        redis_client = await self._get_redis()
        
        # Delete all keys for this identifier
        pattern = f"{self.config.key_prefix}*{key}*"
        cursor = 0
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                await redis_client.delete(*keys)
            if cursor == 0:
                break


# Rate limiting configurations for different resources

RATE_LIMIT_CONFIGS = {
    # API endpoints
    "api_general": RateLimitConfig(
        max_requests=60,
        window_seconds=60,
        limit_type=RateLimitType.SLIDING_WINDOW,
        error_message="API rate limit exceeded. Please try again later."
    ),
    
    # Voice/WebSocket connections
    "websocket_connect": RateLimitConfig(
        max_requests=10,
        window_seconds=60,
        limit_type=RateLimitType.FIXED_WINDOW,
        error_message="Too many connection attempts. Please try again later."
    ),
    
    # LLM requests
    "llm_requests": RateLimitConfig(
        max_requests=30,
        window_seconds=60,
        burst_size=5,
        limit_type=RateLimitType.TOKEN_BUCKET,
        error_message="Too many AI requests. Please slow down."
    ),
    
    # Order placement
    "order_placement": RateLimitConfig(
        max_requests=5,
        window_seconds=300,  # 5 minutes
        limit_type=RateLimitType.FIXED_WINDOW,
        error_message="Too many orders. Please wait before placing another order."
    ),
    
    # SMS sending
    "sms_send": RateLimitConfig(
        max_requests=10,
        window_seconds=3600,  # 1 hour
        limit_type=RateLimitType.FIXED_WINDOW,
        error_message="SMS rate limit exceeded."
    ),
    
    # Menu queries
    "menu_query": RateLimitConfig(
        max_requests=100,
        window_seconds=60,
        limit_type=RateLimitType.SLIDING_WINDOW,
        error_message="Too many menu queries."
    )
}


class RateLimitManager:
    """Manages multiple rate limiters."""
    
    def __init__(self, use_redis: bool = True):
        """Initialize rate limit manager."""
        self.use_redis = use_redis and hasattr(settings, 'REDIS_URL')
        self.limiters: Dict[str, RateLimiter] = {}
        
        # Initialize limiters
        for name, config in RATE_LIMIT_CONFIGS.items():
            if self.use_redis:
                self.limiters[name] = RedisRateLimiter(config)
            else:
                self.limiters[name] = InMemoryRateLimiter(config)
    
    async def check_rate_limit(
        self,
        limit_name: str,
        identifier: str
    ) -> bool:
        """
        Check rate limit for identifier.
        
        Args:
            limit_name: Name of the rate limit config
            identifier: Unique identifier (e.g., IP, user ID)
            
        Returns:
            True if allowed, False if rate limited
        """
        if limit_name not in self.limiters:
            logger.warning(f"Unknown rate limit: {limit_name}")
            return True
        
        return await self.limiters[limit_name].is_allowed(identifier)
    
    async def reset_rate_limit(
        self,
        limit_name: str,
        identifier: str
    ) -> None:
        """Reset rate limit for identifier."""
        if limit_name in self.limiters:
            await self.limiters[limit_name].reset(identifier)


# Global rate limit manager
rate_limit_manager = RateLimitManager()


# FastAPI dependencies

async def check_api_rate_limit(request: Request):
    """Check general API rate limit."""
    client_ip = request.client.host
    
    if not await rate_limit_manager.check_rate_limit("api_general", client_ip):
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMIT_CONFIGS["api_general"].error_message
        )


async def check_websocket_rate_limit(client_ip: str) -> bool:
    """Check WebSocket connection rate limit."""
    return await rate_limit_manager.check_rate_limit("websocket_connect", client_ip)


async def check_llm_rate_limit(user_id: str) -> bool:
    """Check LLM request rate limit."""
    return await rate_limit_manager.check_rate_limit("llm_requests", user_id)


async def check_order_rate_limit(phone_number: str) -> bool:
    """Check order placement rate limit."""
    return await rate_limit_manager.check_rate_limit("order_placement", phone_number)


# Middleware for automatic rate limiting

class RateLimitMiddleware:
    """Middleware for automatic rate limiting."""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        """Initialize middleware."""
        self.app = app
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs"]
    
    async def __call__(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Get client identifier
        client_ip = request.client.host
        
        # Check rate limit
        if not await rate_limit_manager.check_rate_limit("api_general", client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": RATE_LIMIT_CONFIGS["api_general"].error_message,
                    "type": "rate_limit_error"
                }
            )
        
        # Process request
        response = await call_next(request)
        return response


# Utility functions

def get_client_identifier(request: Request) -> str:
    """Get client identifier from request."""
    # Try to get authenticated user ID
    if hasattr(request.state, "user_id"):
        return f"user:{request.state.user_id}"
    
    # Try to get API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api:{api_key}"
    
    # Fall back to IP address
    return f"ip:{request.client.host}"


async def check_custom_rate_limit(
    identifier: str,
    max_requests: int,
    window_seconds: int,
    limit_type: RateLimitType = RateLimitType.SLIDING_WINDOW
) -> bool:
    """Check custom rate limit."""
    config = RateLimitConfig(
        max_requests=max_requests,
        window_seconds=window_seconds,
        limit_type=limit_type,
        key_prefix="custom"
    )
    
    if rate_limit_manager.use_redis:
        limiter = RedisRateLimiter(config)
    else:
        limiter = InMemoryRateLimiter(config)
    
    return await limiter.is_allowed(identifier)


# Decorators for rate limiting

def rate_limit(
    limit_name: str,
    identifier_func: Optional[Callable[[Request], str]] = None
):
    """Decorator for rate limiting endpoints."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # Get identifier
            if identifier_func:
                identifier = identifier_func(request)
            else:
                identifier = get_client_identifier(request)
            
            # Check rate limit
            if not await rate_limit_manager.check_rate_limit(limit_name, identifier):
                raise HTTPException(
                    status_code=429,
                    detail=RATE_LIMIT_CONFIGS.get(
                        limit_name,
                        RateLimitConfig(0, 0)
                    ).error_message
                )
            
            # Call original function
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator