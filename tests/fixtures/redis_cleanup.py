"""
Redis cleanup fixtures for integration tests.

This module provides fixtures that properly clean up Redis connections
and global state between tests to prevent event loop issues.
"""

import pytest
import pytest_asyncio
import asyncio
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis_globals():
    """
    Clean up global Redis connections and state before and after each test.
    This prevents event loop issues when tests are run together.
    """
    # Import modules that have global state
    import app.redis_async
    import app.fsm.core
    import app.utils.conversation_store_async
    
    # Clean up before test
    await _cleanup_redis_state(app.redis_async, app.fsm.core, app.utils.conversation_store_async)
    
    # Run the test
    yield
    
    # Clean up after test
    await _cleanup_redis_state(app.redis_async, app.fsm.core, app.utils.conversation_store_async)


async def _cleanup_redis_state(redis_module, fsm_module, conversation_store_module):
    """
    Helper function to clean up Redis-related global state.
    """
    # Clean up Redis client
    if hasattr(redis_module, '_redis_client') and redis_module._redis_client is not None:
        try:
            await redis_module._redis_client.aclose()
            await asyncio.sleep(0.1)  # Give connection time to close
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        finally:
            redis_module._redis_client = None
    
    # Clear memory caches
    if hasattr(redis_module, '_memory_cache'):
        redis_module._memory_cache.clear()
    if hasattr(redis_module, '_memory_cache_timestamps'):
        redis_module._memory_cache_timestamps.clear()
    
    # Clean up FSM manager
    if hasattr(fsm_module, 'async_fsm_manager'):
        await fsm_module.async_fsm_manager.cleanup_all()
    
    # Clean up conversation store
    if hasattr(conversation_store_module, 'async_conversation_store'):
        store = conversation_store_module.async_conversation_store
        if hasattr(store, '_redis_client') and store._redis_client is not None:
            try:
                await store._redis_client.aclose()
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Error closing conversation store Redis client: {e}")
            finally:
                store._redis_client = None
        
        # Clear any memory caches in conversation store
        if hasattr(store, '_memory_cache'):
            store._memory_cache.clear()


@pytest_asyncio.fixture
async def isolated_redis_client():
    """
    Provide an isolated Redis client for tests that need direct Redis access.
    This client is properly cleaned up after the test.
    """
    import redis.asyncio as aioredis
    import os
    
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Use a separate database for isolation
    if redis_url.endswith("/0"):
        redis_url = redis_url[:-1] + "1"  # Use database 1 for tests
    
    client = await aioredis.from_url(
        redis_url,
        decode_responses=True,
        socket_keepalive=False,
        socket_timeout=2.0,
        socket_connect_timeout=5.0
    )
    
    try:
        # Clear the test database
        await client.flushdb()
        yield client
    finally:
        # Clean up
        await client.flushdb()
        await client.aclose()
        await asyncio.sleep(0.1)


@pytest.fixture(autouse=True)
def reset_event_loop_policy():
    """
    Reset the event loop policy for each test to ensure clean state.
    """
    import asyncio
    
    # Store original policy
    original_policy = asyncio.get_event_loop_policy()
    
    # Create new policy for the test
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy') and asyncio.get_event_loop_policy().__class__.__name__ == 'WindowsProactorEventLoopPolicy':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    yield
    
    # Restore original policy
    asyncio.set_event_loop_policy(original_policy)


@pytest_asyncio.fixture
async def clean_app_state():
    """
    Fixture that ensures a clean application state for integration tests.
    Use this when you need to guarantee no state leakage.
    """
    # Import and clean all modules with global state
    import app.redis_async
    import app.fsm.core
    import app.utils.conversation_store_async
    import app.utils.agent_orchestration_async
    
    # Clean before test
    await _cleanup_redis_state(app.redis_async, app.fsm.core, app.utils.conversation_store_async)
    
    # Reset orchestrator sessions if it exists
    if hasattr(app.utils.agent_orchestration_async, 'AsyncAgentOrchestrator'):
        # Clear any global orchestrator instances
        pass  # Orchestrator doesn't have global instance, good!
    
    yield
    
    # Clean after test
    await _cleanup_redis_state(app.redis_async, app.fsm.core, app.utils.conversation_store_async)