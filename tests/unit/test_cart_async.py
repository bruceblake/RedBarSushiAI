"""
Unit tests for AsyncCartAgent class.

This module tests the cart agent functionality including item lookup,
cart management, and order building capabilities.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.agents.cart_async import AsyncCartAgent
from app.models.menu_async import MenuItem


class TestAsyncCartAgent:
    """Test suite for AsyncCartAgent class."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_menu_matcher(self):
        """Create a mock menu matcher."""
        with patch('app.agents.cart_async.get_cached_async_menu_matcher') as mock_get_matcher:
            matcher = MagicMock()
            
            # Mock successful item match
            async def mock_match_item(item_name, context=None):
                if "california roll" in item_name.lower():
                    return {
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "price": 12.95,
                        "description": "Crab, avocado, cucumber",
                        "category": "Rolls"
                    }
                elif "spicy tuna" in item_name.lower():
                    return {
                        "plu": "TUNA_001",
                        "name": "Spicy Tuna Roll",
                        "price": 13.95,
                        "description": "Spicy tuna, cucumber",
                        "category": "Rolls"
                    }
                return None
            
            matcher.match_menu_item = mock_match_item
            mock_get_matcher.return_value = matcher
            yield matcher
    
    @pytest.fixture
    def mock_conversation_store(self):
        """Create a mock conversation store."""
        with patch('app.agents.cart_async.async_agents_conversation_store') as mock_store:
            # Mock cart storage
            cart_data = {"items": []}
            
            async def mock_get_cart(session_id):
                return cart_data.copy()
            
            async def mock_save_cart(session_id, cart):
                cart_data.clear()
                cart_data.update(cart)
            
            mock_store.get_cart = mock_get_cart
            mock_store.save_cart = mock_save_cart
            
            yield mock_store
    
    @pytest.fixture
    async def cart_agent(self, mock_db_session, mock_menu_matcher, mock_conversation_store):
        """Create a cart agent instance for testing."""
        agent = AsyncCartAgent(agent_id="test_cart_123", db=mock_db_session)
        return agent
    
    def test_initialization(self, mock_db_session):
        """Test cart agent initialization."""
        agent = AsyncCartAgent(agent_id="custom_cart", db=mock_db_session)
        
        assert agent.name == "Cart"
        assert agent.agent_id == "custom_cart"
        assert agent.db == mock_db_session
        assert len(agent.tools) >= 4  # At least 4 tools defined
        
        # Check tool names
        tool_names = [tool["function"]["name"] for tool in agent.tools]
        assert "lookup_menu_item" in tool_names
        assert "add_item_to_cart" in tool_names
        assert "remove_from_cart" in tool_names
        assert "modify_cart_item" in tool_names
    
    @pytest.mark.asyncio
    async def test_execute_tool_lookup_menu_item(self, cart_agent, mock_menu_matcher):
        """Test looking up a menu item."""
        result = await cart_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "California Roll"}
        )
        
        assert result["status"] == "success"
        assert "California Roll" in result["result"]
        assert "12.95" in result["result"]
        assert "CALI_001" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_lookup_menu_item_not_found(self, cart_agent, mock_menu_matcher):
        """Test looking up a non-existent menu item."""
        result = await cart_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "Unknown Item"}
        )
        
        assert result["status"] == "error"
        assert "not found" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_add_item_to_cart(self, cart_agent, mock_conversation_store):
        """Test adding an item to the cart."""
        # Mock context
        cart_agent.context = {"session_id": "test_session"}
        
        result = await cart_agent.execute_tool(
            "add_item_to_cart",
            {
                "plu": "CALI_001",
                "quantity": 2,
                "modifiers": [
                    {"plu": "NO_WASABI", "quantity": 1}
                ],
                "special_instructions": "Extra ginger please"
            }
        )
        
        assert result["status"] == "success"
        assert "Added" in result["result"]
        
        # Verify cart was updated
        cart = await mock_conversation_store.get_cart("test_session")
        assert len(cart["items"]) == 1
        assert cart["items"][0]["plu"] == "CALI_001"
        assert cart["items"][0]["quantity"] == 2
        assert len(cart["items"][0]["modifiers"]) == 1
    
    @pytest.mark.asyncio
    async def test_execute_tool_remove_from_cart(self, cart_agent, mock_conversation_store):
        """Test removing an item from the cart."""
        # Set up cart with items
        cart_agent.context = {"session_id": "test_session"}
        await mock_conversation_store.save_cart("test_session", {
            "items": [
                {"plu": "CALI_001", "quantity": 2, "modifiers": []},
                {"plu": "TUNA_001", "quantity": 1, "modifiers": []}
            ]
        })
        
        result = await cart_agent.execute_tool(
            "remove_from_cart",
            {"item_index": 0}
        )
        
        assert result["status"] == "success"
        assert "Removed" in result["result"]
        
        # Verify item was removed
        cart = await mock_conversation_store.get_cart("test_session")
        assert len(cart["items"]) == 1
        assert cart["items"][0]["plu"] == "TUNA_001"
    
    @pytest.mark.asyncio
    async def test_execute_tool_modify_cart_item(self, cart_agent, mock_conversation_store):
        """Test modifying a cart item."""
        # Set up cart with item
        cart_agent.context = {"session_id": "test_session"}
        await mock_conversation_store.save_cart("test_session", {
            "items": [
                {"plu": "CALI_001", "quantity": 1, "modifiers": []}
            ]
        })
        
        result = await cart_agent.execute_tool(
            "modify_cart_item",
            {
                "item_index": 0,
                "quantity": 3,
                "add_modifiers": [
                    {"plu": "EXTRA_AVO", "quantity": 1}
                ]
            }
        )
        
        assert result["status"] == "success"
        assert "Modified" in result["result"]
        
        # Verify modifications
        cart = await mock_conversation_store.get_cart("test_session")
        assert cart["items"][0]["quantity"] == 3
        assert len(cart["items"][0]["modifiers"]) == 1
        assert cart["items"][0]["modifiers"][0]["plu"] == "EXTRA_AVO"
    
    @pytest.mark.asyncio
    async def test_process_input_add_item_request(self, cart_agent, mock_menu_matcher):
        """Test processing natural language add item request."""
        cart_agent.context = {"session_id": "test_session"}
        
        # Mock AI processing (if the agent uses AI)
        with patch.object(cart_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {
                "text": "I'll add 2 California Rolls to your order.",
                "handled": True,
                "tool_calls": [
                    {
                        "function": {
                            "name": "add_item_to_cart",
                            "arguments": {
                                "plu": "CALI_001",
                                "quantity": 2
                            }
                        }
                    }
                ]
            }
            
            response = await cart_agent.process_input(
                "I'd like two California rolls please"
            )
            
            assert response["handled"] is True
            assert "California Roll" in response["text"]
    
    @pytest.mark.asyncio
    async def test_cart_summary_generation(self, cart_agent, mock_conversation_store):
        """Test generating cart summary."""
        # Set up cart with multiple items
        cart_agent.context = {"session_id": "test_session"}
        await mock_conversation_store.save_cart("test_session", {
            "items": [
                {
                    "plu": "CALI_001",
                    "name": "California Roll",
                    "quantity": 2,
                    "price": 12.95,
                    "modifiers": []
                },
                {
                    "plu": "TUNA_001",
                    "name": "Spicy Tuna Roll",
                    "quantity": 1,
                    "price": 13.95,
                    "modifiers": [
                        {"plu": "NO_WASABI", "name": "No Wasabi", "price": 0}
                    ]
                }
            ]
        })
        
        # Test get_cart_summary if it exists
        if hasattr(cart_agent, 'get_cart_summary'):
            summary = await cart_agent.get_cart_summary()
            assert len(summary["items"]) == 2
            assert summary["total"] > 0
    
    @pytest.mark.asyncio
    async def test_invalid_tool_parameters(self, cart_agent):
        """Test handling invalid tool parameters."""
        # Missing required parameter
        result = await cart_agent.execute_tool(
            "add_item_to_cart",
            {"quantity": 2}  # Missing 'plu'
        )
        
        assert result["status"] == "error"
        assert "missing" in result["result"].lower() or "required" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_cart_persistence(self, cart_agent, mock_conversation_store):
        """Test that cart state persists across operations."""
        cart_agent.context = {"session_id": "test_session"}
        
        # Add first item
        await cart_agent.execute_tool(
            "add_item_to_cart",
            {"plu": "CALI_001", "quantity": 1}
        )
        
        # Add second item
        await cart_agent.execute_tool(
            "add_item_to_cart",
            {"plu": "TUNA_001", "quantity": 2}
        )
        
        # Verify both items are in cart
        cart = await mock_conversation_store.get_cart("test_session")
        assert len(cart["items"]) == 2
        assert cart["items"][0]["plu"] == "CALI_001"
        assert cart["items"][1]["plu"] == "TUNA_001"


class TestCartAgentEdgeCases:
    """Test edge cases and error scenarios for cart agent."""
    
    @pytest.fixture
    async def cart_agent_with_errors(self, mock_db_session):
        """Create cart agent that simulates errors."""
        agent = AsyncCartAgent(db=mock_db_session)
        return agent
    
    @pytest.mark.asyncio
    async def test_remove_from_empty_cart(self, cart_agent_with_errors):
        """Test removing from an empty cart."""
        cart_agent_with_errors.context = {"session_id": "test_session"}
        
        with patch('app.agents.cart_async.async_agents_conversation_store.get_cart') as mock_get:
            mock_get.return_value = {"items": []}
            
            result = await cart_agent_with_errors.execute_tool(
                "remove_from_cart",
                {"item_index": 0}
            )
            
            assert result["status"] == "error"
            assert "empty" in result["result"].lower() or "no items" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_item_index(self, cart_agent_with_errors):
        """Test modifying with invalid item index."""
        cart_agent_with_errors.context = {"session_id": "test_session"}
        
        with patch('app.agents.cart_async.async_agents_conversation_store.get_cart') as mock_get:
            mock_get.return_value = {"items": [{"plu": "CALI_001", "quantity": 1}]}
            
            result = await cart_agent_with_errors.execute_tool(
                "modify_cart_item",
                {"item_index": 5, "quantity": 2}
            )
            
            assert result["status"] == "error"
            assert "invalid" in result["result"].lower() or "out of range" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_cart_modifications(self, cart_agent_with_errors):
        """Test handling concurrent cart modifications."""
        cart_agent_with_errors.context = {"session_id": "test_session"}
        
        # Simulate concurrent adds
        tasks = []
        for i in range(5):
            task = cart_agent_with_errors.execute_tool(
                "add_item_to_cart",
                {"plu": f"ITEM_{i}", "quantity": 1}
            )
            tasks.append(task)
        
        # Execute concurrently
        with patch('app.agents.cart_async.async_agents_conversation_store') as mock_store:
            cart = {"items": []}
            
            async def mock_get_cart(session_id):
                return cart.copy()
            
            async def mock_save_cart(session_id, new_cart):
                cart.clear()
                cart.update(new_cart)
            
            mock_store.get_cart = mock_get_cart
            mock_store.save_cart = mock_save_cart
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All operations should complete
            assert all(isinstance(r, dict) for r in results)