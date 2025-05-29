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
        assert ConversationState.GREETING.value == "greeting"
        assert ConversationState.MAIN_MENU.value == "main_menu"
        assert ConversationState.ORDERING.value == "ordering"
    
    def test_conversation_event_enum(self):
        """Test conversation event enum."""
        assert ConversationEvent.CUSTOMER_GREETED.value == "customer_greeted"
        assert ConversationEvent.ORDER_STARTED.value == "order_started"
    
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