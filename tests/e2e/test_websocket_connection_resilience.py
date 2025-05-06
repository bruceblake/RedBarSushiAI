"""
End-to-end tests for WebSocket connection resilience in RedBarSushiAI.

This module contains tests that verify the connection stability, recovery,
and error handling capabilities of the WebSocket-based voice processing system.
"""

import pytest
import os
import json
import base64
import asyncio
import time
import uuid
import random
from unittest.mock import patch, MagicMock, AsyncMock

# Set environment to test mode
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"
os.environ["NO_X11"] = "1"  # Disable X11 requirement for headless testing
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"  # Disable display for OpenAI Realtime

# Import app components
from app import create_app
from app.routes.voice.utils.connection_manager import ConnectionState


class MockAsyncWebSocket:
    """Mock WebSocket class for testing with advanced failure simulation."""
    
    def __init__(self, test_inputs=None, mock_responses=None, failure_config=None):
        self.test_inputs = test_inputs or []
        self.mock_responses = mock_responses or {}
        self.sent_messages = []
        self.received_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.connected = True
        self.failure_config = failure_config or {}
        
        # Configure possible failures
        self.failure_points = {
            "disconnect_after_messages": self.failure_config.get("disconnect_after_messages", -1),
            "error_after_messages": self.failure_config.get("error_after_messages", -1),
            "delay_after_messages": self.failure_config.get("delay_after_messages", -1),
            "delay_seconds": self.failure_config.get("delay_seconds", 2.0),
            "drop_message_ratio": self.failure_config.get("drop_message_ratio", 0.0),
            "recover_after_failures": self.failure_config.get("recover_after_failures", True),
        }
        
        # Track message counts and failure states
        self.message_counts = {
            "send": 0,
            "receive": 0,
            "errors": 0,
            "reconnects": 0,
        }
    
    async def send(self, message):
        """Mock send method with failure simulation."""
        self.message_counts["send"] += 1
        
        # Check for disconnect point
        if self.message_counts["send"] == self.failure_points["disconnect_after_messages"]:
            self.connected = False
            raise ConnectionError("Simulated disconnection after " + 
                                 f"{self.message_counts['send']} messages")
        
        # Check for error point
        if self.message_counts["send"] == self.failure_points["error_after_messages"]:
            self.message_counts["errors"] += 1
            raise RuntimeError("Simulated error after " + 
                              f"{self.message_counts['send']} messages")
        
        # Check for random message drop
        if random.random() < self.failure_points["drop_message_ratio"]:
            # Silently drop the message without raising an error
            return
        
        # Check for delay point
        if self.message_counts["send"] == self.failure_points["delay_after_messages"]:
            await asyncio.sleep(self.failure_points["delay_seconds"])
        
        # Process normally
        self.sent_messages.append(message)
        
    async def receive(self):
        """Mock receive method with failure simulation."""
        self.message_counts["receive"] += 1
        
        # Check if disconnected
        if not self.connected:
            # If configured to recover, reconnect after some failures
            if self.failure_points["recover_after_failures"] and \
               self.message_counts["errors"] >= 3:
                self.connected = True
                self.message_counts["reconnects"] += 1
                return json.dumps({
                    "event": "reconnected",
                    "message": "Connection re-established",
                    "reconnect_count": self.message_counts["reconnects"]
                })
            else:
                raise ConnectionError("WebSocket disconnected")
        
        # Check for no more inputs
        if not self.test_inputs:
            # If no more inputs, simulate waiting by yielding control
            await asyncio.sleep(0.1)
            return None
            
        # Get next message
        msg = self.test_inputs.pop(0)
        self.received_messages.append(msg)
        return msg
    
    async def close(self, code=1000, reason=""):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        self.connected = False


