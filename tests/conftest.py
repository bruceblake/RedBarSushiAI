"""
Test configuration and fixtures for RedBarSushiAI tests.
Simplified version that avoids importing the main app to prevent circular imports.
"""

import os
import sys
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.pool import NullPool
import redis.asyncio as aioredis
from unittest.mock import Mock, AsyncMock, MagicMock
import logging

# Add tests directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import health check
from health_check import wait_for_services

# No mocking fixtures for E2E tests - everything should hit real endpoints

# Set test environment
os.environ["TESTING"] = "1"
os.environ["LOG_LEVEL"] = "DEBUG"

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/redbarsushi_test")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")


# Session-scoped fixture to check services once per test session
@pytest.fixture(scope="session", autouse=True)
def ensure_services_healthy():
    """
    Ensure all required services are healthy before running any tests.
    This runs once per test session.
    """
    # Skip health check if explicitly disabled
    if os.getenv("SKIP_HEALTH_CHECK", "").lower() == "true":
        logger.info("Skipping health check (SKIP_HEALTH_CHECK=true)")
        return
    
# No unit tests anymore - all tests are E2E
    
    # Run health check synchronously
    try:
        import asyncio
        asyncio.run(wait_for_services(timeout=60))
    except Exception as e:
        pytest.exit(f"Service health check failed: {e}", returncode=1)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    import asyncio
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Disable connection pooling for tests
    )
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    TestSessionLocal = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Create a test Redis client."""
    # Import to ensure we can clean up global state
    import app.redis_async
    
    # Clean up any existing global Redis connection first
    if hasattr(app.redis_async, '_redis_client') and app.redis_async._redis_client is not None:
        try:
            await app.redis_async._redis_client.aclose()
            await asyncio.sleep(0.1)  # Give time for connection to close
        except Exception:
            pass
        finally:
            app.redis_async._redis_client = None
    
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    if "test" in redis_url:
        redis_url = redis_url.replace("redis-test", "redis")
    
    client = await aioredis.from_url(
        redis_url,
        decode_responses=True,
        socket_keepalive=False,  # Disable keepalive to avoid issues
        socket_timeout=2.0,
        socket_connect_timeout=5.0
    )
    
    # Clear test database
    await client.flushdb()
    
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.aclose()
    await asyncio.sleep(0.1)  # Give time for connection to close properly


# No mock fixtures - E2E tests use real services


# Performance tracking
@pytest.fixture(autouse=True)
def track_test_duration(request):
    """Track test execution time and log slow tests."""
    import time
    start_time = time.time()
    
    def finalizer():
        duration = time.time() - start_time
        # Only E2E tests remain
        if duration > 10:
            logger.warning(f"Slow e2e test: {request.node.nodeid} took {duration:.2f}s")
        else:
            logger.info(f"E2E test: {request.node.nodeid} took {duration:.2f}s")
    
    request.addfinalizer(finalizer)