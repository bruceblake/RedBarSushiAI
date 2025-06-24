"""
Comprehensive unit tests for the Cart Agent.
Tests AI integration, cart management, and order processing.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
from app.agents.cart_async import AsyncCartAgent


class TestCartAgentComprehensive:
    """Comprehensive tests for cart agent functionality."""
    
    @pytest_asyncio.fixture
    async def cart_agent(self):
        """Create a cart agent instance for testing."""
        agent = AsyncCartAgent()
        agent.db = MagicMock()
        agent.set_current_call("test_call_123")
        return agent
    
    @pytest.fixture
    def mock_conversation_store(self):
        """Mock the conversation store."""
        with patch('app.agents.cart_async.async_agents_conversation_store') as mock:
            mock.get_conversation = AsyncMock(return_value={
                "context": {
                    "cart": {"items": [], "total_price": 0}
                }
            })
            mock.save_conversation = AsyncMock()
            yield mock
    
    @pytest.fixture
    def mock_menu_store(self):
        """Mock the menu database store."""
        with patch('app.agents.cart_async.async_menu_db_store') as mock:
            mock.get_item_by_plu = AsyncMock(side_effect=self._mock_get_item_by_plu)
            yield mock
    
    def _mock_get_item_by_plu(self, plu, db=None):
        """Mock menu item lookup."""
        items = {
            "SUSHI001": {
                "plu": "SUSHI001",
                "name": "California Roll",
                "price": 12.95,
                "available": True
            },
            "SUSHI002": {
                "plu": "SUSHI002",
                "name": "Spicy Tuna Roll",
                "price": 14.95,
                "available": True
            },
            "APP001": {
                "plu": "APP001",
                "name": "Edamame",
                "price": 5.95,
                "available": True
            }
        }
        return items.get(plu)
    
    @pytest.mark.asyncio
    async def test_ai_order_recognition(self, cart_agent, mock_conversation_store):
        """Test that cart agent uses AI to recognize orders."""
        # Mock AI response
        with patch.object(cart_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {
                "text": "I'll add 2 California Rolls to your order. Is there anything else?",
                "agent": "Cart",
                "handled": True,
                "ai_generated": True,
                "tool_calls": [
                    {
                        "function": {
                            "name": "lookup_menu_item",
                            "arguments": '{"item_name": "california roll"}'
                        }
                    },
                    {
                        "function": {
                            "name": "add_item_to_cart",
                            "arguments": '{"plu": "SUSHI001", "quantity": 2}'
                        }
                    }
                ]
            }
            
            response = await cart_agent.process_input(
                "I want two California rolls",
                {"call_sid": "test_call_123"}
            )
            
            assert response["text"] == "I'll add 2 California Rolls to your order. Is there anything else?"
            assert response["handled"] is True
            assert "cart" in response
            mock_ai.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_duplicate_item_consolidation(self, cart_agent, mock_conversation_store, mock_menu_store):
        """Test that duplicate items are consolidated instead of duplicated."""
        # Set up existing cart with one California Roll
        mock_conversation_store.get_conversation.return_value = {
            "context": {
                "cart": {
                    "items": [{
                        "plu": "SUSHI001",
                        "name": "California Roll",
                        "price": 12.95,
                        "quantity": 1,
                        "modifiers": [],
                        "special_instructions": None
                    }],
                    "total_price": 12.95
                }
            }
        }
        
        # Add another California Roll
        result = await cart_agent._add_item_to_cart("SUSHI001", 2)
        
        # Verify the save was called
        saved_cart = mock_conversation_store.save_conversation.call_args[0][1]["context"]["cart"]
        
        # Should have only one item with quantity 3
        assert len(saved_cart["items"]) == 1
        assert saved_cart["items"][0]["quantity"] == 3
        assert saved_cart["items"][0]["plu"] == "SUSHI001"
    
    @pytest.mark.asyncio
    async def test_order_completion_detection(self, cart_agent):
        """Test detection of order completion phrases."""
        completion_phrases = [
            "That's all",
            "I'm done",
            "Ready to checkout",
            "That's it",
            "Complete my order",
            "Finished ordering"
        ]
        
        for phrase in completion_phrases:
            with patch.object(cart_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = {"text": "Your order is complete.", "handled": True}
                
                response = await cart_agent.process_input(phrase, {"call_sid": "test_123"})
                assert response["order_ready_for_validation"] is True
    
    @pytest.mark.asyncio
    async def test_price_calculation_accuracy(self, cart_agent, mock_conversation_store, mock_menu_store):
        """Test accurate price calculation including modifiers."""
        # Add multiple items
        await cart_agent._add_item_to_cart("SUSHI001", 2)  # 2 x $12.95
        await cart_agent._add_item_to_cart("SUSHI002", 1)  # 1 x $14.95
        await cart_agent._add_item_to_cart("APP001", 1)    # 1 x $5.95
        
        # Get the final cart
        final_call = mock_conversation_store.save_conversation.call_args_list[-1]
        cart = final_call[0][1]["context"]["cart"]
        
        # Total should be (2 * 12.95) + 14.95 + 5.95 = 46.80
        assert abs(cart["total_price"] - 46.80) < 0.01
    
    @pytest.mark.asyncio
    async def test_cart_summary_generation(self, cart_agent):
        """Test cart summary functionality."""
        # Mock a cart with items
        with patch('app.agents.cart_async.async_agents_conversation_store') as mock_store:
            mock_store.get_conversation = AsyncMock(return_value={
                "context": {
                    "cart": {
                        "items": [
                            {"name": "California Roll", "quantity": 2, "price": 12.95},
                            {"name": "Spicy Tuna Roll", "quantity": 1, "price": 14.95}
                        ],
                        "total_price": 40.85
                    }
                }
            })
            
            result = await cart_agent._get_current_cart()
            assert result["success"] is True
            assert result["item_count"] == 2
            assert result["formatted_total"] == "$40.85"
    
    @pytest.mark.asyncio
    async def test_invalid_item_handling(self, cart_agent, mock_menu_store):
        """Test handling of invalid menu items."""
        # Try to add non-existent item
        result = await cart_agent._add_item_to_cart("INVALID_PLU", 1)
        
        assert result["success"] is False
        assert "not found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_empty_cart_handling(self, cart_agent):
        """Test proper handling of empty cart."""
        with patch('app.agents.cart_async.async_agents_conversation_store') as mock_store:
            mock_store.get_conversation = AsyncMock(return_value={
                "context": {"cart": {"items": [], "total_price": 0}}
            })
            
            result = await cart_agent._get_current_cart()
            assert result["item_count"] == 0
            assert result["formatted_total"] == "$0.00"
    
    @pytest.mark.asyncio
    async def test_complex_order_parsing(self, cart_agent):
        """Test parsing of complex orders with multiple items and quantities."""
        with patch.object(cart_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            # Simulate AI correctly parsing a complex order
            mock_ai.return_value = {
                "text": "I've added 2 California Rolls, 3 Spicy Tuna Rolls, and 1 Edamame to your cart.",
                "handled": True,
                "tool_calls": [
                    {"function": {"name": "add_item_to_cart", "arguments": '{"plu": "SUSHI001", "quantity": 2}'}},
                    {"function": {"name": "add_item_to_cart", "arguments": '{"plu": "SUSHI002", "quantity": 3}'}},
                    {"function": {"name": "add_item_to_cart", "arguments": '{"plu": "APP001", "quantity": 1}'}}
                ]
            }
            
            response = await cart_agent.process_input(
                "I'll have two california rolls, three spicy tuna, and one edamame",
                {"call_sid": "test_123"}
            )
            
            assert "California Rolls" in response["text"]
            assert "Spicy Tuna Rolls" in response["text"]
            assert "Edamame" in response["text"]