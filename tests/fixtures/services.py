"""
Service fixtures that adapt to test environment.
Provides mock or real services based on configuration.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator, Optional

from tests.test_config import get_test_config, is_mock_environment
from app.utils.deliverect.orders_async import DeliverectClient
from twilio.rest import Client as TwilioClient
from openai import AsyncOpenAI


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide HTTP client for API testing."""
    config = get_test_config()
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(config.test_timeout)
    ) as client:
        yield client


@pytest.fixture
async def mock_server_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Direct client to mock server."""
    config = get_test_config()
    
    async with httpx.AsyncClient(
        base_url=config.mock_server_url,
        timeout=httpx.Timeout(5.0)
    ) as client:
        # Reset mock state
        await client.post("/mock/reset")
        
        # Seed test data
        await client.post("/mock/menu/seed")
        
        yield client


@pytest.fixture
async def twilio_client(mock_server_client):
    """Provide Twilio client (mock or real based on config)."""
    config = get_test_config()
    
    if is_mock_environment():
        # Return mock client that uses mock server
        client = MagicMock(spec=TwilioClient)
        
        # Mock message sending
        async def mock_send_message(**kwargs):
            response = await mock_server_client.post(
                "/twilio/sms/send",
                json=kwargs
            )
            return response.json()
        
        client.messages.create = AsyncMock(side_effect=mock_send_message)
        return client
    else:
        # Real Twilio client
        return TwilioClient(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )


@pytest.fixture
async def openai_client(mock_server_client):
    """Provide OpenAI client (mock or real based on config)."""
    config = get_test_config()
    
    if is_mock_environment():
        # Create mock client that uses mock server
        class MockOpenAIClient:
            def __init__(self, mock_client):
                self.mock_client = mock_client
                self.chat = self
                self.completions = self
            
            async def create(self, **kwargs):
                response = await self.mock_client.post(
                    "/openai/v1/chat/completions",
                    json=kwargs
                )
                return MagicMock(**response.json())
        
        return MockOpenAIClient(mock_server_client)
    else:
        # Real OpenAI client
        return AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=config.openai_base_url if config.environment == "staging" else None
        )


@pytest.fixture
async def deliverect_client(mock_server_client):
    """Provide Deliverect client (mock or real based on config)."""
    config = get_test_config()
    
    if is_mock_environment():
        # Mock Deliverect client
        class MockDeliverectClient:
            def __init__(self, mock_client):
                self.mock_client = mock_client
            
            async def submit_order(self, order_data):
                response = await self.mock_client.post(
                    "/deliverect/orders",
                    json=order_data
                )
                return response.json()
            
            async def get_order_status(self, order_id):
                response = await self.mock_client.get(
                    f"/deliverect/orders/{order_id}"
                )
                return response.json()
            
            async def get_locations(self):
                response = await self.mock_client.get("/deliverect/locations")
                return response.json()
        
        return MockDeliverectClient(mock_server_client)
    else:
        # Real Deliverect client
        return DeliverectClient(
            api_key=os.getenv("DELIVERECT_API_KEY"),
            base_url=config.deliverect_base_url
        )


@pytest.fixture
async def realtime_websocket_url():
    """Get WebSocket URL for Realtime API."""
    config = get_test_config()
    
    if is_mock_environment():
        return f"ws://localhost:8001/openai/v1/realtime"
    else:
        return "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"


@pytest.fixture
def api_headers():
    """Get appropriate API headers for current environment."""
    config = get_test_config()
    
    if is_mock_environment():
        return {
            "Authorization": "Bearer mock-token",
            "Content-Type": "application/json"
        }
    else:
        return {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1",
            "Content-Type": "application/json"
        }


# Service health checks
async def check_service_health(service_name: str, health_url: str) -> bool:
    """Check if a service is healthy."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            return response.status_code == 200
    except:
        return False


@pytest.fixture
async def ensure_services_ready(mock_server_client):
    """Ensure all required services are ready."""
    config = get_test_config()
    
    if is_mock_environment():
        # Check mock server is ready
        health = await check_service_health(
            "mock_server",
            f"{config.mock_server_url}/health"
        )
        if not health:
            pytest.skip("Mock server not ready")
    else:
        # Check real services in staging
        if config.environment == "staging":
            # Could add health checks for real services
            pass
    
    yield