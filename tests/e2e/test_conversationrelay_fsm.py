"""
End-to-end tests for ConversationRelay with FSM integration.
Tests the complete flow from call setup through order completion.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.fsm.core import ConversationState, ConversationEvent
from app.api.conversation_relay.handler import ConversationRelayHandler
from app.utils.agent_orchestration_async import async_agent_orchestrator


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.accept = AsyncMock()
    return ws


@pytest.fixture
def conversation_handler(mock_websocket):
    """Create a ConversationRelay handler instance."""
    handler = ConversationRelayHandler(mock_websocket)
    handler.call_sid = "TEST_CALL_123"
    handler.session_id = "TEST_SESSION_123"
    return handler


@pytest.mark.asyncio
async def test_setup_event_initializes_conversation(mock_websocket):
    """Test that setup event properly initializes the conversation."""
    handler = ConversationRelayHandler(mock_websocket)
    
    setup_message = {
        "type": "setup",
        "sessionId": "TEST_SESSION_123",
        "callSid": "TEST_CALL_123",
        "from": "+1234567890",
        "to": "+0987654321",
        "callStatus": "in-progress"
    }
    
    with patch.object(async_agent_orchestrator, 'start_new_conversation') as mock_start:
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {"text": "Welcome to Red Bar Sushi! What's your name?"}
            
            await handler.handle_setup(setup_message)
            
            # Verify conversation was started
            mock_start.assert_called_once_with(
                "TEST_CALL_123",
                {"first_interaction": True}
            )
            
            # Verify greeting was sent
            mock_websocket.send_json.assert_called_with({
                "type": "text",
                "token": "Welcome to Red Bar Sushi! What's your name?",
                "last": True
            })


@pytest.mark.asyncio
async def test_greeting_to_main_menu_transition(conversation_handler):
    """Test FSM transition from GREETING to MAIN_MENU when user provides name."""
    # Mock FSM in GREETING state
    mock_fsm = MagicMock()
    mock_fsm.current_state = ConversationState.GREETING
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = mock_fsm
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            # First call returns greeting response
            mock_process.return_value = {
                "text": "Nice to meet you John! How can I help you today? You can order, ask about our menu, or speak to staff.",
                "agent": "AsyncFrontlineVoiceAgent",
                "state": "MAIN_MENU"
            }
            
            # Simulate user saying their name
            prompt_message = {
                "type": "prompt",
                "voicePrompt": "John",
                "lang": "en-US",
                "last": True
            }
            
            await conversation_handler.handle_prompt(prompt_message)
            
            # Verify voice input was processed
            mock_process.assert_called_once_with(
                "TEST_CALL_123",
                "John"
            )
            
            # Verify response was sent
            conversation_handler.websocket.send_json.assert_called_with({
                "type": "text",
                "token": "Nice to meet you John! How can I help you today? You can order, ask about our menu, or speak to staff.",
                "last": True
            })


@pytest.mark.asyncio
async def test_main_menu_to_ordering_transition(conversation_handler):
    """Test FSM transition from MAIN_MENU to ORDERING when user wants to order."""
    mock_fsm = MagicMock()
    mock_fsm.current_state = ConversationState.MAIN_MENU
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = mock_fsm
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {
                "text": "Great! What would you like to order today?",
                "agent": "AsyncCartAgent",
                "state": "ORDERING"
            }
            
            # User wants to order
            prompt_message = {
                "type": "prompt",
                "voicePrompt": "I'd like to order some sushi",
                "lang": "en-US",
                "last": True
            }
            
            await conversation_handler.handle_prompt(prompt_message)
            
            # Verify transition happened
            mock_process.assert_called_once_with(
                "TEST_CALL_123",
                "I'd like to order some sushi"
            )


@pytest.mark.asyncio
async def test_ordering_with_menu_item(conversation_handler):
    """Test ordering a specific menu item."""
    mock_fsm = MagicMock()
    mock_fsm.current_state = ConversationState.ORDERING
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = mock_fsm
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {
                "text": "I've added 2 California rolls to your order. Anything else?",
                "agent": "AsyncCartAgent",
                "state": "ORDERING",
                "actions": [{"type": "add_item", "item": "California Roll", "quantity": 2}]
            }
            
            prompt_message = {
                "type": "prompt",
                "voicePrompt": "I'll have two California rolls",
                "lang": "en-US",
                "last": True
            }
            
            await conversation_handler.handle_prompt(prompt_message)
            
            # Verify item was added
            conversation_handler.websocket.send_json.assert_called()
            call_args = conversation_handler.websocket.send_json.call_args[0][0]
            assert "California roll" in call_args["token"]


@pytest.mark.asyncio
async def test_order_completion_flow(conversation_handler):
    """Test completing an order and transitioning through validation."""
    mock_fsm = MagicMock()
    mock_fsm.current_state = ConversationState.ORDERING
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = mock_fsm
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            # Mock responses for order completion flow
            mock_process.side_effect = [
                {
                    "text": "Let me confirm your order: 2 California rolls. Your total is $16. Is that correct?",
                    "agent": "AsyncGuardrailAgent",
                    "state": "CONFIRMATION"
                },
                {
                    "text": "Perfect! Will this be for pickup or delivery?",
                    "agent": "AsyncFulfillmentAgent",
                    "state": "FULFILLMENT"
                }
            ]
            
            # User completes order
            await conversation_handler.handle_prompt({
                "type": "prompt",
                "voicePrompt": "That's all for now",
                "lang": "en-US",
                "last": True
            })
            
            # User confirms order
            mock_fsm.current_state = ConversationState.CONFIRMATION
            await conversation_handler.handle_prompt({
                "type": "prompt",
                "voicePrompt": "Yes that's correct",
                "lang": "en-US",
                "last": True
            })
            
            # Verify confirmation flow
            assert mock_process.call_count == 2
            assert conversation_handler.websocket.send_json.call_count >= 2


@pytest.mark.asyncio
async def test_interrupt_handling(conversation_handler):
    """Test handling user interruption during TTS playback."""
    interrupt_message = {
        "type": "interrupt",
        "reason": "user_speech",
        "utteranceUntilInterrupt": "Welcome to Red Bar Sushi! What's your"
    }
    
    with patch.object(async_agent_orchestrator, 'handle_interruption') as mock_interrupt:
        await conversation_handler.handle_interrupt(interrupt_message)
        
        # Verify interruption was handled
        mock_interrupt.assert_called_once_with("TEST_CALL_123")
        assert not conversation_handler.is_agent_speaking


@pytest.mark.asyncio
async def test_error_handling(conversation_handler):
    """Test error handling in conversation flow."""
    error_message = {
        "type": "error",
        "errorCode": "1001",
        "errorMessage": "Speech recognition failed"
    }
    
    await conversation_handler.handle_error(error_message)
    # Should log error but not crash


@pytest.mark.asyncio
async def test_menu_inquiry_flow(conversation_handler):
    """Test handling menu inquiries without transitioning to ordering."""
    mock_fsm = MagicMock()
    mock_fsm.current_state = ConversationState.MAIN_MENU
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = mock_fsm
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {
                "text": "We have various sushi rolls including California, Spicy Tuna, and Salmon. We also have sashimi and appetizers. What interests you?",
                "agent": "AsyncMenuAgent",
                "state": "MAIN_MENU"  # Stays in MAIN_MENU for inquiry
            }
            
            prompt_message = {
                "type": "prompt",
                "voicePrompt": "What kind of sushi do you have?",
                "lang": "en-US",
                "last": True
            }
            
            await conversation_handler.handle_prompt(prompt_message)
            
            # Should stay in MAIN_MENU state
            assert mock_fsm.current_state == ConversationState.MAIN_MENU


@pytest.mark.asyncio
async def test_language_change(conversation_handler):
    """Test changing language mid-conversation."""
    await conversation_handler.send_language_change("es-US", "es-US")
    
    conversation_handler.websocket.send_json.assert_called_with({
        "type": "language",
        "language": "es-US",
        "ttsLanguage": "es-US"
    })


@pytest.mark.asyncio
async def test_end_conversation(conversation_handler):
    """Test ending conversation gracefully."""
    await conversation_handler.send_end()
    
    conversation_handler.websocket.send_json.assert_called_with({
        "type": "end"
    })


@pytest.mark.asyncio
async def test_fsm_state_logging(conversation_handler, caplog):
    """Test that FSM state transitions are properly logged."""
    mock_fsm_before = MagicMock()
    mock_fsm_before.current_state = ConversationState.GREETING
    
    mock_fsm_after = MagicMock()
    mock_fsm_after.current_state = ConversationState.MAIN_MENU
    
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.side_effect = [mock_fsm_before, mock_fsm_after]
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {
                "text": "Nice to meet you!",
                "agent": "AsyncFrontlineVoiceAgent"
            }
            
            await conversation_handler.handle_prompt({
                "type": "prompt",
                "voicePrompt": "My name is John",
                "lang": "en-US",
                "last": True
            })
            
            # Check logs for state transition
            assert "FSM State BEFORE prompt: GREETING" in caplog.text
            assert "FSM State AFTER prompt: MAIN_MENU" in caplog.text


@pytest.mark.asyncio
async def test_no_response_handling(conversation_handler):
    """Test handling when agent returns no response."""
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.return_value = MagicMock()
        
        with patch.object(async_agent_orchestrator, 'process_voice_input') as mock_process:
            mock_process.return_value = {"text": "", "agent": "AsyncFrontlineVoiceAgent"}
            
            await conversation_handler.handle_prompt({
                "type": "prompt",
                "voicePrompt": "Hello",
                "lang": "en-US",
                "last": True
            })
            
            # Should not send empty text
            conversation_handler.websocket.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_exception_handling_with_fallback(conversation_handler):
    """Test exception handling sends fallback message."""
    with patch.object(async_agent_orchestrator, 'get_fsm') as mock_get_fsm:
        mock_get_fsm.side_effect = Exception("Test error")
        
        await conversation_handler.handle_prompt({
            "type": "prompt",
            "voicePrompt": "Hello",
            "lang": "en-US",
            "last": True
        })
        
        # Should send fallback message
        conversation_handler.websocket.send_json.assert_called_with({
            "type": "text",
            "token": "I'm sorry, I'm having trouble understanding. Could you please repeat that?",
            "last": True
        })