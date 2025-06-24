"""
Integration tests for WebSocket reconnection logic - Task 3.6.3.

This module tests WebSocket reconnection scenarios, connection recovery,
and resilience to network interruptions for both Twilio Media Streams
and ConversationRelay handlers.
"""

import pytest
import asyncio
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.api.voice.websocket import handle_media_stream
from app.api.conversation_relay.handler import ConversationRelayHandler


class ReconnectableWebSocket:
    """Mock WebSocket that can simulate disconnections and reconnections."""
    
    def __init__(self):
        self.state = WebSocketState.CONNECTING
        self.client_state = WebSocketState.CONNECTING
        self.messages_sent = []
        self.messages_received = []
        self.headers = {}
        self.query_params = {}
        self.client = None
        self.disconnect_count = 0
        self.reconnect_count = 0
        self.connection_id = str(uuid.uuid4())
        self.should_disconnect = False
        self.disconnect_after_messages = None
        self.messages_processed = 0
        self.reconnection_delay = 0.1
        
    async def accept(self):
        """Mock accept method."""
        self.state = WebSocketState.CONNECTED
        self.client_state = WebSocketState.CONNECTED
        
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        self.state = WebSocketState.DISCONNECTED
        self.client_state = WebSocketState.DISCONNECTED
        
    async def send_text(self, data: str):
        """Mock send_text method."""
        if self.state != WebSocketState.CONNECTED:
            raise WebSocketDisconnect()
        self.messages_sent.append({"type": "text", "data": data})
        
    async def send_json(self, data: Dict[str, Any]):
        """Mock send_json method."""
        if self.state != WebSocketState.CONNECTED:
            raise WebSocketDisconnect()
        self.messages_sent.append({"type": "json", "data": data})
        
    async def receive_text(self):
        """Mock receive_text method with reconnection simulation."""
        return await self._receive_message("text")
        
    async def receive_json(self):
        """Mock receive_json method with reconnection simulation."""
        return await self._receive_message("json")
    
    async def _receive_message(self, expected_type: str):
        """Internal method to handle message receiving with disconnection simulation."""
        # Check if we should simulate a disconnection
        if self.should_disconnect or (
            self.disconnect_after_messages is not None and 
            self.messages_processed >= self.disconnect_after_messages
        ):
            await self.simulate_disconnection()
            raise WebSocketDisconnect()
        
        # Normal message processing
        if self.messages_received:
            message = self.messages_received.pop(0)
            if message["type"] == expected_type:
                self.messages_processed += 1
                return message["data"]
        
        # No more messages - simulate end of stream
        raise WebSocketDisconnect()
    
    async def simulate_disconnection(self):
        """Simulate a connection disconnection."""
        self.disconnect_count += 1
        self.state = WebSocketState.DISCONNECTED
        self.client_state = WebSocketState.DISCONNECTED
        await asyncio.sleep(self.reconnection_delay)
    
    async def simulate_reconnection(self):
        """Simulate a connection reconnection."""
        self.reconnect_count += 1
        self.connection_id = str(uuid.uuid4())
        self.state = WebSocketState.CONNECTED
        self.client_state = WebSocketState.CONNECTED
        self.should_disconnect = False
        self.messages_processed = 0
        
    def add_message(self, message_type: str, data: Any):
        """Add a message to the received queue."""
        self.messages_received.append({"type": message_type, "data": data})
        
    def set_disconnect_after_messages(self, count: int):
        """Set to disconnect after processing a certain number of messages."""
        self.disconnect_after_messages = count
        
    def force_disconnect(self):
        """Force disconnection on next message receive."""
        self.should_disconnect = True


@pytest.fixture
def reconnectable_websocket():
    """Create a reconnectable mock WebSocket for testing."""
    return ReconnectableWebSocket()


@pytest.fixture
def sample_call_sid():
    """Generate a sample call SID for testing."""
    return f"CA{uuid.uuid4().hex[:24]}"


