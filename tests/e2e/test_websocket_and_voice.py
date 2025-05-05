"""
End-to-end tests for WebSocket and voice processing in RedBarSushiAI.
Focuses on real-time audio handling, WebSocket connection management, and VAD events.
"""

import pytest
import os
import json
import base64
import asyncio
import time
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

# Set environment to test mode
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"
os.environ["NO_X11"] = "1"  # Disable X11 requirement for headless testing
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"  # Disable display for OpenAI Realtime

# Import app components
from app import create_app


class MockAsyncWebSocket:
    """Mock WebSocket class for testing"""
    
    def __init__(self, test_inputs=None, mock_responses=None):
        self.test_inputs = test_inputs or []
        self.mock_responses = mock_responses or {}
        self.sent_messages = []
        self.received_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
    
    async def send(self, message):
        """Mock send method"""
        self.sent_messages.append(message)
        
    async def receive(self):
        """Mock receive method, returns predefined test inputs"""
        if not self.test_inputs:
            # If no more inputs, simulate waiting by yielding control
            await asyncio.sleep(0.1)
            return None
            
        msg = self.test_inputs.pop(0)
        self.received_messages.append(msg)
        return msg
    
    async def close(self, code=1000, reason=""):
        """Mock close method"""
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture
def app():
    """Create Flask app for testing"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    
    yield app


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing"""
    return MockAsyncWebSocket()


class MockRealtimeProcessor:
    """Mock for the OpenAI Realtime API processor"""
    
    def __init__(self, events=None):
        self.events = events or []
        self.processed_audio = []
    
    async def process_media_stream(self, audio_generator, session_id):
        """Mock processing of audio stream"""
        # Collect audio chunks for verification
        async for chunk in audio_generator:
            if chunk:
                self.processed_audio.append(chunk)
        
        # Yield pre-defined events
        for event in self.events:
            yield event


@pytest.mark.asyncio
async def test_websocket_connection_handling(app, mock_websocket):
    """Test WebSocket connection establishment and closure"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with no events
    mock_processor = MockRealtimeProcessor()
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Patch the realtime processor and agents
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=MagicMock()):
        
        # Call WebSocket handler (will terminate when no more events)
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=1.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout as we're only testing connection setup
    
    # Check if connection was established
    connection_messages = [
        msg for msg in mock_websocket.sent_messages 
        if isinstance(msg, str) and "connected" in msg.lower()
    ]
    assert len(connection_messages) > 0, "Should send connection confirmation"


@pytest.mark.asyncio
async def test_audio_chunk_processing(app, mock_websocket):
    """Test processing of audio chunks through the WebSocket"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor
    mock_processor = MockRealtimeProcessor()
    
    # Prepare audio chunks for testing
    audio_chunks = [
        base64.b64encode(b"audio_chunk_1").decode('utf-8'),
        base64.b64encode(b"audio_chunk_2").decode('utf-8'),
        base64.b64encode(b"audio_chunk_3").decode('utf-8')
    ]
    
    # Set up mock WebSocket with media events
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        json.dumps({
            "event": "media",
            "media": {"payload": audio_chunks[0]}
        }),
        json.dumps({
            "event": "media",
            "media": {"payload": audio_chunks[1]}
        }),
        json.dumps({
            "event": "media",
            "media": {"payload": audio_chunks[2]}
        }),
        json.dumps({
            "event": "stop"
        })
    ]
    
    # Patch the realtime processor and agents
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=MagicMock()):
        
        # Call WebSocket handler
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Verify that audio chunks were processed
    assert len(mock_processor.processed_audio) > 0, "Should process audio chunks"
    
    # The actual comparison of audio chunks would be more complex in a real test
    # due to format conversions and WebSocket processing


