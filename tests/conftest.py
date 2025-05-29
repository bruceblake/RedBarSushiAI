"""
Test configuration and fixtures for RedBarSushiAI tests.
Simplified version that avoids importing the main app to prevent circular imports.
"""

import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.pool import NullPool
import redis.asyncio as aioredis
from unittest.mock import Mock, AsyncMock, MagicMock

# Set test environment
os.environ["TESTING"] = "1"
os.environ["LOG_LEVEL"] = "DEBUG"

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/redbarsushi_test")


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    import asyncio
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest_asyncio.fixture(scope="session")
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
    client = await aioredis.from_url(
        "redis://localhost:6379/15",  # Use database 15 for tests
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