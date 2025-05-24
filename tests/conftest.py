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
    from app.utils.fsm_async import async_fsm_manager
    
    # Clear FSM instances
    async_fsm_manager._instances.clear()
    
    # Reset agent orchestrator state
    async_agent_orchestrator._initialized = False


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