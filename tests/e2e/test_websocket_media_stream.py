"""
End-to-end tests for WebSocket media streaming with Twilio.
Tests the WebSocket connection handling for ConversationRelay.
"""

import pytest
import asyncio
import json
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket
from fastapi.testclient import TestClient

from app.main import app
from app.api.conversation_relay.handler import ConversationRelayHandler


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.receive_queue = asyncio.Queue()
        
    async def accept(self):
        self.accepted = True
        
    async def send_json(self, data):
        self.sent_messages.append(("json", data))
        
    async def send_bytes(self, data):
        self.sent_messages.append(("bytes", data))
        
    async def receive_json(self):
        return await self.receive_queue.get()
        
    async def close(self, code=1000):
        self.closed = True
        self.close_code = code
        
    async def add_test_message(self, message):
        """Add a message to be received."""
        await self.receive_queue.put(message)


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def mock_websocket():
    """Create mock WebSocket."""
    return MockWebSocket()


@pytest.mark.asyncio
async def test_websocket_connection_accepted(mock_websocket):
    """Test WebSocket connection is properly accepted."""
    handler = ConversationRelayHandler(mock_websocket)
    
    # Simulate connection
    await mock_websocket.accept()
    
    assert mock_websocket.accepted is True


@pytest.mark.asyncio
async def test_setup_event_processing(mock_websocket):
    """Test processing of setup event from Twilio."""
    handler = ConversationRelayHandler(mock_websocket)
    
    setup_event = {
        "type": "setup",
        "sessionId": "ES123",
        "callSid": "CA123",
        "from": "+1234567890",
        "to": "+0987654321",
        "callStatus": "in-progress",
        "direction": "inbound"
    }
    
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator') as mock_orch:
        await handler.handle_setup(setup_event)
        
        # Verify session data was stored
        assert handler.session_id == "ES123"
        assert handler.call_sid == "CA123"
        assert handler.from_number == "+1234567890"
        
        # Verify orchestrator was initialized
        mock_orch.start_new_conversation.assert_called_once()


@pytest.mark.asyncio
async def test_prompt_event_to_text_response(mock_websocket):
    """Test converting voice prompt to text response."""
    handler = ConversationRelayHandler(mock_websocket)
    handler.call_sid = "CA123"
    
    prompt_event = {
        "type": "prompt",
        "voicePrompt": "I'd like to order some sushi",
        "lang": "en-US",
        "last": True
    }
    
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.process_voice_input') as mock_process:
        mock_process.return_value = {
            "text": "Great! What kind of sushi would you like?",
            "agent": "AsyncCartAgent"
        }
        
        await handler.handle_prompt(prompt_event)
        
        # Verify agent was called
        mock_process.assert_called_with("CA123", "I'd like to order some sushi")
        
        # Verify text response was sent
        assert len(mock_websocket.sent_messages) == 1
        msg_type, msg_data = mock_websocket.sent_messages[0]
        assert msg_type == "json"
        assert msg_data["type"] == "text"
        assert msg_data["token"] == "Great! What kind of sushi would you like?"
        assert msg_data["last"] is True


@pytest.mark.asyncio
async def test_interrupt_event_handling(mock_websocket):
    """Test handling user interruption."""
    handler = ConversationRelayHandler(mock_websocket)
    handler.call_sid = "CA123"
    handler.is_agent_speaking = True
    
    interrupt_event = {
        "type": "interrupt",
        "reason": "user_speech",
        "utteranceUntilInterrupt": "Great! What kind of"
    }
    
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.handle_interruption') as mock_interrupt:
        await handler.handle_interrupt(interrupt_event)
        
        # Verify interruption was handled
        mock_interrupt.assert_called_with("CA123")
        assert handler.is_agent_speaking is False


@pytest.mark.asyncio
async def test_dtmf_event_handling(mock_websocket):
    """Test DTMF digit handling."""
    handler = ConversationRelayHandler(mock_websocket)
    
    dtmf_event = {
        "type": "dtmf",
        "digit": "1"
    }
    
    # Should handle without error
    await handler.handle_dtmf(dtmf_event)


@pytest.mark.asyncio
async def test_error_event_logging(mock_websocket, caplog):
    """Test error event logging."""
    handler = ConversationRelayHandler(mock_websocket)
    
    error_event = {
        "type": "error",
        "errorCode": "1001",
        "errorMessage": "Speech recognition failed"
    }
    
    await handler.handle_error(error_event)
    
    # Check error was logged
    assert "Twilio error - Code: 1001" in caplog.text


