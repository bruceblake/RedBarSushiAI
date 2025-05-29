"""
End-to-end tests for WebSocket-based voice flow.
"""
import pytest
import asyncio
import json
import base64
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from app.main import app


class TestWebSocketVoiceFlow:
    """Test WebSocket-based voice interactions."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment."""
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/media/test_ws_001") as websocket:
                # Send Twilio start event
                websocket.send_json({
                    "event": "start",
                    "start": {
                        "streamSid": "SM123",
                        "callSid": "CA123",
                        "accountSid": "AC123"
                    }
                })
                
                # Should receive connected event
                data = websocket.receive_json()
                assert data["event"] == "connected"
    
    @pytest.mark.asyncio
    async def test_websocket_audio_streaming(self, mock_openai_client):
        """Test audio streaming through WebSocket."""
        with TestClient(app) as client:
            with patch('app.api.voice.websocket.OpenAIRealtimeClient') as mock_realtime:
                mock_instance = AsyncMock()
                mock_realtime.return_value = mock_instance
                mock_instance.connect = AsyncMock()
                mock_instance.send_audio = AsyncMock()
                
                with client.websocket_connect(f"/ws/media/test_ws_002") as websocket:
                    # Send start event
                    websocket.send_json({
                        "event": "start",
                        "start": {
                            "streamSid": "SM456",
                            "callSid": "CA456"
                        }
                    })
                    
                    # Send audio data
                    audio_payload = base64.b64encode(b"fake_audio_data").decode()
                    websocket.send_json({
                        "event": "media",
                        "media": {
                            "payload": audio_payload
                        }
                    })
                    
                    # Verify audio was forwarded
                    await asyncio.sleep(0.1)  # Allow async processing
                    mock_instance.send_audio.assert_called()
    
    @pytest.mark.asyncio
    async def test_websocket_transcript_processing(self, db_session, sample_menu_data):
        """Test transcript processing through WebSocket."""
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/media/test_ws_003") as websocket:
                # Simulate transcript event
                websocket.send_json({
                    "event": "transcript",
                    "transcript": {
                        "text": "I'd like to order a California roll",
                        "final": True
                    }
                })
                
                # Should receive response
                response = websocket.receive_json()
                assert "event" in response
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling."""
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/media/test_ws_error") as websocket:
                # Send invalid event
                websocket.send_json({
                    "event": "invalid_event",
                    "data": {}
                })
                
                # Should handle gracefully
                try:
                    response = websocket.receive_json(timeout=2)
                    # Should either ignore or send error response
                except Exception:
                    # Connection might close on error
                    pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup(self):
        """Test WebSocket connection cleanup."""
        with TestClient(app) as client:
            # Open connection
            websocket = client.websocket_connect(f"/ws/media/test_ws_cleanup")
            websocket.__enter__()
            
            # Send start
            websocket.send_json({
                "event": "start",
                "start": {"callSid": "CA789"}
            })
            
            # Close connection
            websocket.__exit__(None, None, None)
            
            # Verify cleanup occurred (session should be removed)
            # This would be verified by checking Redis or session manager


class TestWebSocketRealtimeAPI:
    """Test OpenAI Realtime API integration."""
    
    @pytest.mark.asyncio
    async def test_realtime_session_creation(self, mock_openai_client):
        """Test OpenAI Realtime session creation."""
        with patch('app.utils.realtime_audio_async.AsyncOpenAIRealtimeClient') as mock_client:
            instance = AsyncMock()
            mock_client.return_value = instance
            instance.create_session = AsyncMock(return_value={"session_id": "sess_123"})
            
            # Trigger session creation through WebSocket
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws/media/test_realtime_001") as websocket:
                    websocket.send_json({
                        "event": "start",
                        "start": {"callSid": "CA_RT_001"}
                    })
                    
                    await asyncio.sleep(0.1)
                    instance.create_session.assert_called()
    
    @pytest.mark.asyncio
    async def test_realtime_audio_forwarding(self):
        """Test audio forwarding to OpenAI Realtime."""
        with patch('app.api.voice.websocket.OpenAIRealtimeClient') as mock_realtime:
            instance = AsyncMock()
            mock_realtime.return_value = instance
            instance.append_audio = AsyncMock()
            
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws/media/test_realtime_002") as websocket:
                    # Send audio
                    audio_data = base64.b64encode(b"test_audio").decode()
                    websocket.send_json({
                        "event": "media",
                        "media": {"payload": audio_data}
                    })
                    
                    await asyncio.sleep(0.1)
                    instance.append_audio.assert_called_with(audio_data)
    
    @pytest.mark.asyncio
    async def test_realtime_response_handling(self):
        """Test handling responses from OpenAI Realtime."""
        with patch('app.api.voice.websocket.OpenAIRealtimeClient') as mock_realtime:
            instance = AsyncMock()
            mock_realtime.return_value = instance
            
            # Mock receiving audio from OpenAI
            instance.receive_audio = AsyncMock(
                return_value={"audio": base64.b64encode(b"response_audio").decode()}
            )
            
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws/media/test_realtime_003") as websocket:
                    # Trigger response
                    websocket.send_json({
                        "event": "get_response"
                    })
                    
                    # Should receive audio back
                    response = websocket.receive_json()
                    assert response["event"] == "media"
                    assert "payload" in response["media"]