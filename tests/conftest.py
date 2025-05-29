"""
Simple test configuration.
"""

import pytest
import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment
os.environ["TESTING"] = "True"

# Import after setting environment
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Get FastAPI app."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def client(app):
    """Test client for FastAPI."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app):
    """Async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    client = AsyncMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response"))]
    )
    return client


@pytest.fixture
def mock_twilio():
    """Mock Twilio client."""
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid="SMtest123")
    return client


@pytest.fixture
def mock_deliverect():
    """Mock Deliverect client."""
    client = AsyncMock()
    client.submit_order.return_value = {"_id": "test123", "status": 1}
    return client


@pytest.fixture
async def db_session():
    """Test database session."""
    from app.db_async import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_menu_item():
    """Sample menu item for testing."""
    return {
        "id": 1,
        "name": "California Roll",
        "plu": "PLU_CALI",
        "price": 1295,
        "is_available": True
    }


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return {
        "customer_name": "Test User",
        "customer_phone": "+1234567890",
        "items": [
            {
                "plu": "PLU_CALI",
                "name": "California Roll",
                "quantity": 2,
                "price": 1295
            }
        ],
        "total": 2590
    }


# Simple test markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")