class MockRealtimeProcessor:
    """Mock for the OpenAI Realtime API processor with advanced event generation."""
    
    def __init__(self, events=None, failure_config=None):
        self.events = events or []
        self.processed_audio = []
        self.failure_config = failure_config or {}
        self.is_fallback = False
        
        # Event generation configuration
        self.generate_silence = self.failure_config.get("generate_silence", True)
        self.silence_interval = self.failure_config.get("silence_interval", 10)
        self.generate_transcripts = self.failure_config.get("generate_transcripts", True)
        self.transcript_interval = self.failure_config.get("transcript_interval", 15)
        self.generate_errors = self.failure_config.get("generate_errors", False)
        self.error_interval = self.failure_config.get("error_interval", 25)
        
        # Audio processing tracking
        self.chunk_count = 0
        self.event_count = 0
    
    def get_config(self):
        """Return mock configuration."""
        return {
            "vad_enabled": True,
            "sample_rate": 16000,
            "model": "realtime-test-model",
            "response_format": "verbose_json"
        }
    
    def configure_vad(self, config):
        """Mock VAD configuration."""
        self.vad_config = config
        return True
    
    async def process_media_stream(self, audio_generator, session_id):
        """Mock processing of audio stream with dynamic event generation."""
        # First yield any pre-defined events
        for event in self.events:
            self.event_count += 1
            yield event
        
        # Then process audio and generate dynamic events
        async for chunk in audio_generator:
            if chunk:
                self.chunk_count += 1
                self.processed_audio.append(chunk)
                
                # Generate silence events at configured intervals
                if self.generate_silence and self.chunk_count % self.silence_interval == 0:
                    self.event_count += 1
                    yield {
                        "type": "silence_detected",
                        "duration": 2.0,
                        "timestamp": time.time()
                    }
                
                # Generate transcript events at configured intervals
                if self.generate_transcripts and self.chunk_count % self.transcript_interval == 0:
                    self.event_count += 1
                    yield {
                        "type": "transcript_complete",
                        "text": f"This is test transcript #{self.event_count}",
                        "final": True,
                        "timestamp": time.time()
                    }
                
                # Generate error events at configured intervals
                if self.generate_errors and self.chunk_count % self.error_interval == 0:
                    self.event_count += 1
                    yield {
                        "type": "error",
                        "error": f"Test error #{self.event_count}",
                        "timestamp": time.time()
                    }


class MockFSMOrchestrator:
    """Mock FSM orchestrator for testing."""
    
    def __init__(self, initial_state="GREETING"):
        self.states = {}
        self.transitions = {}
        self.current_state = initial_state
    
    def set_state(self, session_id, state):
        """Set the state for a session."""
        self.states[session_id] = state
        return True
    
    def get_current_state(self, session_id):
        """Get the current state for a session."""
        return self.states.get(session_id, self.current_state)
    
    def transition(self, session_id, new_state, reason=None):
        """Record a state transition."""
        old_state = self.get_current_state(session_id)
        self.transitions.setdefault(session_id, []).append((old_state, new_state, reason))
        self.states[session_id] = new_state
        return True


class MockFrontlineAgent:
    """Mock frontline agent for testing."""
    
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.process_calls = []
    
    async def process_voice_input(self, session_id, transcript, context=None):
        """Process voice input and return a response."""
        self.process_calls.append((session_id, transcript, context))
        
        # Return predefined response or generic one
        if transcript in self.responses:
            return self.responses[transcript]
        return f"I processed: {transcript}"


class MockToolRegistry:
    """Mock tool registry for testing."""
    
    def __init__(self, tool_results=None):
        self.tool_results = tool_results or {}
        self.execute_calls = []
        
        # Define default tools
        self.tools = {
            "lookup_menu_item": {
                "function": self._mock_lookup_menu_item
            },
            "get_restaurant_info": {
                "function": self._mock_get_restaurant_info
            }
        }
    
    async def execute_tool(self, session_id, name, arguments):
        """Execute a tool and return the result."""
        self.execute_calls.append((session_id, name, arguments))
        
        # Return predefined result or call mock function
        if name in self.tool_results:
            return self.tool_results[name]
        elif name in self.tools:
            return await self.tools[name]["function"](arguments)
        return {"error": f"Tool not found: {name}"}
    
    async def _mock_lookup_menu_item(self, arguments):
        """Mock menu item lookup tool."""
        item_name = arguments.get("item_name", "")
        return {
            "name": item_name,
            "price": 1200,
            "description": f"Mock description for {item_name}",
            "plu": "MOCK-PLU"
        }
    
    async def _mock_get_restaurant_info(self, arguments):
        """Mock restaurant info tool."""
        query = arguments.get("query", "")
        return {
            "name": "Red Bar Sushi",
            "hours": "11am-10pm",
            "info": f"Mock info for query: {query}"
        }


# Define FSMState enum for testing
class FSMState:
    GREETING = "GREETING"
    MAIN_MENU = "MAIN_MENU"
    ORDERING = "ORDERING"
    CONFIRMATION = "CONFIRMATION"
    COMPLETION = "COMPLETION"


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    
    yield app


@pytest.fixture
def stable_mock_websocket():
    """Create mock WebSocket without failures for baseline testing."""
    return MockAsyncWebSocket()


