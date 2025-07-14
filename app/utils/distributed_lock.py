"""
Distributed Lock Implementation for RedBarSushiAI.

This module provides Redis-based distributed locking to prevent race conditions
during critical operations like order submission.
"""

import asyncio
import time
import uuid
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager

from app.utils.redis_utils_async import get_redis
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class DistributedLockError(Exception):
    """Raised when distributed lock operations fail."""
    pass


class DistributedLockTimeout(DistributedLockError):
    """Raised when unable to acquire lock within timeout."""
    pass


class DistributedLock:
    """
    Redis-based distributed lock implementation with automatic expiration.
    
    Uses SETNX with expiration to ensure locks are automatically released
    even if the holder crashes or fails to release explicitly.
    """
    
    def __init__(
        self,
        key: str,
        timeout: float = 30.0,
        acquire_timeout: float = 10.0,
        check_interval: float = 0.1
    ):
        """
        Initialize distributed lock.
        
        Args:
            key: Unique lock key (will be prefixed with 'lock:')
            timeout: Lock expiration timeout in seconds
            acquire_timeout: Maximum time to wait to acquire lock in seconds
            check_interval: Interval between acquisition attempts in seconds
        """
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.acquire_timeout = acquire_timeout
        self.check_interval = check_interval
        self.lock_value = str(uuid.uuid4())  # Unique value to prevent accidental unlock
        self.acquired = False
        
    async def acquire(self) -> bool:
        """
        Attempt to acquire the distributed lock.
        
        Returns:
            True if lock acquired successfully, False otherwise
            
        Raises:
            DistributedLockTimeout: If unable to acquire within acquire_timeout
        """
        start_time = time.time()
        redis_client = await get_redis()
        
        while time.time() - start_time < self.acquire_timeout:
            try:
                # Use SETNX with expiration - atomic operation
                result = await redis_client.set(
                    self.key, 
                    self.lock_value, 
                    nx=True,  # Only set if key doesn't exist
                    ex=int(self.timeout)  # Expiration in seconds
                )
                
                if result:
                    self.acquired = True
                    logger.info(f"Distributed lock acquired: {self.key}")
                    return True
                    
                # Lock is held by someone else, wait and retry
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error acquiring distributed lock {self.key}: {e}")
                raise DistributedLockError(f"Failed to acquire lock: {e}")
        
        # Timeout exceeded
        raise DistributedLockTimeout(f"Could not acquire lock {self.key} within {self.acquire_timeout}s")
    
    async def release(self) -> bool:
        """
        Release the distributed lock.
        
        Returns:
            True if lock was successfully released, False if lock wasn't held
        """
        if not self.acquired:
            logger.warning(f"Attempted to release unacquired lock: {self.key}")
            return False
            
        try:
            redis_client = await get_redis()
            
            # Lua script for atomic check-and-delete
            # Only delete if the value matches our lock value
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = await redis_client.eval(lua_script, 1, self.key, self.lock_value)
            
            if result == 1:
                self.acquired = False
                logger.info(f"Distributed lock released: {self.key}")
                return True
            else:
                logger.warning(f"Lock {self.key} was not held or already expired")
                self.acquired = False
                return False
                
        except Exception as e:
            logger.error(f"Error releasing distributed lock {self.key}: {e}")
            self.acquired = False
            raise DistributedLockError(f"Failed to release lock: {e}")
    
    async def extend(self, additional_time: float = None) -> bool:
        """
        Extend the lock timeout.
        
        Args:
            additional_time: Additional seconds to extend (defaults to original timeout)
            
        Returns:
            True if extension successful, False otherwise
        """
        if not self.acquired:
            return False
            
        if additional_time is None:
            additional_time = self.timeout
            
        try:
            redis_client = await get_redis()
            
            # Lua script for atomic check-and-extend
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            
            result = await redis_client.eval(
                lua_script, 1, self.key, self.lock_value, int(additional_time)
            )
            
            if result == 1:
                logger.debug(f"Extended lock {self.key} by {additional_time}s")
                return True
            else:
                logger.warning(f"Could not extend lock {self.key} - not held or expired")
                self.acquired = False
                return False
                
        except Exception as e:
            logger.error(f"Error extending distributed lock {self.key}: {e}")
            return False
    
    async def is_locked(self) -> bool:
        """
        Check if the lock is currently held (by anyone).
        
        Returns:
            True if lock exists, False otherwise
        """
        try:
            redis_client = await get_redis()
            result = await redis_client.exists(self.key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking lock status {self.key}: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.release()


@asynccontextmanager
async def distributed_lock(
    key: str,
    timeout: float = 30.0,
    acquire_timeout: float = 10.0
) -> AsyncContextManager[DistributedLock]:
    """
    Async context manager for distributed locking.
    
    Args:
        key: Unique lock key
        timeout: Lock expiration timeout in seconds
        acquire_timeout: Maximum time to wait to acquire lock
        
    Example:
        async with distributed_lock("order_submission:call_123"):
            # Critical section protected by distributed lock
            await submit_order_to_pos(order_data)
    """
    lock = DistributedLock(key, timeout, acquire_timeout)
    try:
        await lock.acquire()
        yield lock
    finally:
        await lock.release()


class OrderSubmissionLock:
    """
    Specialized lock for order submission operations.
    
    Provides higher-level interface for protecting order submission
    with appropriate timeouts and error handling.
    """
    
    @staticmethod
    async def acquire_order_lock(call_sid: str) -> AsyncContextManager[DistributedLock]:
        """
        Acquire order submission lock for a specific call.
        
        Args:
            call_sid: Call SID to lock order submission for
            
        Returns:
            Async context manager for the lock
        """
        return distributed_lock(
            key=f"order_submission:{call_sid}",
            timeout=60.0,  # Order submission can take up to 60 seconds
            acquire_timeout=5.0  # Don't wait too long for lock acquisition
        )
    
    @staticmethod
    async def check_order_cancellation(call_sid: str) -> bool:
        """
        Check if an order cancellation is in progress for this call.
        
        Args:
            call_sid: Call SID to check
            
        Returns:
            True if cancellation lock exists, False otherwise
        """
        cancellation_lock = DistributedLock(f"order_cancellation:{call_sid}")
        return await cancellation_lock.is_locked()
    
    @staticmethod
    async def acquire_cancellation_lock(call_sid: str) -> AsyncContextManager[DistributedLock]:
        """
        Acquire order cancellation lock for a specific call.
        
        Args:
            call_sid: Call SID to lock order cancellation for
            
        Returns:
            Async context manager for the lock
        """
        return distributed_lock(
            key=f"order_cancellation:{call_sid}",
            timeout=30.0,  # Cancellation should be quick
            acquire_timeout=2.0  # Quick acquisition for cancellation
        )