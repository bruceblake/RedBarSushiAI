"""
Test configuration and fixtures for RedBarSushiAI tests.
Simplified version that avoids importing the main app to prevent circular imports.
"""

import os
import sys
import pytest
import pytest_asyncio
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

# Set test environment
os.environ["TESTING"] = "1"
os.environ["LOG_LEVEL"] = "DEBUG"

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/redbarsushi_test")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "requires_redis: mark test as requiring Redis")
    config.addinivalue_line("markers", "requires_db: mark test as requiring database")


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
    
    # Skip for unit tests
    if os.getenv("PYTEST_CURRENT_TEST", "").find("unit") != -1:
        logger.info("Skipping health check for unit tests")
        return
    
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
    redis_url = os.getenv("REDIS_URL", "redis://redis-test:6379/0")
    client = await aioredis.from_url(
        redis_url,
        decode_responses=True
    )
    
    # Clear test database
    await client.flushdb()
    
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock()
    mock.audio.speech.create = AsyncMock()
    return mock


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client for testing."""
    mock = MagicMock()
    mock.messages.create = MagicMock()
    mock.calls.create = MagicMock()
    return mock


@pytest.fixture
def mock_deliverect_client():
    """Mock Deliverect client for testing."""
    mock = MagicMock()
    mock.create_order = AsyncMock()
    mock.get_order_status = AsyncMock()
    mock.get_menu = AsyncMock()
    return mock


@pytest.fixture
def sample_menu_item():
    """Sample menu item for testing."""
    return {
        "id": 1,
        "name": "California Roll",
        "description": "Crab, avocado, and cucumber",
        "price": 850,
        "plu": "ROLL_001",
        "category_id": 1,
        "is_available": True
    }


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return {
        "id": 1,
        "customer_phone": "+1234567890",
        "order_type": "pickup",
        "status": "pending",
        "total_price": 2550,
        "items": [
            {
                "menu_item_plu": "ROLL_001",
                "quantity": 2,
                "modifiers": []
            },
            {
                "menu_item_plu": "ROLL_002",
                "quantity": 1,
                "modifiers": ["MOD_001"]
            }
        ]
    }


@pytest.fixture
def sample_location():
    """Sample location for testing."""
    return {
        "id": 1,
        "name": "Red Bar Sushi - Main",
        "deliverect_location_id": "test_location_123",
        "deliverect_channel_link_id": "test_channel_123",
        "is_active": True,
        "settings": {
            "business_hours": {
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "11:00", "close": "23:00"},
                "sunday": {"open": "12:00", "close": "21:00"}
            }
        }
    }


# Performance tracking
@pytest.fixture(autouse=True)
def track_test_duration(request):
    """Track test execution time and log slow tests."""
    import time
    start_time = time.time()
    
    def finalizer():
        duration = time.time() - start_time
        # Different thresholds for different test types
        if "unit" in request.node.keywords and duration > 1:
            logger.warning(f"Slow unit test: {request.node.nodeid} took {duration:.2f}s")
        elif "integration" in request.node.keywords and duration > 5:
            logger.warning(f"Slow integration test: {request.node.nodeid} took {duration:.2f}s")
        elif "e2e" in request.node.keywords and duration > 10:
            logger.warning(f"Slow e2e test: {request.node.nodeid} took {duration:.2f}s")
        elif duration > 3:  # Default threshold
            logger.warning(f"Slow test: {request.node.nodeid} took {duration:.2f}s")
    
    request.addfinalizer(finalizer)