"""
Integration tests for the Media Streams WebSocket handler.

Tests the MediaStreamHandler class with mock Twilio Media Stream events,
including barge-in functionality and the complete conversational loop.
"""

import json
import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from app.voice_gateway import MediaStreamHandler
from app.services.stt_service import MockSTTStream
from app.agent_orchestrator import MockAgentOrchestrator


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.receive_queue = asyncio.Queue()
        
    async def send_text(self, data: str):
        """Store sent messages for verification."""
        self.sent_messages.append(json.loads(data))
        
    async def receive_text(self):
        """Return queued messages."""
        return await self.receive_queue.get()
        
    async def queue_message(self, message: dict):
        """Add a message to the receive queue."""
        await self.receive_queue.put(json.dumps(message))


@pytest.mark.asyncio
async def test_media_stream_handler_greeting():
    """Test that handler sends greeting on start event."""
    # Create mock WebSocket
    ws = MockWebSocket()
    
    # Create handler
    handler = MediaStreamHandler(
        websocket=ws,
        call_sid="test-call-123",
        stt_service=None,
        tts_service=None,
        orchestrator=None
    )
    
    # Queue messages
    await ws.queue_message({"event": "connected", "protocol": "Call", "version": "1.0.0"})
    await ws.queue_message({
        "event": "start",
        "streamSid": "MZ123456",
        "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
    })
    await ws.queue_message({"event": "stop"})
    
    # Run handler
    await handler.run()
    
    # Verify greeting was sent
    media_messages = [msg for msg in ws.sent_messages if msg["event"] == "media"]
    mark_messages = [msg for msg in ws.sent_messages if msg["event"] == "mark"]
    
    assert len(media_messages) > 0, "Should send at least one media message for greeting"
    assert len(mark_messages) == 1, "Should send exactly one mark message"
    assert "greeting_finished" in mark_messages[0]["mark"]["name"]


@pytest.mark.asyncio
async def test_media_stream_handler_barge_in():
    """Test that user speech interrupts TTS playback."""
    # Create mock WebSocket
    ws = MockWebSocket()
    
    # Create handler
    handler = MediaStreamHandler(
        websocket=ws,
        call_sid="test-call-456",
        stt_service=None,
        tts_service=None,
        orchestrator=None
    )
    
    # Flag to track if TTS was interrupted
    tts_interrupted = False
    
    # Custom run method to simulate barge-in
    async def run_with_interruption():
        # Start the handler in a task
        handler_task = asyncio.create_task(handler.run())
        
        # Send initial messages
        await ws.queue_message({"event": "connected"})
        await ws.queue_message({
            "event": "start",
            "streamSid": "MZ789",
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
        })
        
        # Wait for TTS to start
        await asyncio.sleep(0.1)
        
        # Simulate user speaking during TTS (barge-in)
        silence_audio = base64.b64encode(bytes([0x7F] * 160)).decode('utf-8')
        await ws.queue_message({
            "event": "media",
            "streamSid": "MZ789",
            "media": {"payload": silence_audio}
        })
        
        # Check if TTS task was cancelled
        await asyncio.sleep(0.1)
        if handler.current_tts_task and handler.current_tts_task.cancelled():
            nonlocal tts_interrupted
            tts_interrupted = True
        
        # Stop the stream
        await ws.queue_message({"event": "stop"})
        
        # Wait for handler to complete
        await handler_task
    
    await run_with_interruption()
    
    # Verify interruption occurred
    assert tts_interrupted or not handler.is_tts_active, "TTS should be interrupted or inactive"
    
    # Check that we didn't send all TTS chunks
    media_messages = [msg for msg in ws.sent_messages if msg["event"] == "media"]
    # With interruption, we should have fewer media messages than a full greeting
    assert len(media_messages) < 10, "Should have fewer media messages due to interruption"


@pytest.mark.asyncio
async def test_media_stream_handler_streamid_usage():
    """Test that streamSid is properly stored and used."""
    ws = MockWebSocket()
    
    handler = MediaStreamHandler(
        websocket=ws,
        call_sid="test-call-789",
        stt_service=None,
        tts_service=None,
        orchestrator=None
    )
    
    test_stream_sid = "MZ-TEST-STREAM-ID"
    
    # Queue messages
    await ws.queue_message({"event": "connected"})
    await ws.queue_message({
        "event": "start",
        "streamSid": test_stream_sid,
        "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
    })
    await ws.queue_message({"event": "stop"})
    
    # Run handler
    await handler.run()
    
    # Verify all media and mark messages use the correct streamSid
    for msg in ws.sent_messages:
        if msg["event"] in ["media", "mark"]:
            assert msg["streamSid"] == test_stream_sid, f"Message should use streamSid {test_stream_sid}"


