"""
End-to-end tests with real external services in staging environment.
These tests ONLY run when FASTAPI_ENV=staging and require real API credentials.
"""

import pytest
import os
import asyncio
import json
from datetime import datetime
from twilio.rest import Client as TwilioClient
from openai import AsyncOpenAI
import httpx


@pytest.mark.skipif(
    os.getenv("FASTAPI_ENV") != "staging",
    reason="Real service tests only run in staging environment"
)
class TestStagingRealServices:
    """Test with real external services in staging."""
    
    @pytest.fixture
    def staging_config(self):
        """Verify staging configuration is complete."""
        required_vars = [
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_TEST_PHONE_NUMBER",
            "OPENAI_API_KEY",
            "DELIVERECT_API_KEY",
            "DELIVERECT_SANDBOX_URL"
        ]
        
        for var in required_vars:
            if not os.getenv(var):
                pytest.skip(f"Missing required staging variable: {var}")
        
        return {
            "twilio_sid": os.getenv("TWILIO_ACCOUNT_SID"),
            "twilio_auth": os.getenv("TWILIO_AUTH_TOKEN"),
            "twilio_test_number": os.getenv("TWILIO_TEST_PHONE_NUMBER"),
            "openai_key": os.getenv("OPENAI_API_KEY"),
            "deliverect_key": os.getenv("DELIVERECT_API_KEY"),
            "deliverect_url": os.getenv("DELIVERECT_SANDBOX_URL"),
            "app_base_url": os.getenv("STAGING_APP_URL", "https://redbarsushi-staging.onrender.com")
        }
    
    @pytest.fixture
    def twilio_client(self, staging_config):
        """Create real Twilio client."""
        return TwilioClient(
            staging_config["twilio_sid"],
            staging_config["twilio_auth"]
        )
    
    @pytest.fixture
    async def openai_client(self, staging_config):
        """Create real OpenAI client."""
        return AsyncOpenAI(api_key=staging_config["openai_key"])
    
    @pytest.mark.asyncio
    async def test_twilio_webhook_integration(self, staging_config, twilio_client):
        """Test real Twilio webhook with test credentials."""
        # Create a test call using Twilio's test numbers
        # From: +15005550006 (valid test number)
        # To: Our staging app's Twilio number
        
        test_webhook_url = f"{staging_config['app_base_url']}/api/conversation-relay"
        
        # Make test API call to verify webhook is accessible
        async with httpx.AsyncClient() as client:
            # Send test webhook payload
            test_payload = {
                "CallSid": f"CA_TEST_{datetime.utcnow().timestamp()}",
                "From": "+15005550006",  # Twilio test number
                "To": staging_config["twilio_test_number"],
                "CallStatus": "ringing"
            }
            
            response = await client.post(
                test_webhook_url,
                data=test_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            assert response.status_code == 200
            assert "TwiML" in response.text or "Response" in response.text
    
    @pytest.mark.asyncio
    async def test_openai_realtime_connection(self, staging_config):
        """Test connecting to OpenAI Realtime API."""
        import websockets
        import base64
        
        # OpenAI Realtime WebSocket URL
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        headers = {
            "Authorization": f"Bearer {staging_config['openai_key']}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        try:
            async with websockets.connect(url, extra_headers=headers) as ws:
                # Send session update
                session_update = {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text", "audio"],
                        "instructions": "You are a test assistant.",
                        "voice": "shimmer",
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16",
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500
                        }
                    }
                }
                
                await ws.send(json.dumps(session_update))
                
                # Wait for session.created event
                response = await ws.recv()
                data = json.loads(response)
                
                assert data["type"] == "session.created"
                assert "session" in data
                
                # Test sending audio
                test_audio = base64.b64encode(b"\x00" * 320).decode()  # 20ms of silence
                audio_event = {
                    "type": "input_audio_buffer.append",
                    "audio": test_audio
                }
                
                await ws.send(json.dumps(audio_event))
                
                # Close connection
                await ws.close()
                
        except Exception as e:
            pytest.fail(f"Failed to connect to OpenAI Realtime API: {e}")
    
    @pytest.mark.asyncio
    async def test_openai_intent_detection(self, openai_client):
        """Test real OpenAI API for intent detection."""
        # Test with cheaper model in staging
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are analyzing restaurant order intents. Respond with: ORDER, MENU_INQUIRY, or OTHER"
                },
                {
                    "role": "user",
                    "content": "I'd like to order two California rolls please"
                }
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        intent = response.choices[0].message.content.strip()
        assert intent == "ORDER"
    
    @pytest.mark.asyncio
    async def test_deliverect_sandbox_connection(self, staging_config):
        """Test connection to Deliverect sandbox."""
        async with httpx.AsyncClient() as client:
            # Test authentication endpoint
            response = await client.get(
                f"{staging_config['deliverect_url']}/locations",
                headers={
                    "Authorization": f"Bearer {staging_config['deliverect_key']}",
                    "Content-Type": "application/json"
                }
            )
            
            # Should get 200 or 401 (not 404 or network error)
            assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_voice_flow_with_real_services(self, staging_config):
        """Test complete voice ordering flow with real services."""
        call_sid = f"STAGING_E2E_TEST_{datetime.utcnow().timestamp()}"
        
        async with httpx.AsyncClient() as client:
            # 1. Simulate incoming call webhook
            webhook_response = await client.post(
                f"{staging_config['app_base_url']}/api/conversation-relay",
                data={
                    "CallSid": call_sid,
                    "From": "+15005550006",
                    "To": staging_config["twilio_test_number"],
                    "CallStatus": "in-progress"
                }
            )
            
            assert webhook_response.status_code == 200
            
            # 2. Simulate conversation through API endpoints
            # Start conversation
            start_response = await client.post(
                f"{staging_config['app_base_url']}/api/voice/test/process",
                json={
                    "call_sid": call_sid,
                    "transcript": "My name is Test User",
                    "state": "GREETING"
                }
            )
            
            assert start_response.status_code == 200
            data = start_response.json()
            assert data["state"] == "MAIN_MENU"
            
            # 3. Place order
            order_response = await client.post(
                f"{staging_config['app_base_url']}/api/voice/test/process",
                json={
                    "call_sid": call_sid,
                    "transcript": "I'd like to order a California roll",
                    "state": "MAIN_MENU"
                }
            )
            
            assert order_response.status_code == 200
            assert "California" in order_response.json()["text"]
    
    @pytest.mark.asyncio
    async def test_menu_data_availability(self, staging_config):
        """Test that menu data is properly loaded in staging."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{staging_config['app_base_url']}/api/menu/items"
            )
            
            assert response.status_code == 200
            items = response.json()
            assert len(items) > 0
            
            # Verify essential items exist
            item_names = [item["name"] for item in items]
            assert any("California" in name for name in item_names)
    
    @pytest.mark.asyncio
    async def test_fsm_state_persistence(self, staging_config):
        """Test FSM state persists across requests."""
        call_sid = f"FSM_TEST_{datetime.utcnow().timestamp()}"
        
        async with httpx.AsyncClient() as client:
            # Create FSM instance
            response1 = await client.post(
                f"{staging_config['app_base_url']}/api/voice/test/fsm/create",
                json={"call_sid": call_sid}
            )
            assert response1.status_code == 200
            
            # Update state
            response2 = await client.post(
                f"{staging_config['app_base_url']}/api/voice/test/fsm/transition",
                json={
                    "call_sid": call_sid,
                    "event": "START_ORDER"
                }
            )
            assert response2.status_code == 200
            
            # Verify state persisted
            response3 = await client.get(
                f"{staging_config['app_base_url']}/api/voice/test/fsm/{call_sid}"
            )
            assert response3.status_code == 200
            state_data = response3.json()
            assert state_data["current_state"] == "ORDERING"
    
    @pytest.mark.asyncio
    async def test_error_recovery_with_real_services(self, staging_config, openai_client):
        """Test system recovers from API errors gracefully."""
        # Test with invalid API key
        bad_client = AsyncOpenAI(api_key="sk-invalid-key")
        
        with pytest.raises(Exception) as exc_info:
            await bad_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}]
            )
        
        # Should get auth error, not crash
        assert "authentication" in str(exc_info.value).lower() or "api" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_calls_handling(self, staging_config):
        """Test system handles multiple concurrent calls."""
        call_sids = [f"CONCURRENT_{i}_{datetime.utcnow().timestamp()}" for i in range(5)]
        
        async with httpx.AsyncClient() as client:
            # Create multiple concurrent requests
            tasks = []
            for call_sid in call_sids:
                task = client.post(
                    f"{staging_config['app_base_url']}/api/voice/test/process",
                    json={
                        "call_sid": call_sid,
                        "transcript": "Hello, my name is Test",
                        "state": "GREETING"
                    }
                )
                tasks.append(task)
            
            # Execute concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            assert success_count >= 4  # At least 80% success rate
    
    @pytest.mark.asyncio
    async def test_deliverect_order_submission_sandbox(self, staging_config):
        """Test submitting order to Deliverect sandbox."""
        # This test requires proper Deliverect sandbox setup
        test_order = {
            "channelOrderId": f"TEST_{datetime.utcnow().timestamp()}",
            "orderType": 1,  # Pickup
            "customer": {
                "name": "Staging Test",
                "phone": "+15005550006",
                "email": "test@staging.com"
            },
            "items": [
                {
                    "plu": "TEST_ITEM_001",
                    "name": "Test Item",
                    "quantity": 1,
                    "price": 1000
                }
            ],
            "payment": {
                "type": 1  # Cash
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{staging_config['deliverect_url']}/orders",
                json=test_order,
                headers={
                    "Authorization": f"Bearer {staging_config['deliverect_key']}",
                    "Content-Type": "application/json"
                }
            )
            
            # Sandbox might accept or reject - just verify we can connect
            assert response.status_code in [200, 201, 400, 401, 422]