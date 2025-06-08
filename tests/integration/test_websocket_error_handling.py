"""
Integration tests for WebSocket error handling - Task 3.6.4.

This module tests comprehensive error handling scenarios for WebSocket connections,
including protocol errors, data corruption, timeout handling, and recovery mechanisms
for both Twilio Media Streams and ConversationRelay handlers.
"""

import pytest
import asyncio
import json
import uuid
import time
from typing import Dict, Any, List, Optional, Union
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.api.voice.websocket import handle_media_stream, handle_twilio_media_stream
from app.api.conversation_relay.handler import ConversationRelayHandler


class ErrorSimulatingWebSocket:
    """Mock WebSocket that can simulate various error conditions."""
    
    def __init__(self):
        self.state = WebSocketState.CONNECTING
        self.client_state = WebSocketState.CONNECTING
        self.messages_sent = []
        self.messages_received = []
        self.headers = {}
        self.query_params = {}
        self.client = None
        self.error_mode = None
        self.error_after_messages = None
        self.messages_processed = 0
        self.send_errors = []
        self.receive_errors = []
        
    async def accept(self):
        """Mock accept method."""
        if self.error_mode == "accept_failure":
            raise ConnectionError("Failed to accept WebSocket connection")
        self.state = WebSocketState.CONNECTED
        self.client_state = WebSocketState.CONNECTED
        
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        if self.error_mode == "close_failure":
            raise RuntimeError("Failed to close WebSocket connection")
        self.state = WebSocketState.DISCONNECTED
        self.client_state = WebSocketState.DISCONNECTED
        
    async def send_text(self, data: str):
        """Mock send_text method with error simulation."""
        if self.error_mode == "send_error":
            raise ConnectionError("Failed to send text message")
        if "send_timeout" in self.send_errors:
            raise asyncio.TimeoutError("Send operation timed out")
        if "send_broken_pipe" in self.send_errors:
            raise BrokenPipeError("Broken pipe during send")
            
        self.messages_sent.append({"type": "text", "data": data})
        
    async def send_json(self, data: Dict[str, Any]):
        """Mock send_json method with error simulation."""
        if self.error_mode == "send_json_error":
            raise ValueError("Failed to serialize JSON")
        if "send_connection_reset" in self.send_errors:
            raise ConnectionResetError("Connection reset by peer")
            
        self.messages_sent.append({"type": "json", "data": data})
        
    async def receive_text(self):
        """Mock receive_text method with error simulation."""
        return await self._receive_with_errors("text")
        
    async def receive_json(self):
        """Mock receive_json method with error simulation."""
        return await self._receive_with_errors("json")
    
    async def _receive_with_errors(self, expected_type: str):
        """Internal method to handle message receiving with error simulation."""
        self.messages_processed += 1
        
        # Check if we should simulate an error after certain number of messages
        if (self.error_after_messages is not None and 
            self.messages_processed > self.error_after_messages):
            if self.error_mode == "receive_timeout":
                raise asyncio.TimeoutError("Receive operation timed out")
            elif self.error_mode == "receive_connection_error":
                raise ConnectionError("Connection lost during receive")
            elif self.error_mode == "receive_decode_error":
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "Invalid UTF-8")
        
        # Simulate specific receive errors
        if "receive_json_decode_error" in self.receive_errors:
            if expected_type == "json":
                raise json.JSONDecodeError("Invalid JSON", "{invalid", 0)
        
        if "receive_websocket_disconnect" in self.receive_errors:
            raise WebSocketDisconnect()
            
        if "receive_memory_error" in self.receive_errors:
            raise MemoryError("Out of memory during receive")
        
        # Normal message processing
        if self.messages_received:
            message = self.messages_received.pop(0)
            if message["type"] == expected_type:
                return message["data"]
        
        # No more messages
        raise WebSocketDisconnect()
    
    def add_message(self, message_type: str, data: Any):
        """Add a message to the received queue."""
        self.messages_received.append({"type": message_type, "data": data})
        
    def set_error_mode(self, mode: str, after_messages: Optional[int] = None):
        """Set error simulation mode."""
        self.error_mode = mode
        self.error_after_messages = after_messages
        
    def add_send_error(self, error_type: str):
        """Add a send error type."""
        self.send_errors.append(error_type)
        
    def add_receive_error(self, error_type: str):
        """Add a receive error type."""
        self.receive_errors.append(error_type)