@pytest.mark.asyncio
async def test_complete_conversational_loop():
    """Test the complete conversational loop: User speaks -> STT -> Orchestrator -> TTS."""
    ws = MockWebSocket()
    
    # Create mock services
    stt_service = MockSTTStream("test-conv-123")
    orchestrator = MockAgentOrchestrator()
    
    # Create handler with dependencies
    handler = MediaStreamHandler(
        websocket=ws,
        call_sid="test-conv-123",
        stt_service=stt_service,
        tts_service=None,  # Using built-in mock
        orchestrator=orchestrator
    )
    
    # Start the handler
    handler_task = asyncio.create_task(handler.run())
    
    # Send initial connection
    await ws.queue_message({"event": "connected"})
    
    # Send start event
    await ws.queue_message({
        "event": "start",
        "streamSid": "MZ-CONV-TEST",
        "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
    })
    
    # Wait for greeting to start
    await asyncio.sleep(0.2)
    
    # Simulate user speaking (send 3 audio chunks to trigger final transcript)
    user_audio = base64.b64encode(bytes([0x7F] * 160)).decode('utf-8')
    for i in range(3):
        await ws.queue_message({
            "event": "media",
            "streamSid": "MZ-CONV-TEST",
            "media": {"payload": user_audio}
        })
        await asyncio.sleep(0.05)
    
    # Wait for processing
    await asyncio.sleep(0.3)
    
    # Stop the stream
    await ws.queue_message({"event": "stop"})
    await handler_task
    
    # Verify the flow
    sent_events = [msg["event"] for msg in ws.sent_messages]
    
    # Should have greeting TTS and response TTS
    media_events = [msg for msg in ws.sent_messages if msg["event"] == "media"]
    mark_events = [msg for msg in ws.sent_messages if msg["event"] == "mark"]
    
    # At least greeting and one response
    assert len(mark_events) >= 2, "Should have marks for greeting and response"
    
    # Check mark names
    mark_names = [msg["mark"]["name"] for msg in mark_events]
    assert any("greeting" in name for name in mark_names), "Should have greeting mark"
    assert any("response" in name or "fallback" in name for name in mark_names), "Should have response mark"
    
    # Verify orchestrator was called
    assert "test-conv-123" in orchestrator.active_conversations or "test-conv-123" in orchestrator.conversation_history


@pytest.mark.asyncio
async def test_stt_orchestrator_integration():
    """Test that STT results are properly sent to orchestrator."""
    ws = MockWebSocket()
    
    # Create mocks with spying capability
    stt_service = MockSTTStream("test-stt-orch")
    orchestrator = MockAgentOrchestrator()
    
    # Spy on orchestrator.handle_input
    original_handle_input = orchestrator.handle_input
    handle_input_calls = []
    
    async def spy_handle_input(call_sid, transcript):
        handle_input_calls.append((call_sid, transcript))
        return await original_handle_input(call_sid, transcript)
    
    orchestrator.handle_input = spy_handle_input
    
    # Create handler
    handler = MediaStreamHandler(
        websocket=ws,
        call_sid="test-stt-orch",
        stt_service=stt_service,
        orchestrator=orchestrator
    )
    
    # Run test
    handler_task = asyncio.create_task(handler.run())
    
    await ws.queue_message({"event": "connected"})
    await ws.queue_message({
        "event": "start",
        "streamSid": "MZ-STT-ORCH",
        "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
    })
    
    # Send enough audio to trigger final transcript
    for i in range(4):
        await ws.queue_message({
            "event": "media",
            "streamSid": "MZ-STT-ORCH",
            "media": {"payload": base64.b64encode(bytes([0x7F] * 2000)).decode('utf-8')}
        })
    
    await asyncio.sleep(0.2)
    await ws.queue_message({"event": "stop"})
    await handler_task
    
    # Verify orchestrator was called with transcript
    assert len(handle_input_calls) > 0, "Orchestrator should have been called"
    call_sid, transcript = handle_input_calls[0]
    assert call_sid == "test-stt-orch"
    assert transcript in ["hello I'd like to order", "hello I'd like to order some", "hello I'd like to order some sushi"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])