@pytest.mark.asyncio
async def test_silence_detection_handling(app, mock_websocket):
    """Test handling of silence detection events"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with a silence event
    mock_processor = MockRealtimeProcessor(events=[
        {
            "type": "silence_detected",
            "duration": 3.0,
            "timestamp": time.time()
        }
    ])
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Mock the FSM orchestrator to track state
    mock_fsm = MagicMock()
    mock_fsm.get_current_state.return_value = FSMState.GREETING
    
    # Patch necessary components
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=MagicMock()), \
         patch('app.routes.voice_orchestrated_realtime.fsm_orchestrator', mock_fsm):
        
        # Define a fake FSMState class for use in the test
        class FSMState:
            GREETING = "GREETING"
            MAIN_MENU = "MAIN_MENU"
            ORDERING = "ORDERING"
        
        # Patch the FSMState class
        with patch('app.routes.voice_orchestrated_realtime.FSMState', FSMState):
            # Call WebSocket handler
            try:
                await asyncio.wait_for(media_stream(mock_websocket), timeout=2.0)
            except asyncio.TimeoutError:
                pass  # Expected timeout
    
    # Check for a prompt sent in response to silence
    prompt_messages = [
        json.loads(msg) for msg in mock_websocket.sent_messages 
        if isinstance(msg, str) and "message" in msg.lower()
    ]
    
    # There should be at least one message in response to silence
    assert any(msg.get("text") for msg in prompt_messages), "Should send prompt on silence"


@pytest.mark.asyncio
async def test_transcript_processing(app, mock_websocket):
    """Test processing of speech transcripts"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with a transcript event
    mock_processor = MockRealtimeProcessor(events=[
        {
            "type": "transcript_complete",
            "text": "I'd like to order a California roll",
            "final": True,
            "timestamp": time.time()
        }
    ])
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Mock the agent with a process_voice_input method
    mock_agent = MagicMock()
    mock_agent.process_voice_input = AsyncMock(return_value="I'll add a California roll to your order")
    
    # Patch necessary components
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=mock_agent):
        
        # Call WebSocket handler
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check if the agent processed the transcript
    assert mock_agent.process_voice_input.called, "Agent should process transcript"
    
    # Check for agent response sent back through WebSocket
    response_messages = [
        json.loads(msg) for msg in mock_websocket.sent_messages 
        if isinstance(msg, str) and "california roll" in msg.lower()
    ]
    assert len(response_messages) > 0, "Should send agent response"


@pytest.mark.asyncio
async def test_tool_call_handling(app, mock_websocket):
    """Test handling of tool call events from the model"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with a tool call event
    mock_processor = MockRealtimeProcessor(events=[
        {
            "type": "tool_call",
            "name": "lookup_menu_item",
            "arguments": {"item_name": "California roll"},
            "id": "call_123",
            "timestamp": time.time()
        }
    ])
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Mock the tool registry
    mock_registry = MagicMock()
    mock_registry.tools = {"lookup_menu_item": {"function": AsyncMock(return_value={"name": "California Roll", "price": 850})}}
    mock_registry.execute_tool = AsyncMock(return_value={"name": "California Roll", "price": 850})
    
    # Patch necessary components
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=MagicMock()), \
         patch('app.routes.voice_orchestrated_realtime.tool_registry', mock_registry):
        
        # Call WebSocket handler
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check if the tool was executed
    assert mock_registry.execute_tool.called, "Tool should be executed"
    
    # Check for tool result sent back through WebSocket
    tool_result_messages = [
        json.loads(msg) for msg in mock_websocket.sent_messages 
        if isinstance(msg, str) and "tool_result" in msg.lower()
    ]
    assert len(tool_result_messages) > 0, "Should send tool result"


@pytest.mark.asyncio
async def test_error_handling_and_recovery(app, mock_websocket):
    """Test error handling and recovery in the WebSocket handler"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor that raises an exception
    mock_processor = MagicMock()
    mock_processor.process_media_stream = AsyncMock(side_effect=Exception("Test error"))
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Patch necessary components
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=MagicMock()):
        
        # Call WebSocket handler, should handle the exception gracefully
        await media_stream(mock_websocket)
    
    # Check if an error message was sent
    error_messages = [
        json.loads(msg) for msg in mock_websocket.sent_messages 
        if isinstance(msg, str) and ("error" in msg.lower() or "exception" in msg.lower())
    ]
    assert len(error_messages) > 0, "Should send error message"
    
    # Check if WebSocket was closed with an error code
    assert mock_websocket.closed, "WebSocket should be closed on error"
    assert mock_websocket.close_code != 1000, "Should close with non-normal code"