@pytest.mark.asyncio
async def test_language_change_message(mock_websocket):
    """Test sending language change message."""
    handler = ConversationRelayHandler(mock_websocket)
    
    await handler.send_language_change("es-US", "es-MX")
    
    assert len(mock_websocket.sent_messages) == 1
    msg_type, msg_data = mock_websocket.sent_messages[0]
    assert msg_data["type"] == "language"
    assert msg_data["language"] == "es-US"
    assert msg_data["ttsLanguage"] == "es-MX"


@pytest.mark.asyncio
async def test_play_audio_message(mock_websocket):
    """Test sending play audio message."""
    handler = ConversationRelayHandler(mock_websocket)
    
    await handler.send_play_audio("https://example.com/hold-music.mp3")
    
    assert len(mock_websocket.sent_messages) == 1
    msg_type, msg_data = mock_websocket.sent_messages[0]
    assert msg_data["type"] == "play"
    assert msg_data["audioUrl"] == "https://example.com/hold-music.mp3"


@pytest.mark.asyncio
async def test_end_conversation_message(mock_websocket):
    """Test sending end conversation message."""
    handler = ConversationRelayHandler(mock_websocket)
    
    await handler.send_end()
    
    assert len(mock_websocket.sent_messages) == 1
    msg_type, msg_data = mock_websocket.sent_messages[0]
    assert msg_data["type"] == "end"


@pytest.mark.asyncio
async def test_empty_prompt_handling(mock_websocket):
    """Test handling empty voice prompts."""
    handler = ConversationRelayHandler(mock_websocket)
    handler.call_sid = "CA123"
    
    prompt_event = {
        "type": "prompt",
        "voicePrompt": "",
        "lang": "en-US",
        "last": True
    }
    
    await handler.handle_prompt(prompt_event)
    
    # Should not send any response for empty prompt
    assert len(mock_websocket.sent_messages) == 0


@pytest.mark.asyncio
async def test_exception_handling_with_fallback(mock_websocket):
    """Test exception handling sends fallback message."""
    handler = ConversationRelayHandler(mock_websocket)
    handler.call_sid = "CA123"
    
    prompt_event = {
        "type": "prompt",
        "voicePrompt": "Hello",
        "lang": "en-US",
        "last": True
    }
    
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.process_voice_input') as mock_process:
        mock_process.side_effect = Exception("Test error")
        
        await handler.handle_prompt(prompt_event)
        
        # Should send fallback message
        assert len(mock_websocket.sent_messages) == 1
        msg_type, msg_data = mock_websocket.sent_messages[0]
        assert "I'm sorry, I'm having trouble understanding" in msg_data["token"]


@pytest.mark.asyncio
async def test_multiple_text_tokens(mock_websocket):
    """Test sending multiple text tokens for streaming."""
    handler = ConversationRelayHandler(mock_websocket)
    
    # Send multiple tokens
    await handler.send_text("Hello", is_last=False)
    await handler.send_text(" there!", is_last=True)
    
    assert len(mock_websocket.sent_messages) == 2
    
    # First token
    _, msg1 = mock_websocket.sent_messages[0]
    assert msg1["token"] == "Hello"
    assert msg1["last"] is False
    
    # Second token
    _, msg2 = mock_websocket.sent_messages[1]
    assert msg2["token"] == " there!"
    assert msg2["last"] is True


@pytest.mark.asyncio
async def test_welcome_greeting_detection(mock_websocket):
    """Test detection of welcomeGreeting in setup."""
    handler = ConversationRelayHandler(mock_websocket)
    
    setup_event = {
        "type": "setup",
        "sessionId": "ES123",
        "callSid": "CA123",
        "welcomeGreeting": "Welcome to Red Bar Sushi!"
    }
    
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator') as mock_orch:
        await handler.handle_setup(setup_event)
        
        # Should not send initial greeting if welcomeGreeting is present
        mock_orch.process_voice_input.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_flow_simulation(mock_websocket):
    """Test a complete conversation flow."""
    handler = ConversationRelayHandler(mock_websocket)
    
    # Setup
    await handler.handle_setup({
        "type": "setup",
        "sessionId": "ES123",
        "callSid": "CA123"
    })
    
    # Customer says name
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.process_voice_input') as mock_process:
        mock_process.return_value = {"text": "Nice to meet you John!"}
        
        await handler.handle_prompt({
            "type": "prompt",
            "voicePrompt": "My name is John"
        })
    
    # Customer orders
    with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.process_voice_input') as mock_process:
        mock_process.return_value = {"text": "I've added 2 California rolls to your order."}
        
        await handler.handle_prompt({
            "type": "prompt",
            "voicePrompt": "I'll have two California rolls"
        })
    
    # Verify conversation progressed
    assert len(mock_websocket.sent_messages) >= 2
    
    # End conversation
    await handler.send_end()
    
    # Verify end was sent
    last_msg = mock_websocket.sent_messages[-1]
    assert last_msg[1]["type"] == "end"