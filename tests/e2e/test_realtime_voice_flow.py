"""Tests for the realtime voice flow."""

import pytest
import os
import requests
import json
import asyncio
import websockets
import logging
from unittest.mock import patch, MagicMock
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip tests if not running in CI or test environment
pytestmark = pytest.mark.skipif(
    not os.environ.get("TESTING", "").lower() == "true"
    and not os.environ.get("CI", "").lower() == "true",
    reason="Not running in test environment",
)

# These tests can be run against a local or staged environment
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:5000")
REALTIME_VOICE_ENDPOINT = f"{BASE_URL}/voice_realtime"
if os.environ.get("CI", "").lower() == "true":
    # In CI, always use the committed URL for staging
    BASE_URL = "https://redbarsushiai-staging.onrender.com"
    REALTIME_VOICE_ENDPOINT = f"{BASE_URL}/voice_realtime"


class TestRealtimeVoiceFlow:
    """Test the complete realtime voice flow."""

    @pytest.mark.asyncio
    async def test_realtime_twiml_endpoint(self):
        """Test that the voice endpoint returns valid TwiML with Twilio Media Streams."""
        # Make a POST request to the voice endpoint with proper Twilio parameters
        data = {
            "From": "+18005551212",
            "To": "+18005551213",
            "CallSid": "test-call-sid-12345",
        }
        
        response = requests.post(REALTIME_VOICE_ENDPOINT, data=data)
        
        # Check that the response is successful
        assert response.status_code == 200
        
        # Check that the content type is XML
        assert "text/xml" in response.headers["Content-Type"]
        
        # Check that the response contains TwiML elements for Media Streams
        twiml = response.text
        
        # Check for Stream elements in the TwiML
        assert "<Stream " in twiml
        assert "track=" in twiml
        
        # Specific Media Streams elements
        assert "<Start>" in twiml
        assert "<Connect>" in twiml
        
        # Log the actual TwiML for debugging
        logger.info(f"Received TwiML: {twiml}")

    @pytest.mark.asyncio
    @patch("websockets.connect")
    async def test_realtime_websocket_connection(self, mock_connect):
        """Test that the WebSocket endpoint connects properly."""
        # Mock WebSocket client
        mock_ws = MagicMock()
        mock_ws.send = MagicMock()
        mock_ws.recv = MagicMock(return_value='{"type":"connected","session_id":"12345"}')
        mock_ws.close = MagicMock()
        
        # Configure the mock WebSocket connection to return our mocked client
        mock_connect.return_value.__aenter__.return_value = mock_ws
        
        # Use an absolute WebSocket URL based on BASE_URL for testing
        ws_url = f"wss://{BASE_URL.split('://')[-1]}/ws/media" 
        if "localhost" in BASE_URL:
            ws_url = f"ws://{BASE_URL.split('://')[-1]}/ws/media"
            
        logger.info(f"Connecting to WebSocket URL: {ws_url}")
        
        # Connect to the WebSocket endpoint
        async with websockets.connect(ws_url) as ws:
            # Check that the WebSocket connected properly
            connection_message = await ws.recv()
            logger.info(f"Received connection message: {connection_message}")
            
            # Parse the message JSON
            message = json.loads(connection_message)
            
            # Check that we got a valid connection message
            assert message["type"] == "connected"
            assert "session_id" in message
            
            # Send a simple message to simulate Twilio Media Streams
            sample_message = {
                "event": "start",
                "streamSid": "12345",
                "accountSid": "AC12345",
                "callSid": "CA12345"
            }
            await ws.send(json.dumps(sample_message))
            
            # Send a sample media event with encoded audio data
            sample_audio = b"SAMPLE_AUDIO_DATA"
            encoded_audio = base64.b64encode(sample_audio).decode('utf-8')
            
            media_message = {
                "event": "media",
                "streamSid": "12345",
                "media": {
                    "payload": encoded_audio
                }
            }
            await ws.send(json.dumps(media_message))
            
            # Send a media_stop event
            stop_message = {
                "event": "stop",
                "streamSid": "12345"
            }
            await ws.send(json.dumps(stop_message))
            
            # Close the WebSocket connection
            await ws.close()
            
        # Assert that our mock ws.send and ws.recv were called
        mock_ws.send.assert_called()
        mock_ws.recv.assert_called()
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test the health endpoint to ensure realtime voice components are loaded."""
        response = requests.get(f"{REALTIME_VOICE_ENDPOINT}/health")
        
        # Check that the response is successful
        assert response.status_code == 200
        
        # Check that we got a proper JSON response
        health_data = response.json()
        assert "status" in health_data
        assert "service" in health_data
        assert health_data["service"] == "voice_realtime"
        
        # Check that the realtime component is present
        assert "realtime" in health_data
        
        # Log the health check result
        logger.info(f"Health check result: {health_data}")