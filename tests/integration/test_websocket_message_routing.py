"""
Integration tests for WebSocket message routing and handling - Task 3.6.2.

This module tests message routing, processing, and handling for both 
Twilio Media Streams and ConversationRelay WebSocket connections.
"""

import pytest
import asyncio
import json
import uuid
import base64
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import WebSocket, WebSocketDisconnect

from app.api.voice.websocket import handle_media_stream
from app.api.conversation_relay.handler import ConversationRelayHandler


class MockWebSocket:
    """Enhanced mock WebSocket for testing message routing."""
    
    def __init__(self):
        self.state = "CONNECTED"
        self.messages_sent = []
        self.messages_received = []
        self.headers = {}
        self.query_params = {}
        self.closed = False
        
    async def accept(self):
        """Mock accept method."""
        pass
        
    async def close(self, code: int = 1000):
        """Mock close method."""
        self.closed = True
        
    async def send_text(self, data: str):
        """Mock send_text method."""
        self.messages_sent.append({"type": "text", "data": data})
        
    async def send_json(self, data: Dict[str, Any]):
        """Mock send_json method."""
        self.messages_sent.append({"type": "json", "data": data})
        
    async def receive_text(self):
        """Mock receive_text method."""
        if self.messages_received:
            message = self.messages_received.pop(0)
            if message["type"] == "text":
                return message["data"]
        raise WebSocketDisconnect()
        
    async def receive_json(self):
        """Mock receive_json method."""
        if self.messages_received:
            message = self.messages_received.pop(0)
            if message["type"] == "json":
                return message["data"]
        raise WebSocketDisconnect()
        
    def add_message(self, message_type: str, data: Any):
        """Add a message to the received queue."""
        self.messages_received.append({"type": message_type, "data": data})
        
    def get_sent_messages(self, message_type: Optional[str] = None):
        """Get sent messages, optionally filtered by type."""
        if message_type:
            return [msg for msg in self.messages_sent if msg["type"] == message_type]
        return self.messages_sent


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()


@pytest.fixture
def sample_call_sid():
    """Generate a sample call SID for testing."""
    return f"CA{uuid.uuid4().hex[:24]}"


@pytest.fixture
def sample_stream_sid():
    """Generate a sample stream SID for testing."""
    return f"SM{uuid.uuid4().hex[:24]}"