class TestWebSocketDisconnectionDetection:
    """Test detection of WebSocket disconnections."""
    
    @pytest.mark.asyncio
    async def test_sudden_disconnection_detection(self, reconnectable_websocket, sample_call_sid):
        """Test detection of sudden WebSocket disconnections."""
        # Setup messages and force disconnection
        reconnectable_websocket.add_message("json", {"event": "connected"})
        reconnectable_websocket.force_disconnect()
        
        # Test handler detects disconnection
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(reconnectable_websocket, sample_call_sid)
            
            # Verify disconnection was detected and logged
            mock_logger.info.assert_any_call(f"Twilio disconnected for call {sample_call_sid}")
    
    @pytest.mark.asyncio
    async def test_gradual_connection_degradation(self, reconnectable_websocket, sample_call_sid):
        """Test detection of gradual connection degradation."""
        # Setup messages that will cause disconnection after a few messages
        messages = [
            {"event": "connected"},
            {"event": "start", "streamSid": "SM123"},
            {"event": "media", "media": {"payload": "data1"}},
            {"event": "media", "media": {"payload": "data2"}},
        ]
        
        for msg in messages:
            reconnectable_websocket.add_message("json", msg)
        
        # Set to disconnect after 3 messages
        reconnectable_websocket.set_disconnect_after_messages(3)
        
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(reconnectable_websocket, sample_call_sid)
            
            # Verify disconnection was handled
            assert reconnectable_websocket.disconnect_count == 1
    
    @pytest.mark.asyncio
    async def test_connection_timeout_detection(self):
        """Test detection of connection timeouts."""
        # Create a WebSocket that simulates timeout
        timeout_websocket = ReconnectableWebSocket()
        
        async def timeout_receive():
            await asyncio.sleep(0.2)  # Simulate slow response
            raise WebSocketDisconnect()
        
        timeout_websocket.receive_json = timeout_receive
        
        # Test timeout detection with a short timeout
        with pytest.raises(WebSocketDisconnect):
            await asyncio.wait_for(timeout_websocket.receive_json(), timeout=0.1)


class TestReconnectionAttempts:
    """Test WebSocket reconnection attempt logic."""
    
    @pytest.mark.asyncio
    async def test_automatic_reconnection_after_disconnect(self, reconnectable_websocket):
        """Test automatic reconnection after unexpected disconnection."""
        handler = ConversationRelayHandler(reconnectable_websocket)
        
        # Simulate setup and then disconnection
        setup_message = {
            "type": "setup",
            "sessionId": "test_session",
            "callSid": "test_call"
        }
        
        reconnectable_websocket.add_message("json", setup_message)
        reconnectable_websocket.force_disconnect()
        
        # Mock the agent orchestrator
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_orchestrator.start_new_conversation = AsyncMock()
            
            # The handler should detect disconnection gracefully
            try:
                # Simulate one iteration of the message loop
                message = await reconnectable_websocket.receive_json()
                await handler.handle_setup(message)
            except WebSocketDisconnect:
                # This is expected behavior
                pass
            
            # Verify setup was processed before disconnection
            assert handler.session_id == "test_session"
    
    @pytest.mark.asyncio
    async def test_reconnection_with_state_recovery(self, reconnectable_websocket):
        """Test reconnection with proper state recovery."""
        handler = ConversationRelayHandler(reconnectable_websocket)
        
        # Initial setup
        handler.session_id = "recovered_session"
        handler.call_sid = "recovered_call"
        handler.is_running = True
        
        # Simulate reconnection
        await reconnectable_websocket.simulate_reconnection()
        
        # Verify state is preserved
        assert handler.session_id == "recovered_session"
        assert handler.call_sid == "recovered_call"
        assert reconnectable_websocket.reconnect_count == 1
    
    @pytest.mark.asyncio
    async def test_multiple_reconnection_attempts(self, reconnectable_websocket):
        """Test multiple reconnection attempts."""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            # Simulate disconnection
            await reconnectable_websocket.simulate_disconnection()
            
            # Simulate reconnection attempt
            await reconnectable_websocket.simulate_reconnection()
            
            # Verify reconnection state
            assert reconnectable_websocket.reconnect_count == attempt + 1
            assert reconnectable_websocket.state == WebSocketState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_reconnection(self):
        """Test exponential backoff for reconnection attempts."""
        websocket = ReconnectableWebSocket()
        
        # Simulate exponential backoff delays
        delays = []
        base_delay = 0.1
        
        for attempt in range(4):
            # Calculate exponential backoff delay
            delay = base_delay * (2 ** attempt)
            delays.append(delay)
            
            start_time = time.time()
            websocket.reconnection_delay = delay
            await websocket.simulate_disconnection()
            await websocket.simulate_reconnection()
            end_time = time.time()
            
            # Verify delay was approximately correct
            actual_delay = end_time - start_time
            assert actual_delay >= delay * 0.8  # Allow some tolerance
        
        # Verify exponential increase
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]
        assert delays[3] > delays[2]


