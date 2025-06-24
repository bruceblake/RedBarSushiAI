"""Unit tests for the AsyncIntentDetector."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.utils.intent_detector_async import AsyncIntentDetector
from app.fsm.core import ConversationState, ConversationEvent


@pytest.fixture
def intent_detector():
    """Create an intent detector instance."""
    return AsyncIntentDetector()


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = Mock()
    mock_client.chat = Mock()
    mock_client.chat.completions = Mock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client


class TestAsyncIntentDetector:
    """Test cases for AsyncIntentDetector."""
    
    @pytest.mark.asyncio
    async def test_detect_intent_with_api(self, intent_detector, mock_openai_client):
        """Test intent detection when API is available."""
        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "PROVIDE_NAME"
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        intent_detector.client = mock_openai_client
        
        # Test
        result = await intent_detector.detect_intent(
            transcript="My name is John",
            current_state=ConversationState.GREETING,
            context={}
        )
        
        assert result == ConversationEvent.USER_PROVIDES_NAME
        mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_intent_empty_transcript(self, intent_detector):
        """Test with empty transcript."""
        result = await intent_detector.detect_intent(
            transcript="",
            current_state=ConversationState.GREETING,
            context={}
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_fallback_name_detection_valid_names(self, intent_detector):
        """Test fallback name detection for valid names."""
        # Force fallback by setting client to None
        intent_detector.client = None
        
        valid_names = [
            "John",
            "Sarah",
            "Mary Jane",
            "O'Brien",
            "Mary-Jane",
            "My name is John",
            "I am Sarah",
            "Call me Mike",
            "It's David"
        ]
        
        for name in valid_names:
            result = await intent_detector.detect_intent(
                transcript=name,
                current_state=ConversationState.GREETING,
                context={}
            )
            assert result == ConversationEvent.USER_PROVIDES_NAME, f"Failed to detect '{name}' as a name"
    
    @pytest.mark.asyncio
    async def test_fallback_name_detection_non_names(self, intent_detector):
        """Test fallback name detection correctly rejects non-names."""
        # Force fallback by setting client to None
        intent_detector.client = None
        
        non_names = [
            "What",
            "I",
            "Actually",
            "Hello",
            "Yes",
            "No",
            "Maybe",
            "Please",
            "what is your name",
            "i don't know",
            "how are you",
            "thank you",
            "okay",
            "sure"
        ]
        
        for non_name in non_names:
            result = await intent_detector.detect_intent(
                transcript=non_name,
                current_state=ConversationState.GREETING,
                context={}
            )
            assert result is None, f"Incorrectly detected '{non_name}' as a name"
    
    @pytest.mark.asyncio
    async def test_fallback_only_in_greeting_state(self, intent_detector):
        """Test that fallback name detection only works in GREETING state."""
        # Force fallback by setting client to None
        intent_detector.client = None
        
        # Should detect name in GREETING state
        result = await intent_detector.detect_intent(
            transcript="John",
            current_state=ConversationState.GREETING,
            context={}
        )
        assert result == ConversationEvent.USER_PROVIDES_NAME
        
        # Should NOT detect name in other states
        for state in [ConversationState.MAIN_MENU, ConversationState.ORDERING, ConversationState.VALIDATION]:
            result = await intent_detector.detect_intent(
                transcript="John",
                current_state=state,
                context={}
            )
            assert result is None
    
    @pytest.mark.asyncio
    async def test_build_system_prompt(self, intent_detector):
        """Test system prompt generation for different states."""
        # Test all states have prompts
        for state in ConversationState:
            prompt = intent_detector._build_system_prompt(state)
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert state.name in prompt
    
    @pytest.mark.asyncio
    async def test_map_intent_to_event(self, intent_detector):
        """Test intent to event mapping."""
        # Test greeting state mappings
        assert intent_detector._map_intent_to_event(
            "PROVIDE_NAME", ConversationState.GREETING
        ) == ConversationEvent.USER_PROVIDES_NAME
        
        assert intent_detector._map_intent_to_event(
            "SKIP_NAME", ConversationState.GREETING
        ) == ConversationEvent.USER_PROVIDES_NAME
        
        # Test main menu mappings
        assert intent_detector._map_intent_to_event(
            "START_ORDER", ConversationState.MAIN_MENU
        ) == ConversationEvent.START_ORDER
        
        assert intent_detector._map_intent_to_event(
            "REQUEST_MENU", ConversationState.MAIN_MENU
        ) == ConversationEvent.REQUEST_MENU_INFO
        
        # Test ordering state mappings
        assert intent_detector._map_intent_to_event(
            "COMPLETE_ORDER", ConversationState.ORDERING
        ) == ConversationEvent.COMPLETE_ORDER
        
        assert intent_detector._map_intent_to_event(
            "CANCEL_ORDER", ConversationState.ORDERING
        ) == ConversationEvent.CANCEL_ORDER
    
    @pytest.mark.asyncio
    async def test_fallback_name_with_punctuation(self, intent_detector):
        """Test fallback handles names with punctuation correctly."""
        # Force fallback by setting client to None
        intent_detector.client = None
        
        test_cases = [
            ("John.", "John"),  # Period at end
            ("Sarah!", "Sarah"),  # Exclamation at end
            ("Mike,", "Mike"),  # Comma at end
            ("David?", "David"),  # Question mark at end
        ]
        
        for transcript, expected_name in test_cases:
            result = await intent_detector.detect_intent(
                transcript=transcript,
                current_state=ConversationState.GREETING,
                context={}
            )
            assert result == ConversationEvent.USER_PROVIDES_NAME, f"Failed to detect '{expected_name}' from '{transcript}'"
    
    @pytest.mark.asyncio
    async def test_fallback_case_sensitivity(self, intent_detector):
        """Test fallback requires proper capitalization for single words."""
        # Force fallback by setting client to None
        intent_detector.client = None
        
        # Capitalized name should be detected
        result = await intent_detector.detect_intent(
            transcript="John",
            current_state=ConversationState.GREETING,
            context={}
        )
        assert result == ConversationEvent.USER_PROVIDES_NAME
        
        # Lowercase name should NOT be detected (without indicator)
        result = await intent_detector.detect_intent(
            transcript="john",
            current_state=ConversationState.GREETING,
            context={}
        )
        assert result is None
        
        # But with indicator, case doesn't matter
        result = await intent_detector.detect_intent(
            transcript="my name is john",
            current_state=ConversationState.GREETING,
            context={}
        )
        assert result == ConversationEvent.USER_PROVIDES_NAME