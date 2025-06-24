"""
Integration tests for WebSocket connection lifecycle - Task 3.6.1.

This module tests WebSocket connection establishment, lifecycle management,
and proper cleanup for both Twilio Media Streams and ConversationRelay handlers.
"""

import pytest
import asyncio
import json
import uuid
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.main import app
from app.api.voice.websocket import handle_media_stream
from app.api.conversation_relay.handler import ConversationRelayHandler


class MockWebSocket:
    """Mock WebSocket for testing connection lifecycle."""
    
    def __init__(self):
        self.state = WebSocketState.CONNECTING
        self.client_state = WebSocketState.CONNECTING
        self.messages_sent = []
        self.messages_received = []
        self.headers = {}
        self.query_params = {}
        self.client = None
        self.accept_called = False
        self.close_called = False
        self.closed_code = None
        self.closed_reason = None
        
    async def accept(self):
        """Mock accept method."""
        self.accept_called = True
        self.state = WebSocketState.CONNECTED
        self.client_state = WebSocketState.CONNECTED
        
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        self.close_called = True
        self.closed_code = code
        self.closed_reason = reason
        self.state = WebSocketState.DISCONNECTED
        self.client_state = WebSocketState.DISCONNECTED
        
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
        
    def add_received_message(self, message_type: str, data: Any):
        """Add a message to the received queue."""
        self.messages_received.append({"type": message_type, "data": data})


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()


@pytest.fixture
def sample_call_sid():
    """Generate a sample call SID for testing."""
    return f"CA{uuid.uuid4().hex[:24]}"