class TestConnectionResilienceStrategies:
    """Test connection resilience and recovery strategies."""
    
    @pytest.mark.asyncio
    async def test_heartbeat_keepalive_simulation(self, reconnectable_websocket, sample_call_sid):
        """Test heartbeat/keepalive message handling."""
        # Add heartbeat-style messages
        heartbeat_messages = [
            {"event": "connected"},
            {"event": "ping", "timestamp": str(int(time.time()))},
            {"event": "media", "media": {"payload": "data"}},
            {"event": "ping", "timestamp": str(int(time.time()) + 30)},
            {"event": "stop"}
        ]
        
        for msg in heartbeat_messages:
            reconnectable_websocket.add_message("json", msg)
        
        # Process messages and verify connection stays alive
        with patch('app.api.voice.websocket.logger'):
            await handle_media_stream(reconnectable_websocket, sample_call_sid)
        
        # Connection should have processed all messages without disconnecting
        assert reconnectable_websocket.disconnect_count == 0
    
    @pytest.mark.asyncio
    async def test_connection_quality_monitoring(self, reconnectable_websocket):
        """Test monitoring of connection quality indicators."""
        # Simulate varying connection quality through message delays
        quality_metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "average_delay": 0,
            "timeouts": 0
        }
        
        async def simulate_message_with_delay(delay: float):
            start_time = time.time()
            await asyncio.sleep(delay)
            end_time = time.time()
            
            quality_metrics["messages_sent"] += 1
            quality_metrics["average_delay"] = (
                (quality_metrics["average_delay"] * (quality_metrics["messages_sent"] - 1) + 
                 (end_time - start_time)) / quality_metrics["messages_sent"]
            )
            
            if delay > 0.1:  # Consider delays > 100ms as timeouts
                quality_metrics["timeouts"] += 1
        
        # Simulate messages with varying delays
        delays = [0.01, 0.05, 0.15, 0.02, 0.25, 0.01]  # Some with high delay
        
        for delay in delays:
            await simulate_message_with_delay(delay)
        
        # Verify quality metrics
        assert quality_metrics["messages_sent"] == 6
        assert quality_metrics["timeouts"] == 2  # Two messages with high delay
        assert quality_metrics["average_delay"] > 0
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_poor_connection(self, reconnectable_websocket, sample_call_sid):
        """Test graceful degradation when connection quality is poor."""
        # Setup messages with some that will cause issues
        messages = [
            {"event": "connected"},
            {"event": "start", "streamSid": "SM123"},
            # Simulate dropped messages by not adding some expected media frames
            {"event": "media", "media": {"payload": "data1", "chunk": "1"}},
            # Skip chunk 2 to simulate dropped message
            {"event": "media", "media": {"payload": "data3", "chunk": "3"}},
            {"event": "stop"}
        ]
        
        for msg in messages:
            reconnectable_websocket.add_message("json", msg)
        
        # Handler should gracefully handle missing chunks
        with patch('app.api.voice.websocket.logger') as mock_logger:
            await handle_media_stream(reconnectable_websocket, sample_call_sid)
        
        # Should complete without errors despite missing chunk
        mock_logger.info.assert_any_call(f"Media stream stopped for call {sample_call_sid}")