@pytest.fixture
def failing_mock_websocket():
    """Create mock WebSocket with configured failures for resilience testing."""
    failure_config = {
        "disconnect_after_messages": 15,  # Disconnect after 15 messages
        "error_after_messages": 8,        # Error after 8 messages
        "delay_after_messages": 5,        # Delay after 5 messages
        "delay_seconds": 1.0,             # 1 second delay
        "drop_message_ratio": 0.1,        # 10% chance to drop messages
        "recover_after_failures": True    # Will reconnect after 3 failures
    }
    return MockAsyncWebSocket(failure_config=failure_config)


@pytest.fixture
def disconnecting_mock_websocket():
    """Create mock WebSocket that will disconnect without recovery."""
    failure_config = {
        "disconnect_after_messages": 10,  # Disconnect after 10 messages
        "recover_after_failures": False   # Will not reconnect
    }
    return MockAsyncWebSocket(failure_config=failure_config)


@pytest.fixture
def stable_mock_realtime():
    """Create stable mock Realtime processor."""
    # Pre-defined events for testing
    events = [
        {
            "type": "transcript_complete",
            "text": "Hello, I'd like to place an order",
            "final": True,
            "timestamp": time.time()
        },
        {
            "type": "silence_detected",
            "duration": 1.5,
            "timestamp": time.time()
        },
        {
            "type": "tool_call",
            "name": "lookup_menu_item",
            "arguments": {"item_name": "California roll"},
            "id": "call_123",
            "timestamp": time.time()
        }
    ]
    
    return MockRealtimeProcessor(events=events)


@pytest.fixture
def unstable_mock_realtime():
    """Create unstable mock Realtime processor with frequent silence and errors."""
    failure_config = {
        "generate_silence": True,
        "silence_interval": 5,        # Generate silence every 5 chunks
        "generate_transcripts": True,
        "transcript_interval": 10,    # Generate transcript every 10 chunks
        "generate_errors": True,
        "error_interval": 20         # Generate error every 20 chunks
    }
    
    return MockRealtimeProcessor(failure_config=failure_config)


@pytest.fixture
def mock_components():
    """Create a set of mock components for testing."""
    mock_fsm = MockFSMOrchestrator(initial_state=FSMState.GREETING)
    mock_frontline = MockFrontlineAgent()
    mock_registry = MockToolRegistry()
    
    return {
        "fsm_orchestrator": mock_fsm, 
        "frontline_agent": mock_frontline,
        "tool_registry": mock_registry
    }