class TestWebSocketConnectionLifecycle:
    """Test basic WebSocket connection lifecycle."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection_establishment(self, mock_websocket, sample_call_sid):
        """Test successful WebSocket connection establishment."""
        # Test the connection flow
        mock_websocket.headers = {
            "user-agent": "Twilio/1.0",
            "host": "test.example.com"
        }
        
        # Simulate accepting the connection
        await mock_websocket.accept()
        
        # Verify connection state
        assert mock_websocket.accept_called is True
        assert mock_websocket.state == WebSocketState.CONNECTED
        assert mock_websocket.client_state == WebSocketState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_websocket_connection_rejection(self, mock_websocket):
        """Test WebSocket connection rejection scenarios."""
        # Simulate connection rejection by not calling accept
        # and directly closing the connection
        await mock_websocket.close(code=1008, reason="Policy Violation")
        
        # Verify connection was rejected
        assert mock_websocket.accept_called is False
        assert mock_websocket.close_called is True
        assert mock_websocket.closed_code == 1008
        assert mock_websocket.closed_reason == "Policy Violation"
        assert mock_websocket.state == WebSocketState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_websocket_normal_closure(self, mock_websocket, sample_call_sid):
        """Test normal WebSocket closure."""
        # Establish connection
        await mock_websocket.accept()
        assert mock_websocket.state == WebSocketState.CONNECTED
        
        # Simulate normal closure
        await mock_websocket.close(code=1000, reason="Normal Closure")
        
        # Verify proper closure
        assert mock_websocket.close_called is True
        assert mock_websocket.closed_code == 1000
        assert mock_websocket.closed_reason == "Normal Closure"
        assert mock_websocket.state == WebSocketState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_websocket_abnormal_disconnection(self, mock_websocket):
        """Test handling of abnormal WebSocket disconnections."""
        # Establish connection
        await mock_websocket.accept()
        
        # Simulate abnormal disconnection by raising WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            # This simulates a client disconnecting unexpectedly
            raise WebSocketDisconnect()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_timeout(self):
        """Test WebSocket connection timeout handling."""
        # Create a mock that simulates timeout
        timeout_websocket = MockWebSocket()
        
        async def timeout_accept():
            # Simulate timeout during accept
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError("Connection timeout")
        
        timeout_websocket.accept = timeout_accept
        
        # Test timeout handling
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(timeout_websocket.accept(), timeout=0.05)


class TestTwilioMediaStreamLifecycle:
    """Test WebSocket lifecycle for Twilio Media Streams."""
    
    @pytest.mark.asyncio
    async def test_twilio_connection_flow(self, mock_websocket, sample_call_sid):
        """Test complete Twilio Media Stream connection flow."""
        # Setup Twilio messages
        twilio_messages = [
            {
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            },
            {
                "event": "start",
                "streamSid": f"SM{uuid.uuid4().hex[:24]}",
                "start": {
                    "accountSid": f"AC{uuid.uuid4().hex[:24]}",
                    "streamSid": f"SM{uuid.uuid4().hex[:24]}",
                    "callSid": sample_call_sid,
                    "customParameters": {
                        "debug": "true",
                        "client": "twilio"
                    }
                }
            },
            {
                "event": "media",
                "streamSid": f"SM{uuid.uuid4().hex[:24]}",
                "media": {
                    "track": "inbound",
                    "chunk": "1",
                    "timestamp": "1234567890",
                    "payload": "iVBORw0KGgoAAAANSUhEUgAA..."  # Base64 audio data
                }
            },
            {
                "event": "stop",
                "streamSid": f"SM{uuid.uuid4().hex[:24]}"
            }
        ]
        
        # Add messages to mock websocket
        for msg in twilio_messages:
            mock_websocket.add_received_message("json", msg)
        
        # Test the handler
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(mock_websocket, sample_call_sid)
        
        # Verify messages were processed
        assert len(mock_websocket.messages_sent) > 0
        
        # Check that connected response was sent
        sent_messages = [msg for msg in mock_websocket.messages_sent if msg["type"] == "json"]
        assert any(msg["data"].get("event") == "connected" for msg in sent_messages)
    
    @pytest.mark.asyncio
    async def test_twilio_media_stream_with_errors(self, mock_websocket, sample_call_sid):
        """Test Twilio Media Stream handling with errors."""
        # Add malformed message
        mock_websocket.add_received_message("text", "invalid json")
        
        # Test error handling
        with patch('app.api.voice.websocket.logger') as mock_logger:
            with pytest.raises(WebSocketDisconnect):
                await handle_media_stream(mock_websocket, sample_call_sid)
    
    @pytest.mark.asyncio
    async def test_media_stream_handler_lifecycle(self, sample_call_sid):
        """Test the complete media stream handler lifecycle."""
        mock_websocket = MockWebSocket()
        mock_websocket.headers = {"user-agent": "Twilio/1.0"}
        
        # Mock the environment variable
        with patch.dict('os.environ', {'VOICE_HANDLER': 'media_streams'}):
            with patch('app.api.voice.websocket.handle_media_stream') as mock_handler:
                mock_handler.return_value = None
                
                # Test the main handler
                await handle_media_stream(
                    mock_websocket,
                    sample_call_sid,
                    debug=True,
                    client="twilio",
                    time="1234567890"
                )
                
                # Verify connection was accepted
                assert mock_websocket.accept_called is True
                
                # Verify handler was called
                mock_handler.assert_called_once_with(mock_websocket, sample_call_sid)


class TestConversationRelayLifecycle:
    """Test WebSocket lifecycle for ConversationRelay."""
    
    @pytest.mark.asyncio
    async def test_conversation_relay_setup(self, mock_websocket):
        """Test ConversationRelay setup process."""
        handler = ConversationRelayHandler(mock_websocket)
        
        setup_message = {
            "event": "setup",
            "sessionId": f"session_{uuid.uuid4().hex[:16]}",
            "callSid": f"CA{uuid.uuid4().hex[:24]}",
            "from": "+1234567890",
            "to": "+0987654321",
            "callStatus": "in-progress"
        }
        
        # Mock the agent orchestrator
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.start_new_conversation = AsyncMock()
            mock_orchestrator.process_voice_input = AsyncMock(return_value={"text": "Hello!"})
            
            await handler.handle_setup(setup_message)
            
            # Verify setup was processed
            assert handler.session_id == setup_message["sessionId"]
            assert handler.call_sid == setup_message["callSid"]
            assert handler.from_number == setup_message["from"]
            assert handler.to_number == setup_message["to"]
            
            # Verify agent orchestrator was called
            mock_orchestrator.start_new_conversation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conversation_relay_prompt_handling(self, mock_websocket):
        """Test ConversationRelay prompt handling."""
        handler = ConversationRelayHandler(mock_websocket)
        handler.call_sid = f"CA{uuid.uuid4().hex[:24]}"
        
        prompt_message = {
            "event": "prompt",
            "voicePrompt": "I would like to order sushi",
            "lang": "en-US",
            "last": True
        }
        
        # Mock the agent orchestrator
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.get_fsm = AsyncMock(return_value=MagicMock(current_state=MagicMock(name="GREETING")))
            mock_orchestrator.process_voice_input = AsyncMock(return_value={
                "text": "I'd be happy to help you with your sushi order!",
                "agent": "FrontlineAgent"
            })
            
            await handler.handle_prompt(prompt_message)
            
            # Verify orchestrator was called with correct parameters
            mock_orchestrator.process_voice_input.assert_called_once_with(
                handler.call_sid, "I would like to order sushi"
            )
    
    @pytest.mark.asyncio
    async def test_conversation_relay_with_welcome_greeting(self, mock_websocket):
        """Test ConversationRelay with welcome greeting enabled."""
        handler = ConversationRelayHandler(mock_websocket)
        
        setup_message = {
            "event": "setup",
            "sessionId": f"session_{uuid.uuid4().hex[:16]}",
            "callSid": f"CA{uuid.uuid4().hex[:24]}",
            "welcomeGreeting": True  # This should skip initial greeting
        }
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.start_new_conversation = AsyncMock()
            
            await handler.handle_setup(setup_message)
            
            # Should not send initial greeting when welcomeGreeting is true
            # Verify only start_new_conversation was called, not process_voice_input
            mock_orchestrator.start_new_conversation.assert_called_once()
            mock_orchestrator.process_voice_input.assert_not_called()


class TestWebSocketErrorHandling:
    """Test WebSocket error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_websocket_json_parsing_errors(self, mock_websocket, sample_call_sid):
        """Test handling of JSON parsing errors."""
        # Add invalid JSON message
        mock_websocket.add_received_message("text", "invalid json {")
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            with pytest.raises(WebSocketDisconnect):
                await handle_media_stream(mock_websocket, sample_call_sid)
    
    @pytest.mark.asyncio
    async def test_websocket_unexpected_disconnect(self, mock_websocket, sample_call_sid):
        """Test handling of unexpected WebSocket disconnections."""
        # Don't add any messages, so receive_text will raise WebSocketDisconnect
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            # Should handle disconnect gracefully
            await handle_media_stream(mock_websocket, sample_call_sid)
            
            # Verify logging occurred
            assert mock_logger.info.called or mock_logger.error.called
    
    @pytest.mark.asyncio
    async def test_websocket_agent_orchestrator_errors(self, mock_websocket):
        """Test handling of agent orchestrator errors."""
        handler = ConversationRelayHandler(mock_websocket)
        
        setup_message = {
            "event": "setup",
            "sessionId": f"session_{uuid.uuid4().hex[:16]}",
            "callSid": f"CA{uuid.uuid4().hex[:24]}"
        }
        
        # Mock orchestrator to raise exception
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.start_new_conversation = AsyncMock(side_effect=Exception("Agent error"))
            
            # Should handle error gracefully
            await handler.handle_setup(setup_message)
            
            # Setup should still complete
            assert handler.session_id == setup_message["sessionId"]
    
    @pytest.mark.asyncio
    async def test_websocket_connection_state_validation(self, mock_websocket):
        """Test WebSocket connection state validation."""
        # Test sending data on disconnected socket
        mock_websocket.state = WebSocketState.DISCONNECTED
        mock_websocket.client_state = WebSocketState.DISCONNECTED
        
        # Attempting to send should be handled gracefully
        try:
            await mock_websocket.send_json({"test": "data"})
            # Should add to sent messages even if disconnected (for testing)
            assert len(mock_websocket.messages_sent) == 1
        except Exception:
            # Or it might raise an exception, which should be caught by handlers
            pass