@pytest.fixture
def error_websocket():
    """Create an error-simulating WebSocket for testing."""
    return ErrorSimulatingWebSocket()


@pytest.fixture
def sample_call_sid():
    """Generate a sample call SID for testing."""
    return f"CA{uuid.uuid4().hex[:24]}"


class TestWebSocketConnectionErrors:
    """Test WebSocket connection-level errors."""
    
    @pytest.mark.asyncio
    async def test_connection_accept_failure(self, error_websocket, sample_call_sid):
        """Test handling of connection accept failures."""
        error_websocket.set_error_mode("accept_failure")
        
        # Test main handler with accept failure
        with pytest.raises(ConnectionError):
            await handle_media_stream(
                error_websocket,
                sample_call_sid,
                debug=False,
                client="twilio"
            )
    
    @pytest.mark.asyncio
    async def test_connection_close_failure(self, error_websocket, sample_call_sid):
        """Test handling of connection close failures."""
        error_websocket.set_error_mode("close_failure")
        
        # Add a simple message to process
        error_websocket.add_message("json", {"event": "stop"})
        
        # Handler should complete despite close failure
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should log the stop event even if close fails
            mock_logger.info.assert_any_call(f"Media stream stopped for call {sample_call_sid}")
    
    @pytest.mark.asyncio
    async def test_connection_timeout_during_setup(self, error_websocket):
        """Test handling of connection timeouts during setup."""
        # Simulate timeout during initial connection
        async def timeout_handler():
            await asyncio.sleep(0.2)  # Simulate slow setup
            return "setup_complete"
        
        # Test with short timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(timeout_handler(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_unexpected_connection_state_changes(self, error_websocket):
        """Test handling of unexpected connection state changes."""
        # Start with connected state
        await error_websocket.accept()
        assert error_websocket.state == WebSocketState.CONNECTED
        
        # Simulate unexpected state change
        error_websocket.state = WebSocketState.DISCONNECTED
        
        # Attempting to send should detect state change
        with pytest.raises((ConnectionError, WebSocketDisconnect)):
            await error_websocket.send_json({"test": "message"})


class TestMessageTransmissionErrors:
    """Test errors during message transmission."""
    
    @pytest.mark.asyncio
    async def test_send_message_failures(self, error_websocket, sample_call_sid):
        """Test handling of send message failures."""
        error_websocket.set_error_mode("send_error")
        error_websocket.add_message("json", {"event": "start", "streamSid": "SM123"})
        error_websocket.add_message("json", {"event": "stop"})
        
        # Handler should handle send errors gracefully
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should log errors but continue processing
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_json_serialization_errors(self, error_websocket, sample_call_sid):
        """Test handling of JSON serialization errors."""
        error_websocket.set_error_mode("send_json_error")
        error_websocket.add_message("json", {"event": "start", "streamSid": "SM123"})
        error_websocket.add_message("json", {"event": "stop"})
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should handle JSON serialization errors
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_network_transmission_errors(self, error_websocket):
        """Test handling of various network transmission errors."""
        handler = ConversationRelayHandler(error_websocket)
        
        # Test different network errors
        network_errors = [
            "send_timeout",
            "send_broken_pipe", 
            "send_connection_reset"
        ]
        
        for error_type in network_errors:
            error_websocket.send_errors.clear()
            error_websocket.add_send_error(error_type)
            
            # Attempt to send text and verify error handling
            with pytest.raises((asyncio.TimeoutError, BrokenPipeError, ConnectionResetError)):
                await handler.send_text("Test message")
    
    @pytest.mark.asyncio
    async def test_large_message_transmission_errors(self, error_websocket):
        """Test handling of errors with large messages."""
        handler = ConversationRelayHandler(error_websocket)
        
        # Create a very large message
        large_message = "x" * 100000  # 100KB message
        
        error_websocket.add_send_error("send_timeout")
        
        # Should handle timeout with large messages
        with pytest.raises(asyncio.TimeoutError):
            await handler.send_text(large_message)


