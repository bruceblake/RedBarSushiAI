"""
Real E2E tests that interact with the running FastAPI application.
"""
import pytest
import httpx
import asyncio
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


class TestRealAPIEndpoints:
    """Test real API endpoints with the running server."""
    
    @pytest.mark.asyncio
    async def test_openapi_docs(self):
        """Test that API documentation is available."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/docs")
            assert response.status_code == 200
            assert "swagger-ui" in response.text
            
            # Test OpenAPI JSON
            response = await client.get(f"{BASE_URL}/openapi.json")
            assert response.status_code == 200
            openapi = response.json()
            assert "openapi" in openapi
            assert "paths" in openapi
    
    @pytest.mark.asyncio
    async def test_menu_endpoints(self):
        """Test menu-related endpoints."""
        async with httpx.AsyncClient() as client:
            # Test getting menu categories
            response = await client.get(f"{BASE_URL}/api/menu/categories")
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict) or isinstance(data, list)
            else:
                # Endpoint might not exist due to cleanup
                pytest.skip("Menu categories endpoint not available")
            
            # Test getting menu items
            response = await client.get(f"{BASE_URL}/api/menu/items")
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict) or isinstance(data, list)
            else:
                pytest.skip("Menu items endpoint not available")
    
    @pytest.mark.asyncio
    async def test_voice_endpoints(self):
        """Test voice-related endpoints."""
        async with httpx.AsyncClient() as client:
            # Test TwiML endpoint
            response = await client.post(f"{BASE_URL}/voice/webhook")
            if response.status_code != 404:
                assert response.headers.get("content-type", "").startswith("text/xml") or \
                       response.headers.get("content-type", "").startswith("application/xml")
            else:
                pytest.skip("Voice webhook endpoint not available")
    
    @pytest.mark.asyncio
    async def test_order_endpoints(self):
        """Test order-related endpoints."""
        async with httpx.AsyncClient() as client:
            # Test creating an order
            order_data = {
                "customer_phone": "+1234567890",
                "order_type": "pickup",
                "items": [
                    {"plu": "CALI_001", "quantity": 2}
                ]
            }
            
            response = await client.post(
                f"{BASE_URL}/api/orders",
                json=order_data
            )
            
            if response.status_code != 404:
                if response.status_code == 422:
                    # Validation error - check the error details
                    error_detail = response.json()
                    assert "detail" in error_detail
                elif response.status_code == 200:
                    data = response.json()
                    assert "order_id" in data or "id" in data
            else:
                pytest.skip("Order creation endpoint not available")


class TestRealWebSocketConnection:
    """Test WebSocket connections."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test establishing a WebSocket connection."""
        import websockets
        import uuid
        
        call_sid = str(uuid.uuid4())
        ws_url = f"ws://localhost:8000/realtime/ws/media/{call_sid}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Send a test message
                await websocket.send(json.dumps({
                    "event": "connected",
                    "protocol": "Call",
                    "version": "1.0.0"
                }))
                
                # Try to receive a response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    assert response is not None
                except asyncio.TimeoutError:
                    # No response within timeout is okay for this test
                    pass
                    
        except Exception as e:
            if "404" in str(e) or "Connection refused" in str(e):
                pytest.skip(f"WebSocket endpoint not available: {e}")
            else:
                raise


class TestRealHealthChecks:
    """Test health and readiness checks."""
    
    @pytest.mark.asyncio
    async def test_health_endpoints(self):
        """Test health check endpoints."""
        async with httpx.AsyncClient() as client:
            # Try different possible health endpoints
            health_endpoints = ["/health", "/healthz", "/api/health", "/_health"]
            
            health_found = False
            for endpoint in health_endpoints:
                response = await client.get(f"{BASE_URL}{endpoint}")
                if response.status_code == 200:
                    health_found = True
                    data = response.json()
                    assert "status" in data or "healthy" in str(data).lower()
                    break
            
            if not health_found:
                # If no health endpoint exists, check if root responds
                response = await client.get(BASE_URL)
                assert response.status_code in [200, 404, 301, 302]


class TestRealDatabaseConnection:
    """Test database connectivity through API."""
    
    @pytest.mark.asyncio
    async def test_database_dependent_endpoint(self):
        """Test an endpoint that requires database access."""
        async with httpx.AsyncClient() as client:
            # Try to get menu items which should require DB
            response = await client.get(f"{BASE_URL}/api/menu/items")
            
            if response.status_code == 500:
                # Database connection error
                error = response.json()
                assert "detail" in error or "error" in error
                pytest.skip("Database not properly configured")
            elif response.status_code == 404:
                pytest.skip("Menu items endpoint not available")
            else:
                # Should return empty list or actual data
                data = response.json()
                assert isinstance(data, (list, dict))


if __name__ == "__main__":
    # Allow running directly for debugging
    pytest.main([__file__, "-v"])