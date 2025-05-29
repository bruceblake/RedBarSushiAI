"""
Main conftest.py for all tests.
This file contains common fixtures and configurations for all test types.
"""

import pytest
import os
import sys
import asyncio
from typing import Generator, AsyncGenerator
import logging

# Add the project root to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set testing environment variables
os.environ["TESTING"] = "True"
os.environ["FASTAPI_ENV"] = "testing"
os.environ["NO_X11"] = "1"
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
os.environ["FORCE_HEADLESS"] = "true"

# Set required environment variables if not present
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key"
if not os.environ.get("APP_SECRET_KEY"):
    os.environ["APP_SECRET_KEY"] = "test-secret-key"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import FastAPI testing utilities
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Base URL for tests
TEST_BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def app():
    """Get the FastAPI application."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="function")
def client(app):
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url=TEST_BASE_URL) as ac:
        yield ac


@pytest.fixture(scope="function")
def mock_openai_response():
    """Mock OpenAI API response for testing."""
    return {
        "choices": [{
            "message": {
                "content": "This is a test response",
                "role": "assistant"
            }
        }]
    }


@pytest.fixture(scope="function")
def sample_twilio_request():
    """Sample Twilio webhook request data."""
    return {
        "CallSid": "CAtest123456789",
        "From": "+15551234567",
        "To": "+15559876543",
        "CallStatus": "in-progress",
        "Direction": "inbound",
        "AccountSid": "ACtest123456789"
    }


@pytest.fixture(scope="function")
def sample_menu_item():
    """Sample menu item for testing."""
    return {
        "id": "test-item-1",
        "name": "California Roll",
        "description": "Crab, avocado, cucumber",
        "price": 8.95,
        "category": "Rolls",
        "is_available": True,
        "plu": "100"
    }


@pytest.fixture(scope="function")
async def test_db_session():
    """Create a test database session."""
    from app.db_async import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset any singleton instances to ensure test isolation
    from app.utils.agent_orchestration_async import async_agent_orchestrator
    from app.fsm.core import async_fsm_manager
    
    # Clear FSM instances
    if hasattr(async_fsm_manager, 'fsm_instances'):
        async_fsm_manager.fsm_instances.clear()
    
    # Reset agent orchestrator state
    if hasattr(async_agent_orchestrator, 'active_sessions'):
        async_agent_orchestrator.active_sessions.clear()
    if hasattr(async_agent_orchestrator, 'conversations'):
        async_agent_orchestrator.conversations.clear()


# Skip markers for different test categories
slow = pytest.mark.slow
integration = pytest.mark.integration
unit = pytest.mark.unit
e2e = pytest.mark.e2e
requires_openai = pytest.mark.skipif(
    os.getenv("DISABLE_OPENAI", "false").lower() == "true",
    reason="OpenAI API tests disabled"
)
requires_twilio = pytest.mark.skipif(
    not os.getenv("TWILIO_ACCOUNT_SID"),
    reason="Twilio credentials not available"
)
requires_deliverect = pytest.mark.skipif(
    not os.getenv("DELIVERECT_API_KEY"),
    reason="Deliverect credentials not available"
)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (only runs in staging)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "requires_twilio: test requires Twilio credentials"
    )
    config.addinivalue_line(
        "markers", "requires_openai: test requires OpenAI API access"
    )
    config.addinivalue_line(
        "markers", "requires_deliverect: test requires Deliverect access"
    )


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests in development environment."""
    if os.getenv("FASTAPI_ENV", "development") != "staging":
        skip_e2e = pytest.mark.skip(reason="E2E tests only run in staging environment")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


# Environment-specific test data
@pytest.fixture
def test_phone_number():
    """Get appropriate test phone number based on environment."""
    env = os.getenv("FASTAPI_ENV", "development")
    if env == "staging":
        # Use real Twilio test number in staging
        return os.getenv("TWILIO_TEST_PHONE_NUMBER", "+15005550006")
    else:
        # Use mock number in development
        return "+15555551234"


@pytest.fixture
def test_openai_model():
    """Get appropriate OpenAI model for testing."""
    env = os.getenv("FASTAPI_ENV", "development")
    if env == "staging":
        # Use cheaper/faster model for staging tests
        return "gpt-3.5-turbo"
    else:
        # Mock in development
        return "mock-model"


@pytest.fixture
def deliverect_test_mode():
    """Determine Deliverect test mode."""
    env = os.getenv("FASTAPI_ENV", "development")
    if env == "staging":
        return "sandbox"  # Use Deliverect sandbox
    else:
        return "mock"  # Use mocked responses