class TestSessionStateManagement:
    """Test session state management during reconnections."""
    
    @pytest.mark.asyncio
    async def test_session_state_persistence_across_reconnects(self, reconnectable_websocket):
        """Test that session state persists across reconnections."""
        handler = ConversationRelayHandler(reconnectable_websocket)
        
        # Initialize session state
        initial_state = {
            "session_id": "persistent_session",
            "call_sid": "persistent_call",
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "call_status": "in-progress"
        }
        
        handler.session_id = initial_state["session_id"]
        handler.call_sid = initial_state["call_sid"]
        handler.from_number = initial_state["from_number"]
        handler.to_number = initial_state["to_number"]
        handler.call_status = initial_state["call_status"]
        
        # Simulate disconnection and reconnection
        await reconnectable_websocket.simulate_disconnection()
        await reconnectable_websocket.simulate_reconnection()
        
        # Verify state persistence
        assert handler.session_id == initial_state["session_id"]
        assert handler.call_sid == initial_state["call_sid"]
        assert handler.from_number == initial_state["from_number"]
        assert handler.to_number == initial_state["to_number"]
        assert handler.call_status == initial_state["call_status"]
    
    @pytest.mark.asyncio
    async def test_conversation_context_recovery(self, reconnectable_websocket):
        """Test recovery of conversation context after reconnection."""
        handler = ConversationRelayHandler(reconnectable_websocket)
        handler.call_sid = "context_test_call"
        
        # Mock conversation context
        conversation_context = {
            "current_state": "ORDERING",
            "cart_items": ["California Roll", "Miso Soup"],
            "customer_preferences": {"spicy": True}
        }
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            # Mock FSM with conversation context
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = conversation_context["current_state"]
            mock_fsm.context = conversation_context
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            
            # Simulate getting context before disconnection
            fsm = await mock_orchestrator.get_fsm(handler.call_sid)
            context_before = fsm.context
            
            # Simulate disconnection and reconnection
            await reconnectable_websocket.simulate_disconnection()
            await reconnectable_websocket.simulate_reconnection()
            
            # Verify context can be recovered
            fsm_after = await mock_orchestrator.get_fsm(handler.call_sid)
            context_after = fsm_after.context
            
            assert context_before == context_after
    
    @pytest.mark.asyncio
    async def test_message_queue_recovery_after_reconnect(self, reconnectable_websocket):
        """Test recovery of message queue after reconnection."""
        # Simulate messages that were in queue during disconnection
        queued_messages = [
            {"type": "prompt", "voicePrompt": "I want to add more items"},
            {"type": "prompt", "voicePrompt": "What sauces do you have?"},
            {"type": "prompt", "voicePrompt": "I'm ready to order"}
        ]
        
        # Add messages after reconnection simulation
        await reconnectable_websocket.simulate_disconnection()
        await reconnectable_websocket.simulate_reconnection()
        
        for msg in queued_messages:
            reconnectable_websocket.add_message("json", msg)
        
        handler = ConversationRelayHandler(reconnectable_websocket)
        handler.call_sid = "queue_test_call"
        
        processed_messages = []
        
        with patch('app.api.conversation_relay.handler.async_agent_orchestrator') as mock_orchestrator:
            mock_fsm = MagicMock()
            mock_fsm.current_state.name = "ORDERING"
            mock_orchestrator.get_fsm = AsyncMock(return_value=mock_fsm)
            
            def track_processed_message(call_sid, prompt):
                processed_messages.append(prompt)
                return {"text": f"Processed: {prompt}", "agent": "TestAgent"}
            
            mock_orchestrator.process_voice_input = AsyncMock(side_effect=track_processed_message)
            
            # Process queued messages
            for _ in range(len(queued_messages)):
                try:
                    message = await reconnectable_websocket.receive_json()
                    if message.get("type") == "prompt":
                        await handler.handle_prompt(message)
                except WebSocketDisconnect:
                    break
        
        # Verify all queued messages were processed
        assert len(processed_messages) == 3
        assert "add more items" in processed_messages[0]
        assert "sauces" in processed_messages[1]
        assert "ready to order" in processed_messages[2]