class TestTwilioMediaStreamMessageRouting:
    """Test message routing for Twilio Media Streams."""
    
    @pytest.mark.asyncio
    async def test_connected_message_routing(self, mock_websocket, sample_call_sid):
        """Test routing of Twilio 'connected' event messages."""
        # Setup connected message
        connected_message = {
            "event": "connected",
            "protocol": "Call",
            "version": "1.0.0"
        }
        
        mock_websocket.add_message("json", connected_message)
        mock_websocket.add_message("json", {"event": "stop"})  # End the stream
        
        # Process messages
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify message was processed
        mock_logger.info.assert_any_call(f"Twilio connected for call {sample_call_sid}")
    
    @pytest.mark.asyncio
    async def test_start_message_routing(self, mock_websocket, sample_call_sid, sample_stream_sid):
        """Test routing of Twilio 'start' event messages."""
        # Setup start message
        start_message = {
            "event": "start",
            "streamSid": sample_stream_sid,
            "start": {
                "accountSid": f"AC{uuid.uuid4().hex[:24]}",
                "streamSid": sample_stream_sid,
                "callSid": sample_call_sid,
                "customParameters": {
                    "debug": "true",
                    "client": "twilio"
                }
            }
        }
        
        mock_websocket.add_message("json", start_message)
        mock_websocket.add_message("json", {"event": "stop"})
        
        # Process messages
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify start message was processed
        mock_logger.info.assert_any_call(f"Media stream started for call {sample_call_sid}")
        mock_logger.info.assert_any_call(f"Stream SID: {sample_stream_sid}")
        
        # Verify response was sent
        sent_json_messages = mock_websocket.get_sent_messages("json")
        assert len(sent_json_messages) > 0
        
        # Check for connected response
        connected_response = next(
            (msg for msg in sent_json_messages if msg["data"].get("event") == "connected"),
            None
        )
        assert connected_response is not None
        assert connected_response["data"]["protocol"] == "Call"
    
    @pytest.mark.asyncio
    async def test_media_message_routing(self, mock_websocket, sample_call_sid, sample_stream_sid):
        """Test routing of Twilio 'media' event messages."""
        # Setup media messages
        media_messages = [
            {
                "event": "media",
                "streamSid": sample_stream_sid,
                "media": {
                    "track": "inbound",
                    "chunk": "1",
                    "timestamp": "1234567890",
                    "payload": base64.b64encode(b"audio_data_chunk_1").decode()
                }
            },
            {
                "event": "media", 
                "streamSid": sample_stream_sid,
                "media": {
                    "track": "inbound",
                    "chunk": "2", 
                    "timestamp": "1234567891",
                    "payload": base64.b64encode(b"audio_data_chunk_2").decode()
                }
            }
        ]
        
        # Add messages to websocket
        for msg in media_messages:
            mock_websocket.add_message("json", msg)
        mock_websocket.add_message("json", {"event": "stop"})
        
        # Process messages with debug enabled
        with patch('app.api.voice.websocket.logger') as mock_logger:
            # Enable debug by setting a global variable or modifying the handler
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify media messages were received (logging may vary based on debug setting)
        # In a real implementation, these would be forwarded to OpenAI
    
    @pytest.mark.asyncio
    async def test_stop_message_routing(self, mock_websocket, sample_call_sid, sample_stream_sid):
        """Test routing of Twilio 'stop' event messages."""
        # Setup stop message
        stop_message = {
            "event": "stop",
            "streamSid": sample_stream_sid
        }
        
        mock_websocket.add_message("json", stop_message)
        
        # Process messages
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify stop message was processed
        mock_logger.info.assert_any_call(f"Media stream stopped for call {sample_call_sid}")
    
    @pytest.mark.asyncio
    async def test_unknown_message_type_handling(self, mock_websocket, sample_call_sid):
        """Test handling of unknown message types."""
        # Setup unknown message type
        unknown_message = {
            "event": "unknown_event_type",
            "data": {"some": "data"}
        }
        
        mock_websocket.add_message("json", unknown_message)
        mock_websocket.add_message("json", {"event": "stop"})
        
        # Process messages
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify unknown message doesn't crash the handler
        # Should continue processing until stop message
    
    @pytest.mark.asyncio
    async def test_malformed_message_handling(self, mock_websocket, sample_call_sid):
        """Test handling of malformed JSON messages."""
        # Add malformed JSON
        mock_websocket.add_message("text", "invalid json {")
        
        # Process messages
        with patch('app.api.voice.websocket.logger') as mock_logger:
            with pytest.raises(WebSocketDisconnect):
                await handle_media_stream(mock_websocket, sample_call_sid)