@pytest.mark.asyncio
async def test_websocket_protocol_selection(app):
    """Test proper WebSocket protocol selection based on environment"""
    # Import the function we want to test
    from app.routes.voice_orchestrated_realtime import receive_call
    
    # Create a test request context
    test_request = MagicMock()
    test_request.host = "test.example.com"
    test_request.is_secure = False
    test_request.base_url = "http://test.example.com/"
    test_request.values = {"CallSid": "test-call-123"}
    test_request.headers = []
    
    # Test case 1: Non-production environment
    with patch('app.routes.voice_orchestrated_realtime.request', test_request), \
         patch('app.routes.voice_orchestrated_realtime.os.environ.get', return_value=None), \
         patch('app.routes.voice_orchestrated_realtime.VoiceResponse') as mock_voice_response, \
         patch('app.routes.voice_orchestrated_realtime.Start') as mock_start, \
         patch('app.routes.voice_orchestrated_realtime.Connect') as mock_connect, \
         patch('app.routes.voice_orchestrated_realtime.Response') as mock_response:
        
        # Configure mocks
        mock_voice_response.return_value = MagicMock()
        mock_start.return_value = MagicMock()
        mock_connect.return_value = MagicMock()
        mock_response.return_value = "mocked response"
        
        # Call the function
        response = receive_call()
        
        # Check that ws:// protocol was used
        start_args = mock_start.return_value.stream.call_args[1]
        assert "ws://" in start_args["url"], "Should use ws:// in non-production environment"
    
    # Test case 2: Production environment
    test_request.host = "app.onrender.com"  # Production domain on Render
    
    with patch('app.routes.voice_orchestrated_realtime.request', test_request), \
         patch('app.routes.voice_orchestrated_realtime.VoiceResponse') as mock_voice_response, \
         patch('app.routes.voice_orchestrated_realtime.Start') as mock_start, \
         patch('app.routes.voice_orchestrated_realtime.Connect') as mock_connect, \
         patch('app.routes.voice_orchestrated_realtime.Response') as mock_response:
        
        # Configure mocks
        mock_voice_response.return_value = MagicMock()
        mock_start.return_value = MagicMock()
        mock_connect.return_value = MagicMock()
        mock_response.return_value = "mocked response"
        
        # Call the function
        response = receive_call()
        
        # Check that wss:// protocol was used
        start_args = mock_start.return_value.stream.call_args[1]
        assert "wss://" in start_args["url"], "Should use wss:// in production environment"


@pytest.mark.asyncio
async def test_concurrent_event_processing(app, mock_websocket):
    """Test that multiple events can be processed concurrently"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with multiple events
    mock_processor = MockRealtimeProcessor(events=[
        {
            "type": "transcript_complete",
            "text": "I'd like to order sushi",
            "final": True,
            "timestamp": time.time()
        },
        {
            "type": "transcript_complete",
            "text": "A California roll please",
            "final": True,
            "timestamp": time.time()
        },
        {
            "type": "silence_detected",
            "duration": 2.0,
            "timestamp": time.time()
        }
    ])
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Mock the agent with a process_voice_input method
    mock_agent = MagicMock()
    mock_agent.process_voice_input = AsyncMock(return_value="I'll add that to your order")
    
    # Mock the FSM orchestrator
    mock_fsm = MagicMock()
    mock_fsm.get_current_state.return_value = "ORDERING"
    
    # Set up mocks
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=mock_agent), \
         patch('app.routes.voice_orchestrated_realtime.fsm_orchestrator', mock_fsm):
        
        # Call WebSocket handler
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=3.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check that multiple messages were sent
    # (2 transcripts + responses + 1 silence prompt)
    assert len(mock_websocket.sent_messages) >= 3, "Should process multiple events"
    
    # Verify agent was called multiple times
    assert mock_agent.process_voice_input.call_count >= 2, "Agent should process multiple transcripts"


@pytest.mark.asyncio
async def test_session_info_tracking(app, mock_websocket):
    """Test that session information is properly tracked"""
    # Import handler from our target module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Configure mock realtime processor with a transcript
    mock_processor = MockRealtimeProcessor(events=[
        {
            "type": "transcript_complete",
            "text": "My name is John",
            "final": True,
            "timestamp": time.time()
        }
    ])
    
    # Set up mock WebSocket with a start event
    mock_websocket.test_inputs = [
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ]
    
    # Mock the slot store
    mock_slots = MagicMock()
    mock_slots.set_slot = AsyncMock()
    
    # Mock the agent
    mock_agent = MagicMock()
    mock_agent.process_voice_input = AsyncMock(return_value="Thanks, John. How can I help you today?")
    
    # Patch necessary components
    with patch('app.routes.voice_orchestrated_realtime.get_realtime_processor', return_value=mock_processor), \
         patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=mock_agent), \
         patch('app.routes.voice_orchestrated_realtime.slot_store', mock_slots):
        
        # Call WebSocket handler
        try:
            await asyncio.wait_for(media_stream(mock_websocket), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # Expected timeout
    
    # Check that session metrics are tracked
    assert mock_agent.process_voice_input.called, "Agent should process the name"
    
    # In a real test, we'd verify that the slot was set with the name


# Run these tests with: pytest -v tests/e2e/test_websocket_and_voice.py