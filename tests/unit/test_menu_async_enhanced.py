"""
Unit tests for AsyncMenuAgentEnhanced class.

This module tests the enhanced menu agent functionality including
menu lookup, recommendations, and dietary handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
from app.models.menu_async import MenuItem, MenuCategory


class TestAsyncMenuAgentEnhanced:
    """Test suite for AsyncMenuAgentEnhanced class."""
    
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
        with patch('app.agents.menu_async_enhanced.get_cached_async_menu_matcher') as mock_get_matcher:
            matcher = MagicMock()
            
            async def mock_match_item(item_name, context=None):
                if "california roll" in item_name.lower():
                    return {
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "price": 12.95,
                        "description": "Crab, avocado, cucumber"
                    }
                return None
            
            matcher.match_menu_item = mock_match_item
            mock_get_matcher.return_value = matcher
            yield matcher
    
    @pytest.fixture
    def mock_crud_operations(self):
        """Mock CRUD operations."""
        with patch.multiple('app.agents.menu_async_enhanced',
                          get_all_categories=AsyncMock(),
                          get_items_by_category=AsyncMock(),
                          get_item_by_plu=AsyncMock(),
                          search_menu_items=AsyncMock()) as mocks:
            
            # Mock get_all_categories
            mocks['get_all_categories'].return_value = [
                {"id": 1, "name": "Rolls", "description": "Sushi rolls"},
                {"id": 2, "name": "Sashimi", "description": "Fresh sashimi"},
                {"id": 3, "name": "Appetizers", "description": "Starters"}
            ]
            
            # Mock get_items_by_category
            async def mock_get_items(db, category_name):
                if category_name.lower() == "rolls":
                    return [
                        {
                            "plu": "CALI_001",
                            "name": "California Roll",
                            "price": 12.95,
                            "description": "Crab, avocado, cucumber",
                            "available": True
                        },
                        {
                            "plu": "TUNA_001",
                            "name": "Spicy Tuna Roll",
                            "price": 13.95,
                            "description": "Spicy tuna, cucumber",
                            "available": True
                        }
                    ]
                return []
            
            mocks['get_items_by_category'].side_effect = mock_get_items
            
            # Mock get_item_by_plu
            async def mock_get_by_plu(db, plu):
                if plu == "CALI_001":
                    return {
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "price": 12.95,
                        "description": "Crab, avocado, cucumber",
                        "available": True,
                        "modifiers": []
                    }
                return None
            
            mocks['get_item_by_plu'].side_effect = mock_get_by_plu
            
            # Mock search_menu_items
            async def mock_search(db, keyword, limit=5):
                if "california" in keyword.lower():
                    return [{
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "price": 12.95,
                        "score": 0.95
                    }]
                return []
            
            mocks['search_menu_items'].side_effect = mock_search
            
            yield mocks
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch('app.agents.ai_mixin.openai') as mock_openai:
            mock_client = MagicMock()
            mock_openai.AsyncOpenAI.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Here are our rolls"
            mock_response.choices[0].message.tool_calls = None
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            yield mock_client
    
    @pytest.fixture
    async def menu_agent(self, mock_db_session, mock_menu_matcher, mock_crud_operations, mock_openai_client):
        """Create a menu agent instance for testing."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncMenuAgentEnhanced(agent_id="test_menu_123", db=mock_db_session)
            agent._init_ai_client()
            return agent
    
    def test_initialization(self, mock_db_session, mock_openai_client):
        """Test menu agent initialization."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncMenuAgentEnhanced(agent_id="custom_menu", db=mock_db_session)
            
            assert agent.name == "MenuEnhanced"
            assert agent.agent_id == "custom_menu"
            assert agent.db == mock_db_session
            assert agent._cache_ttl == 300
            assert len(agent.tools) >= 5
            assert "Red Bar Sushi" in agent.instructions
    
    @pytest.mark.asyncio
    async def test_execute_tool_lookup_menu_item(self, menu_agent, mock_menu_matcher):
        """Test looking up a menu item."""
        result = await menu_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "California Roll"}
        )
        
        assert result["status"] == "success"
        assert "California Roll" in result["result"]
        assert "$12.95" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_list_categories(self, menu_agent, mock_crud_operations):
        """Test listing menu categories."""
        result = await menu_agent.execute_tool("list_categories", {})
        
        assert result["status"] == "success"
        assert "Rolls" in result["result"]
        assert "Sashimi" in result["result"]
        assert "Appetizers" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_get_items_by_category(self, menu_agent, mock_crud_operations):
        """Test getting items by category."""
        result = await menu_agent.execute_tool(
            "get_items_by_category",
            {"category_name": "Rolls"}
        )
        
        assert result["status"] == "success"
        assert "California Roll" in result["result"]
        assert "Spicy Tuna Roll" in result["result"]
        assert "$12.95" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_search_menu(self, menu_agent, mock_crud_operations):
        """Test searching menu items."""
        result = await menu_agent.execute_tool(
            "search_menu",
            {"keyword": "california", "max_results": 5}
        )
        
        assert result["status"] == "success"
        assert "California Roll" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_get_item_details(self, menu_agent, mock_crud_operations):
        """Test getting detailed item information."""
        result = await menu_agent.execute_tool(
            "get_item_details",
            {"item_plu": "CALI_001"}
        )
        
        assert result["status"] == "success"
        assert "California Roll" in result["result"]
        assert "Crab, avocado, cucumber" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_check_availability(self, menu_agent, mock_crud_operations):
        """Test checking item availability."""
        result = await menu_agent.execute_tool(
            "check_availability",
            {"item_plu": "CALI_001"}
        )
        
        assert result["status"] == "success"
        assert "available" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_process_input_with_ai(self, menu_agent, mock_openai_client):
        """Test processing input with AI assistance."""
        # Mock AI response with tool call
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Let me show you our rolls."
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                function=MagicMock(
                    name="list_categories",
                    arguments='{}'
                )
            )
        ]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await menu_agent.process_input("What kind of food do you have?")
        
        assert response["handled"] is True
        assert response["agent"] == "MenuEnhanced"
        assert "rolls" in response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_dietary_restriction_handling(self, menu_agent, mock_openai_client, mock_crud_operations):
        """Test handling dietary restrictions."""
        # Mock search to return vegetarian items
        async def mock_veg_search(db, keyword, limit=5):
            if "vegetarian" in keyword.lower():
                return [
                    {"plu": "VEG_001", "name": "Vegetable Roll", "price": 10.95},
                    {"plu": "AVO_001", "name": "Avocado Roll", "price": 9.95}
                ]
            return []
        
        mock_crud_operations['search_menu_items'].side_effect = mock_veg_search
        
        result = await menu_agent.execute_tool(
            "search_menu",
            {"keyword": "vegetarian"}
        )
        
        assert result["status"] == "success"
        assert "Vegetable Roll" in result["result"]
        assert "Avocado Roll" in result["result"]
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, menu_agent):
        """Test menu caching functionality."""
        # First lookup - should hit database
        menu_agent._menu_cache = {}
        
        # Simulate caching an item
        cache_key = "item:CALI_001"
        cached_data = {
            "plu": "CALI_001",
            "name": "California Roll",
            "price": 12.95
        }
        menu_agent._menu_cache[cache_key] = cached_data
        
        # Verify cache is used
        assert menu_agent._menu_cache[cache_key] == cached_data
        assert len(menu_agent._menu_cache) == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_database_error(self, menu_agent, mock_crud_operations):
        """Test handling database errors gracefully."""
        # Mock database error
        mock_crud_operations['get_all_categories'].side_effect = Exception("Database connection error")
        
        result = await menu_agent.execute_tool("list_categories", {})
        
        assert result["status"] == "error"
        assert "error" in result["result"].lower()
    
    @pytest.mark.asyncio
    async def test_recommendation_generation(self, menu_agent, mock_openai_client):
        """Test generating menu recommendations."""
        # Mock AI response for recommendations
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I recommend our California Roll and Spicy Tuna Roll."
        mock_response.choices[0].message.tool_calls = None
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await menu_agent.process_input("What do you recommend?")
        
        assert response["handled"] is True
        assert "recommend" in response["text"].lower()
        assert "california roll" in response["text"].lower() or "spicy tuna" in response["text"].lower()


class TestMenuAgentIntegration:
    """Integration tests for menu agent with other components."""
    
    @pytest.fixture
    async def integrated_menu_agent(self, mock_db_session, mock_openai_client):
        """Create menu agent with real integrations."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncMenuAgentEnhanced(db=mock_db_session)
            agent._init_ai_client()
            return agent
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, integrated_menu_agent, mock_crud_operations):
        """Test complete menu inquiry flow."""
        # Customer asks about rolls
        result1 = await integrated_menu_agent.execute_tool(
            "get_items_by_category",
            {"category_name": "Rolls"}
        )
        assert result1["status"] == "success"
        
        # Customer asks for details
        result2 = await integrated_menu_agent.execute_tool(
            "get_item_details",
            {"item_plu": "CALI_001"}
        )
        assert result2["status"] == "success"
        
        # Check availability
        result3 = await integrated_menu_agent.execute_tool(
            "check_availability",
            {"item_plu": "CALI_001"}
        )
        assert result3["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_concurrent_menu_lookups(self, integrated_menu_agent, mock_crud_operations):
        """Test handling concurrent menu lookups."""
        # Simulate multiple concurrent lookups
        tasks = [
            integrated_menu_agent.execute_tool("lookup_menu_item", {"item_name": "California Roll"}),
            integrated_menu_agent.execute_tool("lookup_menu_item", {"item_name": "Spicy Tuna Roll"}),
            integrated_menu_agent.execute_tool("list_categories", {}),
            integrated_menu_agent.execute_tool("search_menu", {"keyword": "roll"})
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete successfully
        assert all(isinstance(r, dict) and r.get("status") == "success" for r in results)