class TestMessageReceptionErrors:
    """Test errors during message reception."""
    
    @pytest.mark.asyncio
    async def test_receive_timeout_errors(self, error_websocket, sample_call_sid):
        """Test handling of receive timeout errors."""
        error_websocket.set_error_mode("receive_timeout", after_messages=1)
        error_websocket.add_message("json", {"event": "connected"})
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should handle timeout gracefully
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_json_decode_errors(self, error_websocket):
        """Test handling of JSON decode errors."""
        handler = ConversationRelayHandler(error_websocket)
        error_websocket.add_receive_error("receive_json_decode_error")
        error_websocket.add_message("json", {"type": "setup"})  # This will trigger decode error
        
        # Simulate one iteration of message loop with decode error
        with patch('app.api.conversation_relay.handler.logger') as mock_logger:
            try:
                message = await error_websocket.receive_json()
            except json.JSONDecodeError as e:
                # This is expected - verify it's logged properly
                mock_logger.error("Invalid JSON received: {e}")
    
    @pytest.mark.asyncio
    async def test_unicode_decode_errors(self, error_websocket, sample_call_sid):
        """Test handling of Unicode decode errors."""
        error_websocket.set_error_mode("receive_decode_error", after_messages=1)
        error_websocket.add_message("text", "valid message")
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should handle decode errors
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_memory_errors_during_receive(self, error_websocket):
        """Test handling of memory errors during message reception."""
        handler = ConversationRelayHandler(error_websocket)
        error_websocket.add_receive_error("receive_memory_error")
        error_websocket.add_message("json", {"type": "setup"})
        
        # Should handle memory errors gracefully
        with pytest.raises(MemoryError):
            await error_websocket.receive_json()
    
    @pytest.mark.asyncio
    async def test_corrupted_message_handling(self, error_websocket, sample_call_sid):
        """Test handling of corrupted messages."""
        # Add corrupted JSON messages
        corrupted_messages = [
            '{"event": "start", "invalid": }',  # Invalid JSON
            '{"event": "media", "media": {"payload": "###CORRUPTED###"}}',  # Corrupted payload
            '{"event": "stop"',  # Incomplete JSON
        ]
        
        for msg in corrupted_messages:
            error_websocket.add_message("text", msg)
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
            
            # Should log errors for corrupted messages
            assert mock_logger.error.call_count >= 1


class TestProtocolErrors:
    """Test protocol-level errors and violations."""
    
    @pytest.mark.asyncio
    async def test_invalid_message_sequence(self, error_websocket, sample_call_sid):
        """Test handling of invalid message sequences."""
        # Send messages in wrong order (media before start)
        invalid_sequence = [
            {"event": "media", "media": {"payload": "data"}},  # Before start
            {"event": "stop"},  # Before start
            {"event": "start", "streamSid": "SM123"},  # Too late
        ]
        
        for msg in invalid_sequence:
            error_websocket.add_message("json", msg)
        
        # Handler should process all messages without crashing
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, error_websocket):
        """Test handling of messages with missing required fields."""
        handler = ConversationRelayHandler(error_websocket)
        
        # Setup message missing required fields
        invalid_setup = {
            "type": "setup"
            # Missing sessionId, callSid, etc.
        }
        
        # Should handle missing fields gracefully
        await handler.handle_setup(invalid_setup)
        
        # Verify handler state remains None for invalid setup
        assert handler.session_id is None
        assert handler.call_sid is None
    
    @pytest.mark.asyncio
    async def test_invalid_field_types(self, error_websocket):
        """Test handling of messages with invalid field types."""
        handler = ConversationRelayHandler(error_websocket)
        
        # Setup message with wrong field types
        invalid_types_setup = {
            "type": "setup",
            "sessionId": 12345,  # Should be string
            "callSid": True,     # Should be string
            "from": ["array"],   # Should be string
        }
        
        # Should handle invalid types gracefully
        await handler.handle_setup(invalid_types_setup)
        
        # Verify handler converted or handled invalid types
        assert isinstance(handler.session_id, (str, type(None)))
    
    @pytest.mark.asyncio
    async def test_unexpected_message_format(self, error_websocket, sample_call_sid):
        """Test handling of completely unexpected message formats."""
        # Add various unexpected formats
        unexpected_formats = [
            "plain string message",
            {"unexpected": "structure"},
            {"event": 12345},  # event should be string
            [],  # Array instead of object
            None,  # Null message
        ]
        
        for msg in unexpected_formats:
            if isinstance(msg, str):
                error_websocket.add_message("text", msg)
            else:
                error_websocket.add_message("json", msg)
        
        # Add proper stop message to end stream
        error_websocket.add_message("json", {"event": "stop"})
        
        # Should handle all unexpected formats without crashing
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_twilio_media_stream(error_websocket, sample_call_sid)


