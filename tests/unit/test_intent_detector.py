"""
Unit tests for LLM-based intent detection.
Tests intent detection logic with mocked OpenAI client.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.utils.intent_detector_async import AsyncIntentDetector
from app.fsm.core import ConversationState, ConversationEvent


class TestAsyncIntentDetector:
    """Test the LLM-based intent detector."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def detector(self, mock_openai_client):
        """Create intent detector with mocked client."""
        with patch('app.utils.intent_detector_async.AsyncOpenAI', return_value=mock_openai_client):
            detector = AsyncIntentDetector()
            detector.client = mock_openai_client
            return detector
    
    def create_mock_response(self, content):
        """Helper to create mock OpenAI response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = content
        return mock_response
    
    @pytest.mark.asyncio
    async def test_greeting_state_name_detection(self, detector, mock_openai_client):
        """Test detecting name provision in GREETING state."""
        # Mock OpenAI response
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("PROVIDE_NAME")
        
        # Test various name inputs
        test_cases = [
            "My name is John",
            "I'm Sarah",
            "Call me Mike",
            "This is Lisa calling"
        ]
        
        for transcript in test_cases:
            event = await detector.detect_intent(
                transcript=transcript,
                current_state=ConversationState.GREETING,
                context={"greeting_sent": True}
            )
            
            assert event == ConversationEvent.USER_PROVIDES_NAME
    
    @pytest.mark.asyncio
    async def test_greeting_state_skip_name(self, detector, mock_openai_client):
        """Test detecting name skip in GREETING state."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("SKIP_NAME")
        
        event = await detector.detect_intent(
            transcript="I don't want to give my name",
            current_state=ConversationState.GREETING,
            context={"greeting_sent": True}
        )
        
        # Should map to USER_PROVIDES_NAME (skip still moves forward)
        assert event == ConversationEvent.USER_PROVIDES_NAME
    
    @pytest.mark.asyncio
    async def test_main_menu_order_intent(self, detector, mock_openai_client):
        """Test detecting order intent from MAIN_MENU."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("START_ORDER")
        
        test_cases = [
            "I want to order something",
            "Can I place an order?",
            "I'd like to get some food"
        ]
        
        for transcript in test_cases:
            event = await detector.detect_intent(
                transcript=transcript,
                current_state=ConversationState.MAIN_MENU,
                context={}
            )
            
            assert event == ConversationEvent.USER_STARTS_ORDER
    
    @pytest.mark.asyncio
    async def test_main_menu_menu_inquiry(self, detector, mock_openai_client):
        """Test detecting menu inquiry from MAIN_MENU."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("MENU_INQUIRY")
        
        event = await detector.detect_intent(
            transcript="What's on your menu?",
            current_state=ConversationState.MAIN_MENU,
            context={}
        )
        
        assert event == ConversationEvent.USER_ASKS_MENU
    
    @pytest.mark.asyncio
    async def test_ordering_state_add_item(self, detector, mock_openai_client):
        """Test detecting add item intent in ORDERING state."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("ADD_ITEM")
        
        event = await detector.detect_intent(
            transcript="I'll have a California roll",
            current_state=ConversationState.ORDERING,
            context={"cart_items": []}
        )
        
        assert event == ConversationEvent.USER_ADDS_ITEM
    
    @pytest.mark.asyncio
    async def test_ordering_state_confirm_cart(self, detector, mock_openai_client):
        """Test detecting cart confirmation in ORDERING state."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("CONFIRM_CART")
        
        event = await detector.detect_intent(
            transcript="That's all for now",
            current_state=ConversationState.ORDERING,
            context={"cart_items": [{"name": "California Roll"}]}
        )
        
        assert event == ConversationEvent.USER_CONFIRMS_CART
    
    @pytest.mark.asyncio
    async def test_confirmation_state_confirm_order(self, detector, mock_openai_client):
        """Test detecting order confirmation."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("CONFIRM_ORDER")
        
        event = await detector.detect_intent(
            transcript="Yes, that's correct",
            current_state=ConversationState.CONFIRMATION,
            context={}
        )
        
        assert event == ConversationEvent.USER_CONFIRMS_ORDER
    
    @pytest.mark.asyncio
    async def test_escalation_request_any_state(self, detector, mock_openai_client):
        """Test detecting escalation request from any state."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("REQUEST_HUMAN")
        
        states_to_test = [
            ConversationState.GREETING,
            ConversationState.MAIN_MENU,
            ConversationState.ORDERING
        ]
        
        for state in states_to_test:
            event = await detector.detect_intent(
                transcript="I want to speak to a person",
                current_state=state,
                context={}
            )
            
            assert event == ConversationEvent.USER_REQUESTS_HUMAN
    
    @pytest.mark.asyncio
    async def test_prompt_construction(self, detector, mock_openai_client):
        """Test that prompts are constructed correctly."""
        # Capture the actual prompt sent to OpenAI
        captured_messages = None
        
        async def capture_prompt(**kwargs):
            nonlocal captured_messages
            captured_messages = kwargs.get('messages', [])
            return self.create_mock_response("START_ORDER")
        
        mock_openai_client.chat.completions.create.side_effect = capture_prompt
        
        await detector.detect_intent(
            transcript="I want to order",
            current_state=ConversationState.MAIN_MENU,
            context={"customer_name": "John"}
        )
        
        # Verify prompt structure
        assert len(captured_messages) > 0
        assert any("main_menu" in msg.get('content', '').lower() for msg in captured_messages)
        assert any("I want to order" in msg.get('content', '') for msg in captured_messages)
    
    @pytest.mark.asyncio
    async def test_invalid_intent_returns_none(self, detector, mock_openai_client):
        """Test that invalid intents return None."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("INVALID_INTENT")
        
        event = await detector.detect_intent(
            transcript="Random text",
            current_state=ConversationState.MAIN_MENU,
            context={}
        )
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_empty_transcript_returns_none(self, detector, mock_openai_client):
        """Test that empty transcript returns None."""
        event = await detector.detect_intent(
            transcript="",
            current_state=ConversationState.MAIN_MENU,
            context={}
        )
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_error_handling(self, detector, mock_openai_client):
        """Test error handling in intent detection."""
        # Mock OpenAI error
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        event = await detector.detect_intent(
            transcript="Test input",
            current_state=ConversationState.MAIN_MENU,
            context={}
        )
        
        # Should handle error gracefully and return None
        assert event is None
    
    @pytest.mark.asyncio
    async def test_model_configuration(self, detector):
        """Test that the correct model is configured."""
        assert detector.model == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_temperature_setting(self, detector, mock_openai_client):
        """Test that temperature is set appropriately for intent detection."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response("START_ORDER")
        
        await detector.detect_intent(
            transcript="I want to order",
            current_state=ConversationState.MAIN_MENU,
            context={}
        )
        
        # Verify low temperature for consistent results
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get('temperature', 1.0) <= 0.3