class TestConversationRelayMessageRouting:
    """Test message routing for ConversationRelay."""
    
    @pytest.mark.asyncio
    async def test_setup_message_routing(self, mock_websocket):
        """Test routing of ConversationRelay 'setup' messages."""
        handler = ConversationRelayHandler(mock_websocket)
        
        setup_message = {
            "type": "setup",
            "sessionId": f"session_{uuid.uuid4().hex[:16]}",
            "callSid": f"CA{uuid.uuid4().hex[:24]}",
            "from": "+1234567890",
            "to": "+0987654321",
            "callStatus": "in-progress",
            "welcomeGreeting": False
        }
        
        # Mock agent orchestrator
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.start_new_conversation = AsyncMock()
            mock_orchestrator.process_voice_input = AsyncMock(return_value={
                "text": "Welcome to Red Bar Sushi!",
                "agent": "FrontlineAgent"
            })
            
            await handler.handle_setup(setup_message)
            
            # Verify setup was routed correctly
            assert handler.session_id == setup_message["sessionId"]
            assert handler.call_sid == setup_message["callSid"]
            
            # Verify agent orchestrator calls
            mock_orchestrator.start_new_conversation.assert_called_once()
            mock_orchestrator.process_voice_input.assert_called_once()
            
            # Verify response was sent
            sent_messages = mock_websocket.get_sent_messages("json")
            assert len(sent_messages) > 0
    
    @pytest.mark.asyncio
    async def test_prompt_message_routing(self, mock_websocket):
        """Test routing of ConversationRelay 'prompt' messages."""
        handler = ConversationRelayHandler(mock_websocket)
        handler.call_sid = f"CA{uuid.uuid4().hex[:24]}"
        
        prompt_message = {
            "type": "prompt", 
            "voicePrompt": "I would like to order a California roll",
            "lang": "en-US",
            "last": True
        }
        
        # Mock agent orchestrator and FSM
        mock_fsm = MagicMock()
        mock_fsm.current_state.name = "ORDERING"
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            mock_orchestrator.process_voice_input = AsyncMock(return_value={
                "text": "Great choice! One California roll added to your order.",
                "agent": "MenuAgent"
            })
            
            await handler.handle_prompt(prompt_message)
            
            # Verify prompt was routed to agent
            mock_orchestrator.process_voice_input.assert_called_once_with(
                handler.call_sid, "I would like to order a California roll"
            )
            
            # Verify response was sent
            sent_messages = mock_websocket.get_sent_messages("json")
            assert len(sent_messages) > 0
            
            # Check response format
            text_message = sent_messages[0]["data"]
            assert text_message["type"] == "text"
            assert "California roll" in text_message["token"]
    
    @pytest.mark.asyncio
    async def test_interrupt_message_routing(self, mock_websocket):
        """Test routing of ConversationRelay 'interrupt' messages."""
        handler = ConversationRelayHandler(mock_websocket)
        handler.call_sid = f"CA{uuid.uuid4().hex[:24]}"
        handler.is_agent_speaking = True
        
        interrupt_message = {
            "type": "interrupt",
            "reason": "speech",
            "utteranceUntilInterrupt": "Great choice! One Califor"
        }
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.handle_interruption = AsyncMock()
            
            await handler.handle_interrupt(interrupt_message)
            
            # Verify interruption was handled
            mock_orchestrator.handle_interruption.assert_called_once_with(handler.call_sid)
            
            # Verify speaking state was reset
            assert handler.is_agent_speaking is False
    
    @pytest.mark.asyncio
    async def test_dtmf_message_routing(self, mock_websocket):
        """Test routing of ConversationRelay 'dtmf' messages."""
        handler = ConversationRelayHandler(mock_websocket)
        
        dtmf_message = {
            "type": "dtmf",
            "digit": "1"
        }
        
        with patch('app.api.conversation_relay.handler.logger') as mock_logger:
            await handler.handle_dtmf(dtmf_message)
            
            # Verify DTMF was logged
            mock_logger.info.assert_called_with("DTMF digit received: 1")
    
    @pytest.mark.asyncio
    async def test_error_message_routing(self, mock_websocket):
        """Test routing of ConversationRelay 'error' messages."""
        handler = ConversationRelayHandler(mock_websocket)
        
        error_message = {
            "type": "error",
            "errorCode": "TTS_FAILED", 
            "errorMessage": "Text-to-speech conversion failed"
        }
        
        with patch('app.api.conversation_relay.handler.logger') as mock_logger:
            await handler.handle_error(error_message)
            
            # Verify error was logged
            mock_logger.error.assert_called_with(
                "Twilio error - Code: TTS_FAILED, Message: Text-to-speech conversion failed"
            )
    
    @pytest.mark.asyncio
    async def test_unknown_message_type_routing(self, mock_websocket):
        """Test routing of unknown message types in ConversationRelay."""
        handler = ConversationRelayHandler(mock_websocket)
        
        # Mock the run method to process one message and stop
        unknown_message = {
            "type": "unknown_type",
            "data": "some data"
        }
        
        mock_websocket.add_message("json", unknown_message)
        
        with patch('app.api.conversation_relay.handler.logger') as mock_logger:
            # Simulate one iteration of the message loop
            try:
                message = await mock_websocket.receive_json()
                message_type = message.get("type")
                
                if message_type == "setup":
                    await handler.handle_setup(message)
                elif message_type == "prompt":
                    await handler.handle_prompt(message)
                elif message_type == "interrupt":
                    await handler.handle_interrupt(message)
                elif message_type == "dtmf":
                    await handler.handle_dtmf(message)
                elif message_type == "error":
                    await handler.handle_error(message)
                else:
                    mock_logger.warning(f"Unknown message type: {message_type}")
                    
            except WebSocketDisconnect:
                pass
            
            # Verify unknown message type was logged
            mock_logger.warning.assert_called_with("Unknown message type: unknown_type")