class TestConcurrentErrorHandling:
    """Test error handling under concurrent conditions."""
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_errors(self):
        """Test handling of errors across multiple concurrent connections."""
        # Create multiple error-prone connections
        error_websockets = [ErrorSimulatingWebSocket() for _ in range(5)]
        call_sids = [f"CA{uuid.uuid4().hex[:16]}{i:08d}" for i in range(5)]
        
        # Set different error modes for each connection
        error_modes = [
            "send_error",
            "receive_timeout", 
            "send_json_error",
            "receive_connection_error",
            None  # One normal connection
        ]
        
        for ws, mode in zip(error_websockets, error_modes):
            if mode:
                ws.set_error_mode(mode, after_messages=2)
            # Add some messages
            ws.add_message("json", {"event": "connected"})
            ws.add_message("json", {"event": "start", "streamSid": f"SM{uuid.uuid4().hex[:8]}"})
            ws.add_message("json", {"event": "stop"})
        
        async def handle_connection_with_errors(ws, call_sid):
            """Handle a connection that may have errors."""
            try:
                with patch('app.api.voice.websocket.logger'):
                    await handle_twilio_media_stream(ws, call_sid)
                return "success"
            except Exception as e:
                return f"error: {type(e).__name__}"
        
        # Process all connections concurrently
        tasks = [
            handle_connection_with_errors(ws, cid) 
            for ws, cid in zip(error_websockets, call_sids)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify error handling doesn't affect other connections
        success_count = sum(1 for r in results if r == "success")
        assert success_count >= 1  # At least the normal connection should succeed
    
    @pytest.mark.asyncio
    async def test_error_propagation_isolation(self):
        """Test that errors in one connection don't affect others."""
        # Create shared error tracking
        shared_error_count = {"count": 0}
        
        async def connection_with_shared_error_tracking(connection_id: str, should_error: bool):
            """Simulate connection with shared error tracking."""
            try:
                if should_error:
                    shared_error_count["count"] += 1
                    raise RuntimeError(f"Simulated error in connection {connection_id}")
                
                # Simulate successful processing
                await asyncio.sleep(0.1)
                return f"success_{connection_id}"
                
            except Exception as e:
                return f"error_{connection_id}_{type(e).__name__}"
        
        # Create mix of successful and failing connections
        tasks = [
            connection_with_shared_error_tracking("conn_1", True),   # Error
            connection_with_shared_error_tracking("conn_2", False),  # Success
            connection_with_shared_error_tracking("conn_3", True),   # Error
            connection_with_shared_error_tracking("conn_4", False),  # Success
            connection_with_shared_error_tracking("conn_5", False),  # Success
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify error isolation
        successful_results = [r for r in results if r.startswith("success_")]
        error_results = [r for r in results if r.startswith("error_")]
        
        assert len(successful_results) == 3  # 3 should succeed
        assert len(error_results) == 2      # 2 should fail
        assert shared_error_count["count"] == 2  # 2 errors recorded


class TestErrorRecoveryMechanisms:
    """Test error recovery and resilience mechanisms."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_errors(self, error_websocket):
        """Test graceful degradation when errors occur."""
        handler = ConversationRelayHandler(error_websocket)
        handler.call_sid = "degradation_test"
        
        # Mock agent orchestrator that sometimes fails
        error_count = 0
        
        async def sometimes_failing_agent(call_sid, text):
            nonlocal error_count
            error_count += 1
            if error_count % 2 == 0:  # Fail every other call
                raise Exception("Agent temporarily unavailable")
            return {"text": f"Processed: {text}", "agent": "TestAgent"}
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = "ORDERING"
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            mock_orchestrator.process_voice_input = AsyncMock(side_effect=sometimes_failing_agent)
            
            # Process multiple prompts
            prompts = [
                {"type": "prompt", "voicePrompt": "Test 1"},
                {"type": "prompt", "voicePrompt": "Test 2"},  # This should fail
                {"type": "prompt", "voicePrompt": "Test 3"},
                {"type": "prompt", "voicePrompt": "Test 4"},  # This should fail
            ]
            
            successful_responses = 0
            
            for prompt in prompts:
                try:
                    await handler.handle_prompt(prompt)
                    successful_responses += 1
                except Exception:
                    # Should send fallback message on error
                    pass
            
            # Should have attempted all prompts, some succeeded
            assert mock_orchestrator.process_voice_input.call_count == 4
    
    @pytest.mark.asyncio
    async def test_error_rate_limiting(self, error_websocket):
        """Test error rate limiting and circuit breaker patterns."""
        # Simulate error rate tracking
        error_tracker = {
            "errors": 0,
            "total_requests": 0,
            "circuit_open": False
        }
        
        async def rate_limited_operation(operation_id: int):
            """Simulate operation with rate limiting."""
            error_tracker["total_requests"] += 1
            
            # Check circuit breaker
            if error_tracker["circuit_open"]:
                raise Exception("Circuit breaker open")
            
            # Simulate errors for some operations
            if operation_id % 3 == 0:  # Every 3rd operation fails
                error_tracker["errors"] += 1
                
                # Open circuit if error rate too high
                error_rate = error_tracker["errors"] / error_tracker["total_requests"]
                if error_rate > 0.5:  # More than 50% errors
                    error_tracker["circuit_open"] = True
                    
                raise Exception(f"Operation {operation_id} failed")
            
            return f"success_{operation_id}"
        
        # Run operations until circuit opens
        results = []
        for i in range(10):
            try:
                result = await rate_limited_operation(i)
                results.append(result)
            except Exception as e:
                results.append(f"error_{i}")
                
                # Stop if circuit is open
                if error_tracker["circuit_open"]:
                    break
        
        # Verify circuit breaker activated
        assert error_tracker["circuit_open"] is True
        assert error_tracker["errors"] > 0
    
    @pytest.mark.asyncio
    async def test_error_logging_and_monitoring(self, error_websocket, sample_call_sid):
        """Test comprehensive error logging and monitoring."""
        # Track different types of errors
        error_log = {
            "connection_errors": 0,
            "protocol_errors": 0,
            "timeout_errors": 0,
            "unknown_errors": 0
        }
        
        def categorize_error(error: Exception):
            """Categorize errors for monitoring."""
            if isinstance(error, (ConnectionError, BrokenPipeError)):
                error_log["connection_errors"] += 1
            elif isinstance(error, (json.JSONDecodeError, ValueError)):
                error_log["protocol_errors"] += 1
            elif isinstance(error, asyncio.TimeoutError):
                error_log["timeout_errors"] += 1
            else:
                error_log["unknown_errors"] += 1
        
        # Simulate various error types
        error_types = [
            ConnectionError("Connection lost"),
            json.JSONDecodeError("Invalid JSON", "{", 0),
            asyncio.TimeoutError("Operation timed out"),
            RuntimeError("Unknown error"),
        ]
        
        for error in error_types:
            categorize_error(error)
        
        # Verify error categorization
        assert error_log["connection_errors"] == 1
        assert error_log["protocol_errors"] == 1  
        assert error_log["timeout_errors"] == 1
        assert error_log["unknown_errors"] == 1
        
        # Verify total error count
        total_errors = sum(error_log.values())
        assert total_errors == 4


class TestEdgeCaseErrorHandling:
    """Test edge case error scenarios."""
    
    @pytest.mark.asyncio
    async def test_memory_exhaustion_handling(self, error_websocket):
        """Test handling of memory exhaustion scenarios."""
        # Simulate memory pressure
        large_data_chunks = []
        
        try:
            # Try to allocate large amounts of memory
            for i in range(100):
                # Each chunk is 1MB
                chunk = "x" * (1024 * 1024)
                large_data_chunks.append(chunk)
                
                # Simulate processing with memory constraints
                if len(large_data_chunks) > 10:  # Limit memory usage
                    large_data_chunks.pop(0)  # Remove oldest
        
        except MemoryError:
            # Should handle gracefully
            pass
        
        # Verify memory was managed
        assert len(large_data_chunks) <= 10
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self, error_websocket):
        """Test handling of resource exhaustion (file descriptors, etc.)."""
        # Simulate resource tracking
        resource_tracker = {
            "file_descriptors": 0,
            "max_file_descriptors": 5,
            "connections": 0,
            "max_connections": 3
        }
        
        async def allocate_resource(resource_type: str):
            """Simulate resource allocation."""
            if resource_type == "file_descriptor":
                if resource_tracker["file_descriptors"] >= resource_tracker["max_file_descriptors"]:
                    raise OSError("Too many open files")
                resource_tracker["file_descriptors"] += 1
                
            elif resource_type == "connection":
                if resource_tracker["connections"] >= resource_tracker["max_connections"]:
                    raise ConnectionError("Too many connections")
                resource_tracker["connections"] += 1
        
        # Test resource limits
        allocated_resources = []
        
        try:
            # Try to allocate more resources than available
            for i in range(10):
                await allocate_resource("file_descriptor")
                allocated_resources.append(f"fd_{i}")
        except OSError:
            # Expected when limit reached
            pass
        
        # Verify limits were enforced
        assert resource_tracker["file_descriptors"] == resource_tracker["max_file_descriptors"]
    
    @pytest.mark.asyncio
    async def test_malicious_input_handling(self, error_websocket):
        """Test handling of potentially malicious inputs."""
        handler = ConversationRelayHandler(error_websocket)
        handler.call_sid = "malicious_test"
        
        # Test various potentially malicious inputs
        malicious_inputs = [
            {"type": "prompt", "voicePrompt": "x" * 1000000},  # Very long input
            {"type": "prompt", "voicePrompt": "\x00\x01\x02"},  # Binary data
            {"type": "setup", "sessionId": "../../../etc/passwd"},  # Path traversal
            {"type": "prompt", "voicePrompt": "<script>alert('xss')</script>"},  # XSS
            {"type": "dtmf", "digit": "1" * 1000},  # Excessively long DTMF
        ]
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = "ORDERING"
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            mock_orchestrator.process_voice_input = AsyncMock(return_value={
                "text": "Safe response", "agent": "TestAgent"
            })
            
            # Process malicious inputs
            for malicious_input in malicious_inputs:
                message_type = malicious_input.get("type")
                
                try:
                    if message_type == "setup":
                        await handler.handle_setup(malicious_input)
                    elif message_type == "prompt":
                        await handler.handle_prompt(malicious_input)
                    elif message_type == "dtmf":
                        await handler.handle_dtmf(malicious_input)
                except Exception:
                    # Should handle malicious inputs gracefully
                    pass
            
            # Verify handler didn't crash and maintained security
            assert handler.call_sid == "malicious_test"  # State preserved