"""
Integration tests for ConversationRelay webhook handling.
Tests the webhook processing without making real Twilio calls.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def conversation_relay_payload():
    """Sample ConversationRelay webhook payload from Twilio."""
    return {
        "sequenceNumber": "1",
        "accountSid": "AC123456",
        "callSid": "CA123456",
        "from": "+15555551234",
        "to": "+15555556789",
        "direction": "inbound",
        "callStatus": "in-progress",
        "conversationSid": "CX123456",
        "prompt": {
            "text": "Hello, I'd like to order some sushi",
            "language": "en-US",
            "isFinal": True
        }
    }


@pytest.fixture
def mock_agent_orchestrator():
    """Mock agent orchestrator for integration tests."""
    orchestrator = AsyncMock()
    orchestrator.process_voice_input = AsyncMock(return_value={
        "text": "Welcome to Red Bar Sushi! I'd be happy to help you order.",
        "requires_response": True,
        "agent_name": "frontline"
    })
    orchestrator.get_fsm = AsyncMock()
    orchestrator.get_fsm.return_value.current_state.name = "GREETING"
    return orchestrator


@pytest.mark.asyncio
async def test_conversation_relay_webhook(client, conversation_relay_payload, mock_agent_orchestrator):
    """Test ConversationRelay webhook processing."""
    with patch('app.api.conversation_relay.handler.async_agent_orchestrator', mock_agent_orchestrator):
        response = client.post(
            "/api/conversation-relay",
            json=conversation_relay_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "say" in data
        assert data["say"]["text"] == "Welcome to Red Bar Sushi! I'd be happy to help you order."
        assert data["say"]["language"] == "en-US"
        assert data["listen"] == True
        
        # Verify orchestrator was called correctly
        mock_agent_orchestrator.process_voice_input.assert_called_once_with(
            call_sid="CA123456",
            transcript="Hello, I'd like to order some sushi",
            language="en-US",
            is_final=True
        )


@pytest.mark.asyncio
async def test_conversation_relay_greeting(client, mock_agent_orchestrator):
    """Test initial greeting when conversation starts."""
    payload = {
        "sequenceNumber": "0",
        "callSid": "CA123456",
        "conversationSid": "CX123456",
        "callStatus": "in-progress"
    }
    
    with patch('app.api.conversation_relay.handler.async_agent_orchestrator', mock_agent_orchestrator):
        response = client.post(
            "/api/conversation-relay",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "say" in data
        assert "Red Bar Sushi" in data["say"]["text"]


@pytest.mark.asyncio
async def test_conversation_relay_error_handling(client):
    """Test error handling in ConversationRelay."""
    # Send invalid payload
    response = client.post(
        "/api/conversation-relay",
        json={"invalid": "payload"}
    )
    
    # Should handle gracefully
    assert response.status_code == 200
    data = response.json()
    assert "say" in data
    assert "trouble" in data["say"]["text"].lower()


@pytest.mark.asyncio
async def test_conversation_relay_hangup(client, mock_agent_orchestrator):
    """Test handling of call hangup."""
    payload = {
        "sequenceNumber": "10",
        "callSid": "CA123456",
        "callStatus": "completed"
    }
    
    with patch('app.api.conversation_relay.handler.async_agent_orchestrator', mock_agent_orchestrator):
        response = client.post(
            "/api/conversation-relay",
            json=payload
        )
        
        assert response.status_code == 200
        
        # Verify FSM cleanup was triggered
        mock_agent_orchestrator.remove_fsm.assert_called_with("CA123456")


@pytest.mark.asyncio
async def test_conversation_relay_with_fsm_states(client, mock_agent_orchestrator):
    """Test ConversationRelay logs FSM states correctly."""
    # Mock different FSM states
    fsm_mock = AsyncMock()
    fsm_mock.current_state.name = "ORDERING"
    mock_agent_orchestrator.get_fsm.return_value = fsm_mock
    
    payload = {
        "sequenceNumber": "5",
        "callSid": "CA123456",
        "prompt": {
            "text": "I want two California rolls",
            "language": "en-US",
            "isFinal": True
        }
    }
    
    with patch('app.api.conversation_relay.handler.async_agent_orchestrator', mock_agent_orchestrator):
        response = client.post(
            "/api/conversation-relay",
            json=payload
        )
        
        assert response.status_code == 200
        
        # Verify FSM state was checked
        mock_agent_orchestrator.get_fsm.assert_called()


@pytest.mark.asyncio
async def test_conversation_relay_language_support(client, mock_agent_orchestrator):
    """Test different language handling."""
    payload = {
        "sequenceNumber": "1",
        "callSid": "CA123456",
        "prompt": {
            "text": "Hola, quiero ordenar sushi",
            "language": "es-US",
            "isFinal": True
        }
    }
    
    with patch('app.api.conversation_relay.handler.async_agent_orchestrator', mock_agent_orchestrator):
        response = client.post(
            "/api/conversation-relay",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["say"]["language"] == "es-US"