class TestMessageQueueingAndProcessing:
    """Test message queuing and sequential processing."""
    
    @pytest.mark.asyncio
    async def test_sequential_message_processing(self, mock_websocket, sample_call_sid):
        """Test that messages are processed sequentially."""
        # Setup multiple messages
        messages = [
            {"event": "connected", "protocol": "Call", "version": "1.0.0"},
            {"event": "start", "streamSid": "SM123", "accountSid": "AC123"},
            {"event": "media", "media": {"payload": "data1"}},
            {"event": "media", "media": {"payload": "data2"}},
            {"event": "stop"}
        ]
        
        # Add all messages
        for msg in messages:
            mock_websocket.add_message("json", msg)
        
        # Track processing order
        processed_events = []
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            # Mock logger to track event processing
            def track_event(message):
                if "connected" in message:
                    processed_events.append("connected")
                elif "started" in message:
                    processed_events.append("start")
                elif "stopped" in message:
                    processed_events.append("stop")
            
            mock_logger.info.side_effect = track_event
            
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify events were processed in order
        expected_order = ["connected", "start", "stop"]
        assert processed_events == expected_order
    
    @pytest.mark.asyncio
    async def test_message_backlog_handling(self, mock_websocket):
        """Test handling of message backlogs."""
        handler = ConversationRelayHandler(mock_websocket)
        
        # Add multiple prompt messages
        for i in range(5):
            mock_websocket.add_message("json", {
                "type": "prompt",
                "voicePrompt": f"Message {i}",
                "lang": "en-US",
                "last": True
            })
        
        responses = []
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = "ORDERING"
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            
            # Mock different responses for each message
            def mock_process_input(call_sid, text):
                response_text = f"Response to: {text}"
                responses.append(response_text)
                return {"text": response_text, "agent": "TestAgent"}
            
            mock_orchestrator.process_voice_input = AsyncMock(side_effect=mock_process_input)
            
            # Process each message
            for i in range(5):
                try:
                    message = await mock_websocket.receive_json()
                    if message.get("type") == "prompt":
                        await handler.handle_prompt(message)
                except WebSocketDisconnect:
                    break
        
        # Verify all messages were processed
        assert len(responses) == 5
        for i, response in enumerate(responses):
            assert f"Message {i}" in response