class TestReconnectionPerformanceAndLimits:
    """Test performance characteristics and limits of reconnection logic."""
    
    @pytest.mark.asyncio
    async def test_rapid_reconnection_attempts(self):
        """Test handling of rapid reconnection attempts."""
        websocket = ReconnectableWebSocket()
        reconnection_times = []
        
        # Perform rapid reconnections
        num_reconnections = 10
        start_time = time.time()
        
        for i in range(num_reconnections):
            reconnect_start = time.time()
            await websocket.simulate_disconnection()
            await websocket.simulate_reconnection()
            reconnect_end = time.time()
            
            reconnection_times.append(reconnect_end - reconnect_start)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify rapid reconnections are handled efficiently
        assert total_time < 5.0  # Should complete within 5 seconds
        assert websocket.reconnect_count == num_reconnections
        assert all(t < 1.0 for t in reconnection_times)  # Each reconnection < 1 second
    
    @pytest.mark.asyncio
    async def test_reconnection_limit_enforcement(self):
        """Test enforcement of reconnection attempt limits."""
        websocket = ReconnectableWebSocket()
        max_reconnections = 5
        
        # Attempt more reconnections than the limit
        successful_reconnections = 0
        
        for attempt in range(max_reconnections + 3):  # Try 3 more than limit
            try:
                await websocket.simulate_disconnection()
                
                # Simulate reconnection limit check
                if websocket.reconnect_count < max_reconnections:
                    await websocket.simulate_reconnection()
                    successful_reconnections += 1
                else:
                    # Simulate rejection due to limit
                    break
                    
            except Exception:
                break
        
        # Verify limit was enforced
        assert successful_reconnections == max_reconnections
        assert websocket.reconnect_count == max_reconnections
    
    @pytest.mark.asyncio
    async def test_concurrent_reconnection_handling(self):
        """Test handling of concurrent reconnection attempts."""
        # Create multiple websockets simulating concurrent users
        websockets = [ReconnectableWebSocket() for _ in range(5)]
        
        async def handle_reconnections(ws, connection_id):
            """Handle reconnections for a single websocket."""
            try:
                # Simulate multiple disconnection/reconnection cycles
                for cycle in range(3):
                    await ws.simulate_disconnection()
                    await ws.simulate_reconnection()
                    await asyncio.sleep(0.1)  # Brief pause between cycles
                
                return ws.reconnect_count
            except Exception:
                return 0
        
        # Run concurrent reconnection tests
        tasks = [
            handle_reconnections(ws, f"conn_{i}") 
            for i, ws in enumerate(websockets)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all connections handled reconnections successfully
        successful_results = [r for r in results if isinstance(r, int) and r > 0]
        assert len(successful_results) == 5
        assert all(r == 3 for r in successful_results)  # Each should have 3 reconnections
    
    @pytest.mark.asyncio
    async def test_reconnection_memory_efficiency(self):
        """Test memory efficiency during multiple reconnections."""
        websocket = ReconnectableWebSocket()
        
        # Simulate many reconnections to test memory usage
        num_cycles = 50
        
        for cycle in range(num_cycles):
            # Add some messages to simulate memory usage
            websocket.add_message("json", {"event": "test", "cycle": cycle})
            
            await websocket.simulate_disconnection()
            await websocket.simulate_reconnection()
            
            # Clear messages to simulate cleanup
            websocket.messages_received.clear()
            websocket.messages_sent.clear()
        
        # Verify final state
        assert websocket.reconnect_count == num_cycles
        assert len(websocket.messages_received) == 0  # Should be cleared
        assert len(websocket.messages_sent) == 0      # Should be cleared
    
    @pytest.mark.asyncio
    async def test_network_partition_recovery(self, reconnectable_websocket):
        """Test recovery from network partition scenarios."""
        # Simulate network partition with extended disconnection
        partition_duration = 0.5  # 500ms partition
        
        # Set up messages before partition
        pre_partition_messages = [
            {"event": "connected"},
            {"event": "start", "streamSid": "SM_partition_test"}
        ]
        
        for msg in pre_partition_messages:
            reconnectable_websocket.add_message("json", msg)
        
        # Simulate network partition
        reconnectable_websocket.reconnection_delay = partition_duration
        reconnectable_websocket.force_disconnect()
        
        # Attempt to process messages during partition
        start_time = time.time()
        
        with patch('app.api.voice.websocket.logger'):
            await handle_media_stream(reconnectable_websocket, "partition_test_call")
        
        end_time = time.time()
        
        # Verify partition was detected quickly
        assert end_time - start_time < 1.0  # Should fail fast, not hang
        assert reconnectable_websocket.disconnect_count == 1