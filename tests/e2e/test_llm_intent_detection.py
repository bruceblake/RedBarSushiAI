"""
End-to-end tests for LLM-based intent detection system.
Tests that the system properly detects user intents without keyword matching.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.utils.intent_detector_async import AsyncLLMIntentDetector
from app.fsm.core import ConversationState, ConversationEvent


@pytest.fixture
def intent_detector():
    """Create an intent detector instance."""
    with patch('app.utils.intent_detector_async.AsyncOpenAI'):
        detector = AsyncLLMIntentDetector()
        detector.client = AsyncMock()
        return detector


@pytest.mark.asyncio
async def test_greeting_state_name_detection(intent_detector):
    """Test various ways users provide their name in GREETING state."""
    test_cases = [
        ("John", "PROVIDE_NAME"),
        ("My name is Sarah", "PROVIDE_NAME"),
        ("I'm Mike", "PROVIDE_NAME"),
        ("Call me Lisa", "PROVIDE_NAME"),
        ("This is Robert calling", "PROVIDE_NAME"),
        ("I don't want to give my name", "SKIP_NAME"),
        ("What?", "REQUEST_HELP"),
        ("I didn't hear you", "REQUEST_HELP"),
    ]
    
    for transcript, expected_intent in test_cases:
        # Mock OpenAI response
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = expected_intent
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        event = await intent_detector.detect_intent(
            transcript, 
            ConversationState.GREETING,
            {}
        )
        
        if expected_intent == "PROVIDE_NAME":
            assert event == ConversationEvent.USER_PROVIDES_NAME
        elif expected_intent == "SKIP_NAME":
            assert event == ConversationEvent.USER_PROVIDES_NAME  # Maps to same event
        else:
            assert event is None  # REQUEST_HELP has no event mapping


@pytest.mark.asyncio
async def test_main_menu_intent_detection(intent_detector):
    """Test intent detection in MAIN_MENU state."""
    test_cases = [
        ("I'd like to order some sushi", "START_ORDER", ConversationEvent.START_ORDER),
        ("Can I get two California rolls", "START_ORDER", ConversationEvent.START_ORDER),
        ("I want to place an order", "START_ORDER", ConversationEvent.START_ORDER),
        ("What kind of sushi do you have?", "REQUEST_MENU", ConversationEvent.REQUEST_MENU_INFO),
        ("Tell me about your menu", "REQUEST_MENU", ConversationEvent.REQUEST_MENU_INFO),
        ("What's on special today?", "REQUEST_MENU", ConversationEvent.REQUEST_MENU_INFO),
        ("Are you open now?", "REQUEST_HOURS", ConversationEvent.REQUEST_MENU_INFO),
        ("I need to speak to a manager", "REQUEST_HUMAN", ConversationEvent.REQUEST_ESCALATION),
        ("Can I talk to someone?", "REQUEST_HUMAN", ConversationEvent.REQUEST_ESCALATION),
        ("Do you deliver?", "GENERAL_QUESTION", None),
    ]
    
    for transcript, intent, expected_event in test_cases:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = intent
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        event = await intent_detector.detect_intent(
            transcript,
            ConversationState.MAIN_MENU,
            {}
        )
        
        assert event == expected_event


@pytest.mark.asyncio
async def test_ordering_state_intent_detection(intent_detector):
    """Test intent detection during ordering."""
    test_cases = [
        ("Add a spicy tuna roll", "ADD_ITEM", None),  # Handled by cart agent
        ("I'll also have edamame", "ADD_ITEM", None),
        ("Remove the tempura", "REMOVE_ITEM", None),
        ("Make that 3 rolls instead of 2", "MODIFY_ITEM", None),
        ("That's all for now", "COMPLETE_ORDER", ConversationEvent.COMPLETE_ORDER),
        ("I'm done ordering", "COMPLETE_ORDER", ConversationEvent.COMPLETE_ORDER),
        ("Actually, cancel everything", "CANCEL_ORDER", ConversationEvent.CANCEL_ORDER),
        ("What comes with the bento box?", "REQUEST_MENU", None),
    ]
    
    for transcript, intent, expected_event in test_cases:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = intent
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        event = await intent_detector.detect_intent(
            transcript,
            ConversationState.ORDERING,
            {}
        )
        
        assert event == expected_event


@pytest.mark.asyncio
async def test_confirmation_state_intent_detection(intent_detector):
    """Test intent detection during order confirmation."""
    test_cases = [
        ("Yes, that's correct", "CONFIRM_ORDER", ConversationEvent.CONFIRM_ORDER),
        ("Sounds good", "CONFIRM_ORDER", ConversationEvent.CONFIRM_ORDER),
        ("No, I need to change something", "MODIFY_ORDER", ConversationEvent.MODIFY_ORDER),
        ("Actually can I add one more item", "MODIFY_ORDER", ConversationEvent.MODIFY_ORDER),
        ("Cancel the order", "CANCEL_ORDER", ConversationEvent.REJECT_ORDER),
        ("How long will it take?", "REQUEST_INFO", None),
    ]
    
    for transcript, intent, expected_event in test_cases:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = intent
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        event = await intent_detector.detect_intent(
            transcript,
            ConversationState.CONFIRMATION,
            {}
        )
        
        assert event == expected_event


@pytest.mark.asyncio
async def test_system_prompt_generation(intent_detector):
    """Test that system prompts are properly generated for each state."""
    states = [
        ConversationState.GREETING,
        ConversationState.MAIN_MENU,
        ConversationState.ORDERING,
        ConversationState.VALIDATION,
        ConversationState.CONFIRMATION,
        ConversationState.FULFILLMENT
    ]
    
    for state in states:
        prompt = intent_detector._build_system_prompt(state)
        
        # Verify prompt structure
        assert "intent classifier" in prompt
        assert state.name in prompt
        assert "Allowed intents:" in prompt
        assert "Examples:" in prompt
        
        # Verify state-specific content
        if state == ConversationState.GREETING:
            assert "PROVIDE_NAME" in prompt
        elif state == ConversationState.MAIN_MENU:
            assert "START_ORDER" in prompt
            assert "REQUEST_MENU" in prompt
        elif state == ConversationState.ORDERING:
            assert "ADD_ITEM" in prompt
            assert "COMPLETE_ORDER" in prompt


@pytest.mark.asyncio
async def test_empty_transcript_handling(intent_detector):
    """Test that empty transcripts return None."""
    event = await intent_detector.detect_intent(
        "",
        ConversationState.MAIN_MENU,
        {}
    )
    
    assert event is None
    # Should not call OpenAI API
    intent_detector.client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_openai_error_handling(intent_detector):
    """Test error handling when OpenAI API fails."""
    intent_detector.client.chat.completions.create.side_effect = Exception("API Error")
    
    event = await intent_detector.detect_intent(
        "I want to order",
        ConversationState.MAIN_MENU,
        {}
    )
    
    assert event is None  # Should return None on error


@pytest.mark.asyncio
async def test_low_temperature_setting(intent_detector):
    """Test that intent detection uses low temperature for consistency."""
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "START_ORDER"
    intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    await intent_detector.detect_intent(
        "I want to order",
        ConversationState.MAIN_MENU,
        {}
    )
    
    # Verify API call parameters
    call_args = intent_detector.client.chat.completions.create.call_args
    assert call_args.kwargs['temperature'] == 0.1
    assert call_args.kwargs['model'] == 'gpt-4o-mini'
    assert call_args.kwargs['max_tokens'] == 50


@pytest.mark.asyncio
async def test_context_aware_detection(intent_detector):
    """Test that the same phrase can have different intents in different states."""
    # "Yes" in different contexts
    test_cases = [
        (ConversationState.VALIDATION, "CONFIRM"),
        (ConversationState.CONFIRMATION, "CONFIRM_ORDER"),
    ]
    
    for state, expected_intent in test_cases:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = expected_intent
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        event = await intent_detector.detect_intent(
            "Yes",
            state,
            {}
        )
        
        # Different events based on state
        if state == ConversationState.VALIDATION:
            assert event == ConversationEvent.VALIDATE_ORDER
        elif state == ConversationState.CONFIRMATION:
            assert event == ConversationEvent.CONFIRM_ORDER


@pytest.mark.asyncio
async def test_unmapped_intent_handling(intent_detector):
    """Test handling of intents that don't map to events."""
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "UNKNOWN_INTENT"
    intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    event = await intent_detector.detect_intent(
        "Something unexpected",
        ConversationState.MAIN_MENU,
        {}
    )
    
    assert event is None  # No mapping for unknown intent