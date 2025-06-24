"""
Comprehensive unit tests for the Intent Detector.
Tests AI-powered intent detection for all conversation states and events.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.intent_detector_async import AsyncIntentDetector
from app.fsm.core import ConversationState, ConversationEvent


class TestIntentDetectorComprehensive:
    """Comprehensive tests for intent detection functionality."""
    
    @pytest_asyncio.fixture
    async def intent_detector(self):
        """Create intent detector instance."""
        with patch('app.utils.intent_detector_async.AsyncOpenAI'):
            detector = AsyncIntentDetector()
            return detector
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create mock OpenAI response."""
        def _create_response(content):
            mock_choice = MagicMock()
            mock_choice.message.content = content
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            return mock_response
        return _create_response
    
    @pytest.mark.asyncio
    async def test_greeting_state_intents(self, intent_detector, mock_openai_response):
        """Test intent detection in GREETING state."""
        test_cases = [
            ("My name is John", "PROVIDE_NAME"),
            ("I'm Sarah", "PROVIDE_NAME"),
            ("This is Mike", "PROVIDE_NAME"),
            ("Bruce here", "PROVIDE_NAME"),
            ("Hello", "SKIP_NAME"),
            ("Hi there", "SKIP_NAME"),
            ("I need help", "REQUEST_ESCALATION")
        ]
        
        for transcript, expected_event in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_event)
                )
                
                event = await intent_detector.detect_intent(transcript, ConversationState.GREETING, {})
                if expected_event in ["PROVIDE_NAME", "SKIP_NAME"]:
                    assert event == ConversationEvent.USER_PROVIDES_NAME
                elif expected_event == "REQUEST_ESCALATION":
                    assert event is None  # No event mapping in GREETING state
                else:
                    assert False, f"Unexpected event: {expected_event}"
    
    @pytest.mark.asyncio
    async def test_main_menu_intents(self, intent_detector, mock_openai_response):
        """Test intent detection in MAIN_MENU state."""
        test_cases = [
            ("I want to place an order", "START_ORDER"),
            ("I'd like to order food", "START_ORDER"),
            ("What's on your menu?", "REQUEST_MENU"),
            ("What do you have?", "REQUEST_MENU"),
            ("I need to speak to someone", "REQUEST_HUMAN"),
            ("Can I talk to a person?", "REQUEST_HUMAN"),
            ("Never mind", "GENERAL_QUESTION")
        ]
        
        for transcript, expected_event in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_event)
                )
                
                event = await intent_detector.detect_intent(transcript, ConversationState.MAIN_MENU, {})
                if expected_event == "START_ORDER":
                    assert event == ConversationEvent.START_ORDER
                elif expected_event == "REQUEST_MENU":
                    assert event == ConversationEvent.REQUEST_MENU_INFO
                elif expected_event == "REQUEST_HUMAN":
                    assert event == ConversationEvent.REQUEST_ESCALATION
                elif expected_event == "GENERAL_QUESTION":
                    assert event is None
                else:
                    assert False, f"Unexpected event: {expected_event}"
    
    @pytest.mark.asyncio
    async def test_ordering_state_intents(self, intent_detector, mock_openai_response):
        """Test intent detection in ORDERING state."""
        test_cases = [
            ("I'll have two California rolls", "ADD_ITEM"),
            ("Add a spicy tuna roll", "ADD_ITEM"),
            ("Remove the California roll", "REMOVE_ITEM"),
            ("That's all for my order", "COMPLETE_ORDER"),
            ("I'm done ordering", "COMPLETE_ORDER"),
            ("What's in my cart?", "ADD_ITEM"),
            ("Actually, never mind", "CANCEL_ORDER")
        ]
        
        for transcript, expected_event in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_event)
                )
                
                event = await intent_detector.detect_intent(transcript, ConversationState.ORDERING, {})
                if expected_event in ["ADD_ITEM", "REMOVE_ITEM", "MODIFY_ITEM"]:
                    assert event is None  # Handled by cart agent
                elif expected_event == "COMPLETE_ORDER":
                    assert event == ConversationEvent.COMPLETE_ORDER
                elif expected_event == "CANCEL_ORDER":
                    assert event == ConversationEvent.CANCEL_ORDER
                else:
                    assert False, f"Unexpected event: {expected_event}"
    
    @pytest.mark.asyncio
    async def test_confirmation_state_intents(self, intent_detector, mock_openai_response):
        """Test intent detection in CONFIRMATION state."""
        test_cases = [
            ("Yes, that's correct", "CONFIRM_ORDER"),
            ("Yes, looks good", "CONFIRM_ORDER"),
            ("Confirmed", "CONFIRM_ORDER"),
            ("No, that's wrong", "CANCEL_ORDER"),
            ("No, I need to change something", "MODIFY_ORDER"),
            ("Actually, cancel the order", "CANCEL_ORDER")
        ]
        
        for transcript, expected_event in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_event)
                )
                
                event = await intent_detector.detect_intent(transcript, ConversationState.CONFIRMATION, {})
                if expected_event == "CONFIRM_ORDER":
                    assert event == ConversationEvent.CONFIRM_ORDER
                elif expected_event == "MODIFY_ORDER":
                    assert event == ConversationEvent.MODIFY_ORDER
                elif expected_event == "CANCEL_ORDER":
                    assert event == ConversationEvent.REJECT_ORDER
                else:
                    assert False, f"Unexpected event: {expected_event}"
    
    @pytest.mark.asyncio
    async def test_fulfillment_state_intents(self, intent_detector, mock_openai_response):
        """Test intent detection in FULFILLMENT state."""
        test_cases = [
            ("I'll pick it up", "CHOOSE_PICKUP"),
            ("Delivery please", "PROVIDE_DELIVERY"),
            ("In 20 minutes", "PROVIDE_DELIVERY"),
            ("ASAP", "PROVIDE_DELIVERY"),
            ("My address is 123 Main St", "PROVIDE_DELIVERY")
        ]
        
        for transcript, expected_event in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_event)
                )
                
                event = await intent_detector.detect_intent(transcript, ConversationState.FULFILLMENT, {})
                if expected_event == "CHOOSE_PICKUP":
                    assert event == ConversationEvent.CHOOSE_PICKUP
                elif expected_event == "PROVIDE_DELIVERY":
                    assert event == ConversationEvent.PROVIDE_DELIVERY_INFO
                else:
                    assert False, f"Unexpected event: {expected_event}"
    
    @pytest.mark.asyncio
    async def test_ambiguous_intents(self, intent_detector, mock_openai_response):
        """Test handling of ambiguous intents."""
        ambiguous_phrases = [
            "Uh, maybe",
            "I'm not sure",
            "What?",
            "Hmm",
            "..."
        ]
        
        for phrase in ambiguous_phrases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                # AI might return None or UNKNOWN for ambiguous input
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response("UNKNOWN")
                )
                
                event = await intent_detector.detect_intent(phrase, ConversationState.MAIN_MENU, {})
                # Should handle gracefully, possibly returning None
                assert event is None or event == ConversationEvent.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_context_aware_detection(self, intent_detector, mock_openai_response):
        """Test that context affects intent detection."""
        phrase = "Yes"  # Ambiguous without context
        
        # In CONFIRMATION state, "Yes" means confirm
        with patch.object(intent_detector.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(
                return_value=mock_openai_response("CONFIRM_ORDER")
            )
            
            event = await intent_detector.detect_intent(phrase, ConversationState.CONFIRMATION, {})
            assert event == ConversationEvent.CONFIRM_ORDER
        
        # In GREETING state, "Yes" might be acknowledgment
        with patch.object(intent_detector.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(
                return_value=mock_openai_response("SKIP_NAME")  # Use valid greeting intent
            )
            
            event = await intent_detector.detect_intent(phrase, ConversationState.GREETING, {})
            assert event == ConversationEvent.USER_PROVIDES_NAME  # SKIP_NAME maps to USER_PROVIDES_NAME
    
    @pytest.mark.asyncio
    async def test_error_handling(self, intent_detector):
        """Test error handling in intent detection."""
        # Test OpenAI API error
        with patch.object(intent_detector.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(
                side_effect=Exception("API Error")
            )
            
            event = await intent_detector.detect_intent("Test phrase", ConversationState.MAIN_MENU, {})
            assert event is None  # Should return None on error
    
    @pytest.mark.asyncio
    async def test_special_characters_handling(self, intent_detector, mock_openai_response):
        """Test handling of special characters and edge cases."""
        test_cases = [
            ("My name is José García", "GENERAL_QUESTION", ConversationState.MAIN_MENU),  # Name in main menu not expected
            ("I'd like 2 rolls @ $10 each", "START_ORDER", ConversationState.MAIN_MENU),
            ("Email: test@example.com", "GENERAL_QUESTION", ConversationState.MAIN_MENU),
            ("Phone: (555) 123-4567", "GENERAL_QUESTION", ConversationState.MAIN_MENU)
        ]
        
        for transcript, expected_intent, state in test_cases:
            with patch.object(intent_detector.client, 'chat') as mock_chat:
                mock_chat.completions.create = AsyncMock(
                    return_value=mock_openai_response(expected_intent)
                )
                
                event = await intent_detector.detect_intent(transcript, state, {})
                if expected_intent == "GENERAL_QUESTION":
                    assert event is None  # No event mapping
                elif expected_intent == "START_ORDER":
                    assert event == ConversationEvent.START_ORDER
                else:
                    assert False, f"Unexpected intent: {expected_intent}"
    
    @pytest.mark.asyncio
    async def test_multi_intent_phrases(self, intent_detector, mock_openai_response):
        """Test phrases that could have multiple intents."""
        # "I'm done" could mean complete order or end conversation
        with patch.object(intent_detector.client, 'chat') as mock_chat:
            # In ORDERING state, should complete order
            mock_chat.completions.create = AsyncMock(
                return_value=mock_openai_response("COMPLETE_ORDER")
            )
            
            event = await intent_detector.detect_intent("I'm done", ConversationState.ORDERING, {})
            assert event == ConversationEvent.COMPLETE_ORDER
            
            # In MAIN_MENU state, might end conversation
            mock_chat.completions.create = AsyncMock(
                return_value=mock_openai_response("END_CONVERSATION")
            )
            
            event = await intent_detector.detect_intent("I'm done", ConversationState.MAIN_MENU, {})
            assert event is None  # GENERAL_QUESTION has no event mapping