@pytest.mark.asyncio
async def test_connection_establishment(app, stable_mock_websocket, stable_mock_realtime, mock_components):
    """Test WebSocket connection establishment and basic communication."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event
    stable_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler with timeout
        try:
            await asyncio.wait_for(
                handle_robust_media_stream(stable_mock_websocket), 
                timeout=2.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check connection establishment messages
    connection_messages = [
        msg for msg in stable_mock_websocket.sent_messages 
        if isinstance(msg, str) and "connected" in msg.lower()
    ]
    assert len(connection_messages) > 0, "Should send connection confirmation"
    
    # Check keep-alive messages
    keep_alive_messages = [
        msg for msg in stable_mock_websocket.sent_messages 
        if isinstance(msg, str) and "keep_alive" in msg.lower()
    ]
    assert len(keep_alive_messages) > 0, "Should send keep-alive messages"


@pytest.mark.asyncio
async def test_connection_recovery_after_server_disconnect(app, failing_mock_websocket, 
                                                         stable_mock_realtime, mock_components):
    """Test that connection recovers after server-side disconnection."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event and audio data
    failing_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Add audio chunks to simulate ongoing conversation
    for i in range(20):
        failing_mock_websocket.test_inputs.append(
            json.dumps({
                "event": "media",
                "media": {
                    "payload": base64.b64encode(f"audio_chunk_{i}".encode()).decode()
                }
            })
        )
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler with timeout
        try:
            await asyncio.wait_for(
                handle_robust_media_stream(failing_mock_websocket), 
                timeout=3.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Verify that connection recovery was attempted
    assert failing_mock_websocket.message_counts["errors"] > 0, "Should encounter errors"
    
    # Check if recovery messages were sent
    recovery_messages = [
        msg for msg in failing_mock_websocket.sent_messages 
        if isinstance(msg, str) and "recovery" in msg.lower()
    ]
    assert len(recovery_messages) > 0, "Should send recovery messages"


@pytest.mark.asyncio
async def test_silence_handling_in_greeting_phase(app, stable_mock_websocket, 
                                                stable_mock_realtime, mock_components):
    """Test handling of silence events during greeting phase."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event
    stable_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Configure Realtime processor to generate a silence event immediately
    stable_mock_realtime.events = [{
        "type": "silence_detected",
        "duration": 2.0,
        "timestamp": time.time()
    }]
    
    # Set FSM state to GREETING
    mock_components["fsm_orchestrator"].set_state("test_session", FSMState.GREETING)
    
    # Configure frontline agent to return a greeting
    mock_components["frontline_agent"].responses = {
        "SILENCE_GREETING": "Welcome to Red Bar Sushi! How can I help you today?"
    }
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler with timeout
        try:
            await asyncio.wait_for(
                handle_robust_media_stream(stable_mock_websocket), 
                timeout=2.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Verify that the frontline agent was called to generate a greeting
    assert any(call[1] == "SILENCE_GREETING" for call in mock_components["frontline_agent"].process_calls), \
        "Should call frontline agent with SILENCE_GREETING"
    
    # Verify that greeting was sent
    greeting_messages = [
        json.loads(msg) for msg in stable_mock_websocket.sent_messages 
        if isinstance(msg, str) and "text" in json.loads(msg)
    ]
    greeting_texts = [msg.get("text", "") for msg in greeting_messages]
    assert any("welcome" in text.lower() for text in greeting_texts), \
        "Should send welcome greeting"


@pytest.mark.asyncio
async def test_websocket_stability_under_load(app, stable_mock_websocket, 
                                           unstable_mock_realtime, mock_components):
    """Test WebSocket stability under load with multiple events."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event
    stable_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Add a large number of audio chunks
    for i in range(50):
        stable_mock_websocket.test_inputs.append(
            json.dumps({
                "event": "media",
                "media": {
                    "payload": base64.b64encode(f"audio_chunk_{i}".encode()).decode()
                }
            })
        )
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=unstable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler with longer timeout
        try:
            await asyncio.wait_for(
                handle_robust_media_stream(stable_mock_websocket), 
                timeout=5.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check audio processing stats
    assert len(unstable_mock_realtime.processed_audio) > 0, "Should process audio chunks"
    assert unstable_mock_realtime.event_count > 0, "Should generate events"
    
    # Check if system handled various event types
    response_messages = [json.loads(msg) for msg in stable_mock_websocket.sent_messages if isinstance(msg, str)]
    
    # Count event types
    event_types = {}
    for msg in response_messages:
        event_type = msg.get("type") or msg.get("event", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    # Check if multiple types of events were handled
    assert len(event_types) >= 3, f"Should handle multiple event types, got: {event_types}"
    
    # Specifically check for error handling
    error_responses = [msg for msg in response_messages if "error" in msg.get("type", "").lower() 
                      or "error" in msg.get("event", "").lower()]
    
    if unstable_mock_realtime.generate_errors:
        assert len(error_responses) > 0, "Should handle error events"


@pytest.mark.asyncio
async def test_connection_monitoring_and_health_tracking(app, failing_mock_websocket, 
                                                       stable_mock_realtime, mock_components):
    """Test connection health monitoring and reporting."""
    # Import our target handler and connection manager
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream, active_connections
    
    # Set up mock WebSocket with a start event
    failing_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Add audio chunks
    for i in range(10):
        failing_mock_websocket.test_inputs.append(
            json.dumps({
                "event": "media",
                "media": {
                    "payload": base64.b64encode(f"audio_chunk_{i}".encode()).decode()
                }
            })
        )
    
    # Use a session ID we can track
    test_session_id = str(uuid.uuid4())
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler with timeout
        try:
            # Pass our test session ID to track connection
            await asyncio.wait_for(
                handle_robust_media_stream(failing_mock_websocket, session_id=test_session_id), 
                timeout=3.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Verify that health monitoring messages were sent
    status_messages = [
        msg for msg in failing_mock_websocket.sent_messages 
        if isinstance(msg, str) and ("status" in msg.lower() or "health" in msg.lower())
    ]
    
    assert len(status_messages) > 0, "Should send status/health messages"
    
    # Check if connection manager properly tracked connection state changes
    if test_session_id in active_connections:
        conn_mgr = active_connections[test_session_id]
        assert len(conn_mgr.health_log) > 0, "Should log health events"
        
        # Check for state transitions 
        state_changes = [event for event in conn_mgr.health_log if event["type"] == "STATE"]
        assert len(state_changes) > 0, "Should record state transitions"
        
        # Verify connection went through expected states
        state_sequence = [event["data"]["new_state"] for event in state_changes]
        expected_states = ["established", "authenticated"]
        
        for expected in expected_states:
            assert any(expected in state for state in state_sequence), \
                f"Connection should transition through {expected} state"


@pytest.mark.asyncio
async def test_abrupt_disconnection_handling(app, disconnecting_mock_websocket, 
                                           stable_mock_realtime, mock_components):
    """Test handling of abrupt disconnections without recovery."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event
    disconnecting_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Add audio chunks
    for i in range(20):
        disconnecting_mock_websocket.test_inputs.append(
            json.dumps({
                "event": "media",
                "media": {
                    "payload": base64.b64encode(f"audio_chunk_{i}".encode()).decode()
                }
            })
        )
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Call WebSocket handler (should complete when connection fails)
        await handle_robust_media_stream(disconnecting_mock_websocket)
    
    # The connection should be closed
    assert disconnecting_mock_websocket.connected is False, "Connection should be closed"
    
    # Verify that goodbye message was sent before disconnection
    sent_messages = [json.loads(msg) for msg in disconnecting_mock_websocket.sent_messages 
                    if isinstance(msg, str)]
    
    goodbye_messages = [msg for msg in sent_messages 
                       if msg.get("type") == "goodbye" or msg.get("event") == "goodbye"]
    
    # We might not have a goodbye if connection dropped abruptly
    if len(goodbye_messages) == 0:
        # Check for error messages instead
        error_messages = [msg for msg in sent_messages 
                         if "error" in msg.get("type", "").lower() or "error" in msg.get("event", "").lower()]
        assert len(error_messages) > 0, "Should send error messages on connection problems"


@pytest.mark.asyncio
async def test_vad_context_adaptation(app, stable_mock_websocket, 
                                    stable_mock_realtime, mock_components):
    """Test that VAD settings adapt based on conversation context."""
    # Import our target handler
    from app.routes.voice.realtime.robust_stream_handler import handle_robust_media_stream
    
    # Set up mock WebSocket with a start event
    stable_mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "streamSid": "test-stream-sid",
            "callSid": "test-call-sid",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Track VAD configuration changes
    vad_configs = []
    original_configure_vad = stable_mock_realtime.configure_vad
    
    def track_vad_config(config):
        vad_configs.append(config)
        return original_configure_vad(config)
    
    stable_mock_realtime.configure_vad = track_vad_config
    
    # Add a silence event to trigger greeting
    stable_mock_realtime.events = [{
        "type": "silence_detected",
        "duration": 2.0,
        "timestamp": time.time()
    }]
    
    # Configure state transitions to test context adaptation
    async def transition_states(session_id):
        # Wait a bit for initialization
        await asyncio.sleep(0.5)
        
        # Change state to ORDERING and log
        mock_components["fsm_orchestrator"].set_state(session_id, FSMState.ORDERING)
        print(f"Changed state to ORDERING for {session_id}")
        
        # Wait a bit more
        await asyncio.sleep(0.5)
        
        # Change state to CONFIRMATION and log
        mock_components["fsm_orchestrator"].set_state(session_id, FSMState.CONFIRMATION)
        print(f"Changed state to CONFIRMATION for {session_id}")
    
    # Patch the necessary components
    with patch('app.routes.voice.realtime.robust_stream_handler.get_realtime_processor', 
              return_value=stable_mock_realtime), \
         patch('app.routes.voice.realtime.robust_stream_handler.get_global_component', 
              side_effect=lambda name: mock_components.get(name)), \
         patch('app.routes.voice.realtime.robust_stream_handler.FSMState', FSMState):
        
        # Start state transition task
        transition_task = asyncio.create_task(transition_states("test_session"))
        
        # Call WebSocket handler with timeout
        try:
            await asyncio.wait_for(
                handle_robust_media_stream(stable_mock_websocket, session_id="test_session"), 
                timeout=2.0
            )
        except asyncio.TimeoutError:
            pass  # Expected timeout
        
        # Wait for transition task to complete
        await transition_task
    
    # Verify that VAD was configured at least once
    assert len(vad_configs) > 0, "Should configure VAD at least once"
    
    # Verify initial VAD configuration was for greeting
    if vad_configs:
        initial_timeout = vad_configs[0].get("timeout", None)
        assert initial_timeout is not None, "Initial VAD config should have a timeout"


if __name__ == "__main__":
    pytest.main(["-v", __file__])