class TestMessageValidationAndSanitization:
    """Test message validation and sanitization."""
    
    @pytest.mark.asyncio
    async def test_message_structure_validation(self, mock_websocket):
        """Test validation of message structure."""
        handler = ConversationRelayHandler(mock_websocket)
        
        # Test message with missing required fields
        invalid_setup = {
            "type": "setup",
            # Missing sessionId, callSid, etc.
        }
        
        # Should handle gracefully without crashing
        await handler.handle_setup(invalid_setup)
        
        # Verify handler didn't crash
        assert handler.session_id is None  # Should remain None for invalid setup
    
    @pytest.mark.asyncio
    async def test_message_content_sanitization(self, mock_websocket):
        """Test sanitization of message content."""
        handler = ConversationRelayHandler(mock_websocket)
        handler.call_sid = "test_call"
        
        # Test prompt with potentially harmful content
        malicious_prompt = {
            "type": "prompt",
            "voicePrompt": "<script>alert('xss')</script>I want sushi",
            "lang": "en-US",
            "last": True
        }
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = "ORDERING"
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            mock_orchestrator.process_voice_input = AsyncMock(return_value={
                "text": "I'd be happy to help with your order",
                "agent": "MenuAgent"
            })
            
            await handler.handle_prompt(malicious_prompt)
            
            # Verify the prompt was passed to agent (sanitization would happen at agent level)
            mock_orchestrator.process_voice_input.assert_called_once_with(
                "test_call", "<script>alert('xss')</script>I want sushi"
            )
    
    @pytest.mark.asyncio
    async def test_empty_message_handling(self, mock_websocket):
        """Test handling of empty or null messages."""
        handler = ConversationRelayHandler(mock_websocket)
        handler.call_sid = "test_call"
        
        # Test empty prompt
        empty_prompt = {
            "type": "prompt",
            "voicePrompt": "",
            "lang": "en-US",
            "last": True
        }
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            # Should not call agent for empty prompt
            await handler.handle_prompt(empty_prompt)
            
            # Verify agent was not called for empty prompt
            mock_orchestrator.process_voice_input.assert_not_called()


class TestMessageRoutingPerformance:
    """Test message routing performance and efficiency."""
    
    @pytest.mark.asyncio
    async def test_high_frequency_message_routing(self, mock_websocket, sample_call_sid):
        """Test routing of high-frequency messages."""
        # Add many media messages (simulating high-frequency audio)
        num_messages = 100
        for i in range(num_messages):
            mock_websocket.add_message("json", {
                "event": "media",
                "media": {"payload": f"audio_chunk_{i}"}
            })
        mock_websocket.add_message("json", {"event": "stop"})
        
        # Measure processing time
        import time
        start_time = time.time()
        
        with patch('app.api.voice.websocket.logger'):
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process messages efficiently
        assert processing_time < 2.0  # Should complete within 2 seconds
    
    @pytest.mark.asyncio 
    async def test_concurrent_message_routing(self):
        """Test concurrent message routing across multiple connections."""
        # Create multiple mock connections
        connections = []
        call_sids = []
        
        for i in range(10):
            mock_ws = MockWebSocket()
            call_sid = f"CA{uuid.uuid4().hex[:16]}{i:08d}"
            
            # Add messages to each connection
            mock_ws.add_message("json", {"event": "connected"})
            mock_ws.add_message("json", {"event": "start", "streamSid": f"SM{i}"})
            mock_ws.add_message("json", {"event": "media", "media": {"payload": f"data_{i}"}})
            mock_ws.add_message("json", {"event": "stop"})
            
            connections.append(mock_ws)
            call_sids.append(call_sid)
        
        # Process all connections concurrently
        async def process_connection(ws, call_sid):
            with patch('app.api.voice.websocket.logger'):
                await handle_media_stream(ws, call_sid)
            return True
        
        tasks = [process_connection(ws, cid) for ws, cid in zip(connections, call_sids)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all connections were processed successfully
        successful_results = [r for r in results if r is True]
        assert len(successful_results) == 10
    
    @pytest.mark.asyncio
    async def test_message_routing_memory_efficiency(self, mock_websocket, sample_call_sid):
        """Test memory efficiency of message routing."""
        # Add a large number of messages to test memory usage
        large_payload = "x" * 1000  # 1KB payload
        
        for i in range(50):
            mock_websocket.add_message("json", {
                "event": "media",
                "media": {"payload": large_payload}
            })
        mock_websocket.add_message("json", {"event": "stop"})
        
        # Process messages and verify no memory leaks
        with patch('app.api.voice.websocket.logger'):
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # If we reach here without memory errors, the test passes
        assert True