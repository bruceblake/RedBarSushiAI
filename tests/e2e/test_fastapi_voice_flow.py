"""
E2E tests for FastAPI voice flow implementation.
Tests the complete voice ordering flow with WebSockets and realtime audio.
"""

import pytest
import asyncio
import json
import base64
import logging
from unittest.mock import patch, AsyncMock, MagicMock
import websockets
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


class TestFastAPIVoiceFlow:
    """Test the complete FastAPI voice flow."""
    
    def test_health_endpoint(self, client: TestClient):
        """Test the health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
    
    def test_routes_debug_endpoint(self, client: TestClient):
        """Test the routes debug endpoint."""
        response = client.get("/routes-debug")
        assert response.status_code == 200
        data = response.json()
        assert "http_routes" in data
        assert "websocket_routes" in data
        
        # Check that voice routes exist
        http_routes = [r["path"] for r in data["http_routes"]]
        assert "/voice/" in http_routes or "/voice" in http_routes
        
        # Check that WebSocket route exists
        ws_routes = [r["path"] for r in data["websocket_routes"]]
        assert any("/ws/media" in path for path in ws_routes)
    
    def test_voice_webhook_endpoint(self, client: TestClient, sample_twilio_request):
        """Test the voice webhook endpoint returns proper TwiML."""
        response = client.post("/voice/", data=sample_twilio_request)
        
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        
        # Check TwiML content
        twiml = response.text
        assert "<?xml version" in twiml
        assert "<Response>" in twiml
        assert "<Connect>" in twiml
        assert "<Stream" in twiml
        assert 'url="wss://' in twiml or 'url="ws://' in twiml
        assert f"/realtime/ws/media/{sample_twilio_request['CallSid']}" in twiml
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, app):
        """Test WebSocket connection and basic message flow."""
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            call_sid = "test-call-123"
            
            # Test WebSocket connection
            with client.websocket_connect(f"/realtime/ws/media/{call_sid}") as websocket:
                # Send connected event
                connected_msg = {
                    "event": "connected",
                    "protocol": "Call",
                    "version": "1.0.0"
                }
                websocket.send_json(connected_msg)
                
                # Send start event
                start_msg = {
                    "event": "start",
                    "streamSid": "MZtest123",
                    "start": {
                        "streamSid": "MZtest123",
                        "callSid": call_sid,
                        "tracks": ["inbound_track"],
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1
                        }
                    }
                }
                websocket.send_json(start_msg)
                
                # Send a media event with audio
                media_msg = {
                    "event": "media",
                    "streamSid": "MZtest123",
                    "media": {
                        "track": "inbound_track",
                        "chunk": "0",
                        "timestamp": "0",
                        "payload": base64.b64encode(b'\xff' * 160).decode()  # 20ms of silence
                    }
                }
                websocket.send_json(media_msg)
                
                # Allow some processing time
                await asyncio.sleep(0.1)
                
                # Send stop event
                stop_msg = {
                    "event": "stop",
                    "streamSid": "MZtest123"
                }
                websocket.send_json(stop_msg)
    
    @pytest.mark.asyncio
    @patch('app.utils.realtime_audio_async.AsyncRealtimeAudioClient')
    async def test_voice_flow_with_mock_openai(self, mock_realtime_client, app):
        """Test the voice flow with mocked OpenAI Realtime API."""
        # Mock the OpenAI client
        mock_client_instance = AsyncMock()
        mock_realtime_client.return_value = mock_client_instance
        
        # Mock OpenAI responses
        mock_client_instance.connect = AsyncMock()
        mock_client_instance.disconnect = AsyncMock()
        mock_client_instance.send_audio = AsyncMock()
        mock_client_instance.process_audio = AsyncMock(return_value={
            "type": "response.audio.delta",
            "audio": base64.b64encode(b'\xff' * 320).decode()  # Mock audio response
        })
        
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            call_sid = "test-call-456"
            
            with client.websocket_connect(f"/realtime/ws/media/{call_sid}") as websocket:
                # Send start event
                start_msg = {
                    "event": "start",
                    "streamSid": "MZtest456",
                    "start": {
                        "streamSid": "MZtest456",
                        "callSid": call_sid,
                        "tracks": ["inbound_track"]
                    }
                }
                websocket.send_json(start_msg)
                
                # Verify OpenAI client was initialized
                await asyncio.sleep(0.1)
                mock_client_instance.connect.assert_called()
    
    def test_menu_endpoints(self, client: TestClient):
        """Test menu-related endpoints."""
        # Test menu search
        response = client.get("/menu/search?query=sushi")
        assert response.status_code == 200
        
        # Test menu categories
        response = client.get("/menu/categories")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_agent_orchestration(self):
        """Test that agent orchestration initializes properly."""
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        
        # Initialize the orchestrator
        await async_agent_orchestrator.initialize()
        
        # Test starting a conversation
        result = await async_agent_orchestrator.start_new_conversation(
            "test-session-123",
            {"source": "test"}
        )
        
        assert result is not None
        assert "text" in result
    
    @pytest.mark.asyncio
    async def test_fsm_transitions(self):
        """Test FSM state transitions."""
        from app.utils.fsm_async import async_fsm_manager, ConversationState, ConversationEvent
        
        # Create FSM instance
        fsm = await async_fsm_manager.create_fsm("test-fsm-123")
        
        # Test initial state
        assert fsm.current_state == ConversationState.INITIAL
        
        # Test greeting transition
        await fsm.trigger_event(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
        
        # Test transition to main menu
        await fsm.trigger_event(ConversationEvent.GREETING_COMPLETE)
        assert fsm.current_state == ConversationState.MAIN_MENU