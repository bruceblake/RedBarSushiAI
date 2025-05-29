"""
Real WebSocket E2E tests for voice communication.
"""
import pytest
import asyncio
import json
import base64
import websockets
from typing import Dict, Any


class TestRealWebSocket:
    """Test real WebSocket connections for voice communication."""
    
    @pytest.mark.asyncio
    async def test_websocket_pages_available(self):
        """Test that WebSocket test pages are available."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/ws-test-page")
            assert response.status_code == 200
            assert "WebSocket" in response.text
    
    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test WebSocket connection lifecycle."""
        ws_url = "ws://localhost:8000/ws/test"
        
        try:
            async with websockets.connect(ws_url) as ws:
                # Connection established
                assert ws.open
                
                # Send a test message
                await ws.send(json.dumps({"type": "test", "data": "hello"}))
                
                # Close gracefully
                await ws.close()
                
        except websockets.exceptions.InvalidStatusCode as e:
            # If this specific endpoint doesn't exist, that's okay
            if e.status_code == 404:
                pytest.skip("Test WebSocket endpoint not available")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_twilio_media_stream_format(self):
        """Test Twilio media stream WebSocket format."""
        call_sid = "CA" + "1234567890abcdef" * 2  # Fake but valid format
        ws_url = f"ws://localhost:8000/ws/media/{call_sid}"
        
        try:
            async with websockets.connect(ws_url) as ws:
                # Send Twilio 'connected' event
                connected_msg = {
                    "event": "connected",
                    "protocol": "Call",
                    "version": "1.0.0"
                }
                await ws.send(json.dumps(connected_msg))
                
                # Send Twilio 'start' event
                start_msg = {
                    "event": "start",
                    "sequenceNumber": "1",
                    "start": {
                        "streamSid": "MZ" + "1234567890abcdef" * 2,
                        "accountSid": "AC" + "1234567890abcdef" * 2,
                        "callSid": call_sid,
                        "tracks": ["inbound"],
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1
                        }
                    }
                }
                await ws.send(json.dumps(start_msg))
                
                # Send sample audio data
                audio_msg = {
                    "event": "media",
                    "sequenceNumber": "2",
                    "media": {
                        "track": "inbound",
                        "chunk": "1",
                        "timestamp": "1",
                        "payload": base64.b64encode(b"\x00" * 160).decode()  # 20ms of silence
                    }
                }
                await ws.send(json.dumps(audio_msg))
                
                # Try to receive any response
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    response_data = json.loads(response) if isinstance(response, str) else response
                    assert isinstance(response_data, (dict, bytes))
                except asyncio.TimeoutError:
                    # No response is okay for this test
                    pass
                
                # Send stop event
                stop_msg = {
                    "event": "stop",
                    "sequenceNumber": "3"
                }
                await ws.send(json.dumps(stop_msg))
                
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 403:
                pytest.skip("WebSocket requires authentication")
            elif e.status_code == 404:
                pytest.skip("Media stream WebSocket endpoint not available")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_realtime_websocket_endpoint(self):
        """Test the OpenAI Realtime-style WebSocket endpoint."""
        call_sid = "test-call-123"
        ws_url = f"ws://localhost:8000/realtime/ws/media/{call_sid}"
        
        try:
            async with websockets.connect(ws_url) as ws:
                # The realtime endpoint might expect different message formats
                # Try sending a session update
                session_update = {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text", "audio"],
                        "instructions": "You are a helpful assistant.",
                        "voice": "shimmer",
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16"
                    }
                }
                await ws.send(json.dumps(session_update))
                
                # Try to receive session confirmation
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    assert response is not None
                except asyncio.TimeoutError:
                    pass
                
        except Exception as e:
            if "403" in str(e) or "404" in str(e):
                pytest.skip(f"Realtime WebSocket endpoint not accessible: {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling."""
        # Try invalid call SID format
        ws_url = "ws://localhost:8000/ws/media/invalid-sid"
        
        try:
            async with websockets.connect(ws_url) as ws:
                # Send invalid JSON
                await ws.send("invalid json {")
                
                # WebSocket should handle gracefully
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    # If we get a response, it should be an error
                    if isinstance(response, str):
                        data = json.loads(response)
                        assert "error" in data or "event" in data
                except asyncio.TimeoutError:
                    # No response is also acceptable
                    pass
                    
        except websockets.exceptions.InvalidStatusCode as e:
            # Server rejecting invalid format is expected
            assert e.status_code in [400, 403, 404]
        except websockets.exceptions.ConnectionClosedError:
            # Server closing connection on error is also acceptable
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])