"""
Simple unit tests to verify test setup.
"""
import pytest
from app.fsm.core import ConversationState, ConversationEvent


class TestSimple:
    """Simple tests to verify setup."""
    
    def test_basic_assertion(self):
        """Test basic assertion."""
        assert 1 + 1 == 2
    
    def test_conversation_state_enum(self):
        """Test conversation state enum."""
        # ConversationState uses auto() which assigns integer values
        assert isinstance(ConversationState.GREETING.value, int)
        assert isinstance(ConversationState.MAIN_MENU.value, int)
        assert isinstance(ConversationState.ORDERING.value, int)
        
        # Test string representation
        assert str(ConversationState.GREETING) == "GREETING"
        assert str(ConversationState.MAIN_MENU) == "MAIN_MENU"
        assert str(ConversationState.ORDERING) == "ORDERING"
    
    def test_conversation_event_enum(self):
        """Test conversation event enum."""
        # ConversationEvent uses auto() which assigns integer values
        assert isinstance(ConversationEvent.START_CONVERSATION.value, int)
        assert isinstance(ConversationEvent.START_ORDER.value, int)
        
        # Test string representation
        assert str(ConversationEvent.START_CONVERSATION) == "START_CONVERSATION"
        assert str(ConversationEvent.START_ORDER) == "START_ORDER"
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function execution."""
        async def async_add(a, b):
            return a + b
        
        result = await async_add(3, 4)
        assert result == 7
    
    def test_dict_operations(self):
        """Test dictionary operations."""
        cart = {
            "items": [],
            "total": 0
        }
        
        cart["items"].append({"name": "Test Item", "price": 100})
        cart["total"] = 100
        
        assert len(cart["items"]) == 1
        assert cart["total"] == 100