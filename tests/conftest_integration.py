"""
Shared fixtures for integration tests.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.menu_async import Base, MenuItem, MenuCategory, MenuNameVariant
from app.config import settings
from app.redis_async import get_redis_pool


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database session."""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def sample_menu_items(test_db):
    """Create sample menu items for testing."""
    # Create categories
    sushi_category = MenuCategory(
        name="Sushi Rolls",
        description="Fresh sushi rolls",
        display_order=1,
        is_active=True
    )
    appetizer_category = MenuCategory(
        name="Appetizers",
        description="Start your meal",
        display_order=2,
        is_active=True
    )
    
    test_db.add_all([sushi_category, appetizer_category])
    await test_db.commit()
    
    # Create menu items
    california_roll = MenuItem(
        name="California Roll",
        description="Crab, avocado, cucumber",
        price=12.95,
        category_id=sushi_category.id,
        plu="CAL001",
        is_available=True,
        is_active=True,
        prep_time_minutes=10
    )
    
    spicy_tuna_roll = MenuItem(
        name="Spicy Tuna Roll",
        description="Spicy tuna, cucumber",
        price=14.95,
        category_id=sushi_category.id,
        plu="STR001",
        is_available=True,
        is_active=True,
        prep_time_minutes=12
    )
    
    edamame = MenuItem(
        name="Edamame",
        description="Steamed soybeans",
        price=5.95,
        category_id=appetizer_category.id,
        plu="EDA001",
        is_available=True,
        is_active=True,
        prep_time_minutes=5
    )
    
    test_db.add_all([california_roll, spicy_tuna_roll, edamame])
    await test_db.commit()
    
    # Create name variants
    cal_variant1 = MenuNameVariant(
        menu_item_id=california_roll.id,
        variant_name="cali roll",
        variant_type="spoken"
    )
    cal_variant2 = MenuNameVariant(
        menu_item_id=california_roll.id,
        variant_name="california",
        variant_type="abbreviation"
    )
    
    tuna_variant = MenuNameVariant(
        menu_item_id=spicy_tuna_roll.id,
        variant_name="spicy tuna",
        variant_type="spoken"
    )
    
    test_db.add_all([cal_variant1, cal_variant2, tuna_variant])
    await test_db.commit()
    
    return {
        "california_roll": california_roll,
        "spicy_tuna_roll": spicy_tuna_roll,
        "edamame": edamame,
        "categories": {
            "sushi": sushi_category,
            "appetizers": appetizer_category
        }
    }


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock()
    
    # Storage for mock Redis
    storage = {}
    
    async def mock_get(key):
        return storage.get(key)
    
    async def mock_set(key, value, ex=None):
        storage[key] = value
        return True
    
    async def mock_delete(key):
        if key in storage:
            del storage[key]
        return True
    
    async def mock_exists(key):
        return key in storage
    
    mock.get = mock_get
    mock.set = mock_set
    mock.delete = mock_delete
    mock.exists = mock_exists
    mock.ping = AsyncMock(return_value=True)
    
    return mock


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = MagicMock()
    
    # Mock chat completions
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.function_call = None
    
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    return mock_client


@pytest.fixture
def mock_deliverect_service():
    """Create a mock Deliverect service."""
    mock_service = AsyncMock()
    
    # Mock order submission
    mock_service.submit_order = AsyncMock(return_value={
        "order_id": "DEL-TEST-001",
        "status": "accepted",
        "estimated_time": "25 minutes"
    })
    
    # Mock order status check
    mock_service.get_order_status = AsyncMock(return_value={
        "order_id": "DEL-TEST-001",
        "status": "preparing",
        "estimated_time": "20 minutes"
    })
    
    return mock_service


@pytest.fixture
async def mock_fsm_manager(mock_redis):
    """Create a mock FSM manager."""
    from app.utils.fsm_async import AsyncFSMManager
    
    manager = AsyncFSMManager(redis_client=mock_redis)
    return manager


@pytest.fixture
def correlation_id():
    """Provide a test correlation ID."""
    return "test-correlation-12345"


@pytest.fixture(autouse=True)
def setup_correlation_id(correlation_id):
    """Set up correlation ID for all tests."""
    from app.utils.correlation_id import set_correlation_id
    set_correlation_id(correlation_id)