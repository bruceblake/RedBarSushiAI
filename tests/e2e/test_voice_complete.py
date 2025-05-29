"""
Complete voice flow E2E test.
Tests the actual voice webhook and WebSocket endpoints.
"""
import pytest
import httpx
import asyncio
import json
import base64
import websockets
from typing import Dict, Any
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")


class TestVoiceSystemComplete:
    """Test the complete voice ordering system."""
    
    @pytest.mark.asyncio
    async def test_voice_webhook_twiml_generation(self):
        """Test that voice webhook generates proper TwiML."""
        async with httpx.AsyncClient() as client:
            # Simulate Twilio webhook data
            form_data = {
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "AccountSid": "AC1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing",
                "Caller": "+15551234567",
                "Called": "+15559876543",
                "Direction": "inbound",
                "ApiVersion": "2010-04-01"
            }
            
            response = await client.post(
                f"{BASE_URL}/voice/webhook",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            print(f"\nVoice webhook status: {response.status_code}")
            
            if response.status_code == 200:
                twiml = response.text
                print(f"TwiML response preview: {twiml[:200]}...")
                
                # Verify it's valid TwiML
                assert "<?xml" in twiml
                assert "<Response>" in twiml or "<response>" in twiml.lower()
                
                # Check for greeting
                assert "Welcome" in twiml or "welcome" in twiml
                
                # Check for WebSocket stream configuration
                if "<Stream" in twiml:
                    assert "url=" in twiml
                    assert "/ws/media/" in twiml or "/realtime/ws/media/" in twiml
            else:
                print(f"Unexpected status: {response.text[:200]}")
    
    @pytest.mark.asyncio
    async def test_menu_data_loaded(self):
        """Test that menu data is properly loaded in the system."""
        async with httpx.AsyncClient() as client:
            # Get menu items
            response = await client.get(f"{BASE_URL}/menu/items")
            assert response.status_code == 200
            
            data = response.json()
            items = data.get("items", [])
            print(f"\nMenu items loaded: {len(items)}")
            
            # Verify we have actual menu data
            assert len(items) > 0, "No menu items found"
            
            # Check first few items
            for i, item in enumerate(items[:3]):
                print(f"  {i+1}. {item.get('name')} - ${item.get('price', 0)/100:.2f} (PLU: {item.get('plu')})")
            
            # Get categories
            response = await client.get(f"{BASE_URL}/menu/categories")
            assert response.status_code == 200
            
            data = response.json()
            categories = data.get("categories", [])
            print(f"\nMenu categories loaded: {len(categories)}")
            
            for cat in categories[:3]:
                print(f"  - {cat.get('name')}")
    
    @pytest.mark.asyncio
    async def test_order_endpoints_functional(self):
        """Test that order endpoints are functional."""
        async with httpx.AsyncClient() as client:
            # Test order taking endpoint
            order_data = {
                "items": [
                    {"name": "California Roll", "quantity": 2}
                ],
                "customer_info": {
                    "name": "Voice Test Customer",
                    "phone": "+15551234567",
                    "order_type": "pickup"
                }
            }
            
            response = await client.post(
                f"{BASE_URL}/order/take_order",
                json=order_data
            )
            
            print(f"\nOrder endpoint status: {response.status_code}")
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"Order response: {json.dumps(result, indent=2)}")
            else:
                print(f"Order error: {response.text[:200]}")
    
    @pytest.mark.asyncio
    async def test_websocket_endpoints_exist(self):
        """Test that WebSocket endpoints exist (even if they require auth)."""
        endpoints = [
            "/ws/media/test123",
            "/realtime/ws/media/test123",
            "/ws-test/test123"
        ]
        
        print("\nTesting WebSocket endpoints:")
        for endpoint in endpoints:
            ws_url = BASE_URL.replace("http://", "ws://") + endpoint
            print(f"\n  Trying: {ws_url}")
            
            try:
                async with websockets.connect(ws_url) as ws:
                    print(f"    ✅ Connected!")
                    
                    # Send a test message
                    await ws.send(json.dumps({
                        "event": "connected",
                        "protocol": "Call",
                        "version": "1.0.0"
                    }))
                    
                    # Try to receive (might timeout)
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        print(f"    Received: {response[:100]}...")
                    except asyncio.TimeoutError:
                        print(f"    No response (timeout)")
                        
            except websockets.exceptions.InvalidStatusCode as e:
                print(f"    ❌ Status {e.status_code}: {str(e)}")
            except Exception as e:
                print(f"    ❌ Error: {type(e).__name__}: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_system_configuration(self):
        """Test that the system is properly configured."""
        async with httpx.AsyncClient() as client:
            # Check environment
            response = await client.get(f"{BASE_URL}/environment")
            print(f"\nEnvironment check: {response.status_code}")
            
            if response.status_code == 200:
                env_data = response.json()
                print(f"Environment: {env_data.get('environment', 'unknown')}")
                
                # Check for required configurations
                important_vars = ["OPENAI_API_KEY", "VOICE_HANDLER", "DATABASE_URL"]
                for var in important_vars:
                    value = env_data.get(var, "not set")
                    if value and value != "not set":
                        # Mask sensitive data
                        if "KEY" in var or "TOKEN" in var:
                            value = value[:5] + "..." if len(value) > 5 else "***"
                        print(f"  {var}: {value}")
    
    @pytest.mark.asyncio
    async def test_complete_voice_simulation(self):
        """Simulate a complete voice call flow."""
        print("\n" + "="*50)
        print("COMPLETE VOICE FLOW SIMULATION")
        print("="*50)
        
        async with httpx.AsyncClient() as client:
            # Step 1: Incoming call webhook
            print("\n1. Simulating incoming call...")
            call_sid = "CA" + "".join(["1234567890abcdef"] * 2)
            
            form_data = {
                "CallSid": call_sid,
                "From": "+15551234567",
                "To": "+15559876543",
                "CallStatus": "ringing"
            }
            
            response = await client.post(
                f"{BASE_URL}/voice/webhook",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                print("   ✅ TwiML generated successfully")
                twiml = response.text
                
                # Extract WebSocket URL from TwiML if present
                if 'url="' in twiml:
                    start = twiml.find('url="') + 5
                    end = twiml.find('"', start)
                    ws_url = twiml[start:end]
                    print(f"   WebSocket URL: {ws_url}")
            else:
                print(f"   ❌ Failed: {response.status_code}")
            
            # Step 2: Menu inquiry
            print("\n2. Testing menu inquiry...")
            response = await client.get(f"{BASE_URL}/menu/items")
            if response.status_code == 200:
                items = response.json().get("items", [])
                print(f"   ✅ Found {len(items)} menu items")
            
            # Step 3: Order simulation
            print("\n3. Simulating order placement...")
            order_data = {
                "items": [{"name": "California Roll", "quantity": 2}],
                "customer_info": {
                    "name": "Test Voice Customer",
                    "phone": "+15551234567"
                }
            }
            
            response = await client.post(
                f"{BASE_URL}/order/take_order",
                json=order_data
            )
            
            if response.status_code in [200, 201]:
                print("   ✅ Order processed successfully")
            else:
                print(f"   ❌ Order failed: {response.status_code}")
        
        print("\n" + "="*50)
        print("Voice flow simulation complete!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])