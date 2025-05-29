"""
E2E tests against the ngrok-exposed system.
"""
import pytest
import httpx
import asyncio
import json
import websockets
from typing import Dict, Any


NGROK_URL = "https://9322-149-40-62-16.ngrok-free.app"


class TestNgrokSystem:
    """Test the system via ngrok tunnel."""
    
    @pytest.mark.asyncio
    async def test_ngrok_health(self):
        """Test system health via ngrok."""
        async with httpx.AsyncClient() as client:
            # ngrok requires a header
            headers = {"ngrok-skip-browser-warning": "true"}
            
            # Test root
            response = await client.get(NGROK_URL + "/", headers=headers, follow_redirects=True)
            print(f"\nRoot endpoint status: {response.status_code}")
            assert response.status_code in [200, 307]
            
            # Test healthcheck
            response = await client.get(NGROK_URL + "/healthcheck", headers=headers)
            print(f"Healthcheck status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Health data: {data}")
                assert "status" in data
    
    @pytest.mark.asyncio
    async def test_ngrok_api_docs(self):
        """Test API documentation via ngrok."""
        async with httpx.AsyncClient() as client:
            headers = {"ngrok-skip-browser-warning": "true"}
            
            # Test OpenAPI JSON
            response = await client.get(NGROK_URL + "/openapi.json", headers=headers)
            print(f"\nOpenAPI status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"API Title: {data.get('info', {}).get('title')}")
                print(f"Number of endpoints: {len(data.get('paths', {}))}")
    
    @pytest.mark.asyncio
    async def test_ngrok_menu_system(self):
        """Test menu system via ngrok."""
        async with httpx.AsyncClient() as client:
            headers = {"ngrok-skip-browser-warning": "true"}
            
            # Get menu categories
            response = await client.get(NGROK_URL + "/menu/categories", headers=headers)
            print(f"\nMenu categories status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                categories = data.get("categories", [])
                print(f"Number of categories: {len(categories)}")
                if categories:
                    print(f"First category: {categories[0].get('name')}")
            
            # Get menu items
            response = await client.get(NGROK_URL + "/menu/items", headers=headers)
            print(f"Menu items status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                print(f"Number of items: {len(items)}")
                if items:
                    print(f"First item: {items[0].get('name')} - ${items[0].get('price', 0)/100:.2f}")
    
    @pytest.mark.asyncio
    async def test_ngrok_voice_endpoint(self):
        """Test voice webhook via ngrok."""
        async with httpx.AsyncClient() as client:
            headers = {
                "ngrok-skip-browser-warning": "true",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Simulate Twilio webhook
            form_data = {
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing"
            }
            
            response = await client.post(
                NGROK_URL + "/voice/webhook",
                data=form_data,
                headers=headers
            )
            print(f"\nVoice webhook status: {response.status_code}")
            if response.status_code == 200:
                print("TwiML Response received:")
                print(response.text[:500])  # First 500 chars of TwiML
    
    @pytest.mark.asyncio
    async def test_ngrok_websocket(self):
        """Test WebSocket connection via ngrok."""
        # Convert HTTPS to WSS
        ws_url = NGROK_URL.replace("https://", "wss://")
        call_sid = "test-ngrok-123"
        
        # Try different WebSocket endpoints
        endpoints = [
            f"/realtime/ws/media/{call_sid}",
            f"/ws/media/{call_sid}",
            f"/ws-test/{call_sid}"
        ]
        
        for endpoint in endpoints:
            full_url = ws_url + endpoint
            print(f"\nTrying WebSocket: {full_url}")
            
            try:
                # ngrok WebSocket requires headers
                headers = {
                    "ngrok-skip-browser-warning": "true"
                }
                
                async with websockets.connect(full_url, extra_headers=headers) as ws:
                    print(f"✅ Connected to {endpoint}")
                    
                    # Send test message
                    await ws.send(json.dumps({
                        "event": "connected",
                        "protocol": "Call",
                        "version": "1.0.0"
                    }))
                    
                    # Try to receive
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        print(f"Received: {response[:100]}...")
                    except asyncio.TimeoutError:
                        print("No response within timeout")
                        
            except Exception as e:
                print(f"❌ Failed to connect: {type(e).__name__}: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_ngrok_order_flow(self):
        """Test order flow via ngrok."""
        async with httpx.AsyncClient() as client:
            headers = {"ngrok-skip-browser-warning": "true"}
            
            # Take order
            order_data = {
                "items": [{"name": "California Roll", "quantity": 2}],
                "customer_info": {
                    "name": "Ngrok Test",
                    "phone": "+15551234567"
                }
            }
            
            response = await client.post(
                NGROK_URL + "/order/take_order",
                json=order_data,
                headers=headers
            )
            print(f"\nTake order status: {response.status_code}")
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"Order result: {result}")
            elif response.status_code == 422:
                error = response.json()
                print(f"Validation error: {error}")
    
    @pytest.mark.asyncio
    async def test_ngrok_environment(self):
        """Test environment info via ngrok."""
        async with httpx.AsyncClient() as client:
            headers = {"ngrok-skip-browser-warning": "true"}
            
            response = await client.get(NGROK_URL + "/environment", headers=headers)
            print(f"\nEnvironment status: {response.status_code}")
            if response.status_code == 200:
                env = response.json()
                print(f"Environment: {json.dumps(env, indent=2)}")


if __name__ == "__main__":
    print(f"Testing ngrok URL: {NGROK_URL}")
    pytest.main([__file__, "-v", "-s"])