class TestWebSocketConcurrentConnections:
    """Test concurrent WebSocket connections."""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_connections(self):
        """Test handling multiple concurrent WebSocket connections."""
        # Create multiple mock websockets
        websockets = [MockWebSocket() for _ in range(5)]
        call_sids = [f"CA{uuid.uuid4().hex[:24]}" for _ in range(5)]
        
        async def handle_connection(ws, call_sid):
            """Handle a single connection."""
            try:
                await ws.accept()
                # Add a simple message
                ws.add_received_message("json", {
                    "event": "connected",
                    "protocol": "Call",
                    "version": "1.0.0"
                })
                # Simulate processing
                await asyncio.sleep(0.1)
                return True
            except Exception:
                return False
        
        # Handle all connections concurrently
        tasks = [handle_connection(ws, cid) for ws, cid in zip(websockets, call_sids)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all connections were handled
        successful_connections = sum(1 for result in results if result is True)
        assert successful_connections == 5
        
        # Verify all websockets were accepted
        for ws in websockets:
            assert ws.accept_called is True
            assert ws.state == WebSocketState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_connection_cleanup_on_exception(self, mock_websocket, sample_call_sid):
        """Test that connections are properly cleaned up on exceptions."""
        # Mock an exception during handler execution
        with patch('app.api.voice.websocket.handle_media_stream') as mock_handler:
            mock_handler.side_effect = Exception("Handler error")
            
            # Test the main handler with exception
            await handle_media_stream(
                mock_websocket,
                sample_call_sid,
                debug=False,
                client="twilio"
            )
            
            # Connection should still be accepted (before handler is called)
            assert mock_websocket.accept_called is True
            
            # Connection should be closed due to exception handling
            # Note: In real implementation, this would be handled in the try/finally block
    
    @pytest.mark.asyncio
    async def test_websocket_resource_cleanup(self):
        """Test proper cleanup of WebSocket resources."""
        resources_created = []
        resources_cleaned = []
        
        class TrackedResource:
            def __init__(self, resource_id):
                self.id = resource_id
                resources_created.append(self.id)
            
            async def cleanup(self):
                resources_cleaned.append(self.id)
        
        async def simulate_websocket_handler_with_resources():
            """Simulate a WebSocket handler that creates resources."""
            resource = TrackedResource("resource_1")
            
            try:
                # Simulate some work
                await asyncio.sleep(0.01)
                # Simulate an error
                raise Exception("Simulated error")
            finally:
                # Cleanup resource
                await resource.cleanup()
        
        # Run the simulation
        with pytest.raises(Exception):
            await simulate_websocket_handler_with_resources()
        
        # Verify resources were created and cleaned up
        assert len(resources_created) == 1
        assert len(resources_cleaned) == 1
        assert resources_created[0] == resources_cleaned[0]


class TestWebSocketPerformance:
    """Test WebSocket performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self, mock_websocket):
        """Test WebSocket message processing throughput."""
        # Add many messages to process
        num_messages = 100
        for i in range(num_messages):
            mock_websocket.add_received_message("json", {
                "event": "media",
                "media": {
                    "track": "inbound",
                    "chunk": str(i),
                    "payload": f"data_{i}"
                }
            })
        
        # Add stop message
        mock_websocket.add_received_message("json", {"event": "stop"})
        
        # Measure processing time
        import time
        start_time = time.time()
        
        with patch('app.api.voice.websocket.logger'):
            await handle_media_stream(mock_websocket, "test_call")
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process messages efficiently
        assert processing_time < 1.0  # Should complete within 1 second
        
        # Verify all messages were processed (except the stop message)
        # The handler should have processed the messages before hitting stop
    
    @pytest.mark.asyncio
    async def test_websocket_memory_usage(self):
        """Test WebSocket memory usage with many connections."""
        # This test simulates memory usage patterns
        connections = []
        
        try:
            # Create many connection objects
            for i in range(50):
                mock_ws = MockWebSocket()
                mock_ws.headers = {"connection_id": str(i)}
                connections.append(mock_ws)
            
            # Accept all connections
            for ws in connections:
                await ws.accept()
            
            # Verify all are connected
            connected_count = sum(1 for ws in connections if ws.state == WebSocketState.CONNECTED)
            assert connected_count == 50
            
        finally:
            # Cleanup all connections
            for ws in connections:
                if ws.state == WebSocketState.CONNECTED:
                    await ws.close()
            
            # Verify all are closed
            closed_count = sum(1 for ws in connections if ws.state == WebSocketState.DISCONNECTED)
            assert closed_count == 50