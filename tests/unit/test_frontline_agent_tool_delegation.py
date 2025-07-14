"""
Unit tests for Frontline Agent tool delegation optimization.

Tests the new "resolve-then-add" pattern where Frontline Agent
calls Menu Agent before Cart Agent for item additions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.agents.frontline_async_ai import FrontlineAsyncAgent
from app.config import settings


class TestFrontlineAgentToolDelegation:
    """Test suite for Frontline Agent tool delegation optimization."""
    
    @pytest.fixture
    async def frontline_agent(self):
        """Create a Frontline Agent instance for testing."""
        with patch('app.agents.frontline_async_ai.AsyncOpenAI'):
            agent = FrontlineAsyncAgent()
            # Mock the required agents
            agent.menu_agent = AsyncMock()
            agent.cart_agent = AsyncMock()
            yield agent
    
    @pytest.fixture
    def mock_menu_item(self):
        """Mock menu item response from Menu Agent."""
        return {
            "found": True,
            "item": {
                "id": "123",
                "name": "Salmon Nigiri",
                "plu": "SAL001",
                "price": 8.50,
                "category": "Nigiri",
                "description": "Fresh salmon over sushi rice"
            },
            "confidence": 0.95
        }
    
    @pytest.fixture
    def mock_cart_response(self):
        """Mock cart addition response from Cart Agent."""
        return {
            "success": True,
            "item_added": {
                "plu": "SAL001",
                "name": "Salmon Nigiri",
                "quantity": 2,
                "price": 17.00
            },
            "cart_total": 17.00,
            "message": "Added 2 Salmon Nigiri to your cart"
        }
    
    @pytest.mark.asyncio
    async def test_resolve_then_add_pattern_success(self, frontline_agent, mock_menu_item, mock_cart_response):
        """Test that Frontline Agent calls Menu Agent before Cart Agent."""
        # Setup mocks
        frontline_agent.menu_agent.search_menu_items.return_value = mock_menu_item
        frontline_agent.cart_agent.add_item_to_cart.return_value = mock_cart_response
        
        # Test data
        item_description = "2 salmon nigiri"
        context = {"call_sid": "test_call_123"}
        
        # Execute the _add_to_cart method
        result = await frontline_agent._add_to_cart(item_description, context)
        
        # Verify Menu Agent was called first
        frontline_agent.menu_agent.search_menu_items.assert_called_once()
        menu_call_args = frontline_agent.menu_agent.search_menu_items.call_args
        assert "salmon nigiri" in menu_call_args[0][0].lower()
        
        # Verify Cart Agent was called second with PLU from Menu Agent
        frontline_agent.cart_agent.add_item_to_cart.assert_called_once()
        cart_call_args = frontline_agent.cart_agent.add_item_to_cart.call_args
        assert cart_call_args[1]["plu"] == "SAL001"  # PLU from menu item
        assert cart_call_args[1]["quantity"] == 2
        
        # Verify successful result
        assert result["success"] is True
        assert "Salmon Nigiri" in result["message"]
        assert result["cart_total"] == 17.00
    
    @pytest.mark.asyncio
    async def test_menu_item_not_found_handling(self, frontline_agent):
        """Test handling when Menu Agent doesn't find the item."""
        # Setup menu agent to return not found
        frontline_agent.menu_agent.search_menu_items.return_value = {
            "found": False,
            "message": "Item not found in menu",
            "confidence": 0.1
        }
        
        # Test data
        item_description = "unicorn sushi"
        context = {"call_sid": "test_call_123"}
        
        # Execute the _add_to_cart method
        result = await frontline_agent._add_to_cart(item_description, context)
        
        # Verify Menu Agent was called
        frontline_agent.menu_agent.search_menu_items.assert_called_once()
        
        # Verify Cart Agent was NOT called
        frontline_agent.cart_agent.add_item_to_cart.assert_not_called()
        
        # Verify appropriate error response
        assert result["success"] is False
        assert "not found" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_low_confidence_menu_match_handling(self, frontline_agent):
        """Test handling when Menu Agent has low confidence match."""
        # Setup menu agent to return low confidence
        frontline_agent.menu_agent.search_menu_items.return_value = {
            "found": True,
            "item": {
                "id": "456",
                "name": "Mystery Roll",
                "plu": "MYS001",
                "price": 12.00
            },
            "confidence": 0.2  # Below threshold
        }
        
        # Test data
        item_description = "something fishy"
        context = {"call_sid": "test_call_123"}
        
        # Execute the _add_to_cart method
        result = await frontline_agent._add_to_cart(item_description, context)
        
        # Verify Menu Agent was called
        frontline_agent.menu_agent.search_menu_items.assert_called_once()
        
        # Verify Cart Agent was NOT called due to low confidence
        frontline_agent.cart_agent.add_item_to_cart.assert_not_called()
        
        # Verify clarification request
        assert result["success"] is False
        assert "clarify" in result["message"].lower() or "sure" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_cart_addition_failure_handling(self, frontline_agent, mock_menu_item):
        """Test handling when Cart Agent fails to add item."""
        # Setup mocks
        frontline_agent.menu_agent.search_menu_items.return_value = mock_menu_item
        frontline_agent.cart_agent.add_item_to_cart.return_value = {
            "success": False,
            "error": "Item unavailable",
            "message": "Sorry, Salmon Nigiri is currently unavailable"
        }
        
        # Test data
        item_description = "salmon nigiri"
        context = {"call_sid": "test_call_123"}
        
        # Execute the _add_to_cart method
        result = await frontline_agent._add_to_cart(item_description, context)
        
        # Verify both agents were called
        frontline_agent.menu_agent.search_menu_items.assert_called_once()
        frontline_agent.cart_agent.add_item_to_cart.assert_called_once()
        
        # Verify error is properly handled
        assert result["success"] is False
        assert "unavailable" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_quantity_extraction_and_parsing(self, frontline_agent, mock_cart_response):
        """Test that quantities are properly extracted and passed to Cart Agent."""
        # Setup menu mock
        frontline_agent.menu_agent.search_menu_items.return_value = {
            "found": True,
            "item": {"id": "123", "name": "Tuna Roll", "plu": "TUN001", "price": 6.50},
            "confidence": 0.9
        }
        frontline_agent.cart_agent.add_item_to_cart.return_value = mock_cart_response
        
        # Test various quantity formats
        test_cases = [
            ("3 tuna rolls", 3),
            ("five tuna rolls", 5),
            ("a dozen tuna rolls", 12),
            ("tuna roll", 1),  # Default quantity
            ("two orders of tuna rolls", 2)
        ]
        
        for description, expected_qty in test_cases:
            # Reset mocks
            frontline_agent.menu_agent.reset_mock()
            frontline_agent.cart_agent.reset_mock()
            
            # Execute test
            await frontline_agent._add_to_cart(description, {"call_sid": "test"})
            
            # Verify quantity was parsed correctly
            cart_call_args = frontline_agent.cart_agent.add_item_to_cart.call_args
            assert cart_call_args[1]["quantity"] == expected_qty, f"Failed for '{description}'"
    
    @pytest.mark.asyncio
    async def test_tool_call_order_optimization(self, frontline_agent, mock_menu_item, mock_cart_response):
        """Test that the tool calling order is optimized (Menu -> Cart, not Cart -> Menu)."""
        # Setup mocks with call tracking
        menu_call_time = None
        cart_call_time = None
        
        async def track_menu_call(*args, **kwargs):
            nonlocal menu_call_time
            menu_call_time = asyncio.get_event_loop().time()
            return mock_menu_item
        
        async def track_cart_call(*args, **kwargs):
            nonlocal cart_call_time
            cart_call_time = asyncio.get_event_loop().time()
            return mock_cart_response
        
        frontline_agent.menu_agent.search_menu_items.side_effect = track_menu_call
        frontline_agent.cart_agent.add_item_to_cart.side_effect = track_cart_call
        
        # Execute test
        await frontline_agent._add_to_cart("salmon roll", {"call_sid": "test"})
        
        # Verify Menu Agent was called before Cart Agent
        assert menu_call_time is not None, "Menu Agent was not called"
        assert cart_call_time is not None, "Cart Agent was not called"
        assert menu_call_time < cart_call_time, "Menu Agent should be called before Cart Agent"
    
    @pytest.mark.asyncio
    async def test_context_preservation_between_calls(self, frontline_agent, mock_menu_item, mock_cart_response):
        """Test that context is properly passed between Menu and Cart agents."""
        # Setup mocks
        frontline_agent.menu_agent.search_menu_items.return_value = mock_menu_item
        frontline_agent.cart_agent.add_item_to_cart.return_value = mock_cart_response
        
        # Test context
        context = {
            "call_sid": "test_call_123",
            "customer_name": "John",
            "session_id": "sess_456"
        }
        
        # Execute test
        await frontline_agent._add_to_cart("salmon", context)
        
        # Verify context was passed to both agents
        menu_call_context = frontline_agent.menu_agent.search_menu_items.call_args[1]["context"]
        cart_call_context = frontline_agent.cart_agent.add_item_to_cart.call_args[1]["context"]
        
        assert menu_call_context["call_sid"] == "test_call_123"
        assert cart_call_context["call_sid"] == "test_call_123"
        assert menu_call_context["customer_name"] == "John"
        assert cart_call_context["customer_name"] == "John"


class TestPerformanceOptimization:
    """Test performance improvements from tool delegation optimization."""
    
    @pytest.mark.asyncio
    async def test_reduced_tool_call_count(self, frontline_agent, mock_menu_item, mock_cart_response):
        """Test that the new pattern uses fewer tool calls than the old multi-hop approach."""
        # Setup mocks
        frontline_agent.menu_agent.search_menu_items.return_value = mock_menu_item
        frontline_agent.cart_agent.add_item_to_cart.return_value = mock_cart_response
        
        # Execute test
        await frontline_agent._add_to_cart("salmon", {"call_sid": "test"})
        
        # Verify only 2 tool calls were made (Menu -> Cart)
        # Previously it would have been 3-4 calls (Frontline -> Cart -> Menu -> Cart)
        assert frontline_agent.menu_agent.search_menu_items.call_count == 1
        assert frontline_agent.cart_agent.add_item_to_cart.call_count == 1
        
        # Total tool calls should be 2 (optimal)
        total_calls = (frontline_agent.menu_agent.search_menu_items.call_count + 
                      frontline_agent.cart_agent.add_item_to_cart.call_count)
        assert total_calls == 2, f"Expected 2 tool calls, got {total_calls}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])