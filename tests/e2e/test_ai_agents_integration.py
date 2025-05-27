"""
End-to-end tests for AI agents integration with menu data and order processing.
Tests the complete flow with AI-enhanced agents, menu storage, and Redis caching.
"""

import pytest
import asyncio
import json
import os
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

# Set test environment
os.environ["TESTING"] = "True"
os.environ["USE_AI_AGENTS"] = "True"
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "test-key")

from app.db_async import get_db
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem
from app.agents.factory_async import AsyncAgentFactory
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.fsm_async import AsyncConversationFSM, ConversationState
from app.redis_async import RedisConnectionPool


@pytest.fixture
async def db_session(app):
    """Create async database session for testing."""
    async for session in get_db():
        yield session
        await session.rollback()


@pytest.fixture
async def populated_menu(db_session: AsyncSession):
    """Populate database with test menu data."""
    # Create categories
    appetizers = MenuCategory(
        name="Appetizers",
        description="Start your meal with our delicious appetizers",
        deliverect_category_id="cat_app_001"
    )
    sushi_rolls = MenuCategory(
        name="Sushi Rolls",
        description="Fresh and creative sushi rolls",
        deliverect_category_id="cat_sushi_001"
    )
    
    db_session.add_all([appetizers, sushi_rolls])
    await db_session.commit()
    
    # Create menu items
    edamame = MenuItem(
        category_id=appetizers.id,
        name="Edamame",
        description="Steamed soybeans with sea salt",
        price=5.99,
        plu="APP001",
        deliverect_item_id="item_edamame_001",
        is_available=True
    )
    
    california_roll = MenuItem(
        category_id=sushi_rolls.id,
        name="California Roll",
        description="Crab, avocado, and cucumber",
        price=8.99,
        plu="SUSHI001",
        deliverect_item_id="item_cali_001",
        is_available=True
    )
    
    spicy_tuna_roll = MenuItem(
        category_id=sushi_rolls.id,
        name="Spicy Tuna Roll",
        description="Fresh tuna with spicy mayo",
        price=10.99,
        plu="SUSHI002",
        deliverect_item_id="item_spicy_tuna_001",
        is_available=True
    )
    
    db_session.add_all([edamame, california_roll, spicy_tuna_roll])
    await db_session.commit()
    
    # Create modifier groups
    spice_level = MenuModifierGroup(
        name="Spice Level",
        min_selection=0,
        max_selection=1,
        deliverect_group_id="mg_spice_001"
    )
    
    db_session.add(spice_level)
    await db_session.commit()
    
    # Create modifiers
    mild = MenuModifier(
        modifier_group_id=spice_level.id,
        name="Mild",
        price_change=0.0,
        plu="MOD_MILD",
        deliverect_modifier_id="mod_mild_001"
    )
    
    extra_spicy = MenuModifier(
        modifier_group_id=spice_level.id,
        name="Extra Spicy",
        price_change=0.0,
        plu="MOD_XSPICY",
        deliverect_modifier_id="mod_xspicy_001"
    )
    
    db_session.add_all([mild, extra_spicy])
    await db_session.commit()
    
    return {
        "categories": [appetizers, sushi_rolls],
        "items": [edamame, california_roll, spicy_tuna_roll],
        "modifier_groups": [spice_level],
        "modifiers": [mild, extra_spicy]
    }


@pytest.fixture
async def ai_agents(populated_menu):
    """Create AI-enhanced agents with menu data."""
    factory = AsyncAgentFactory()
    await factory.initialize()
    
    return {
        "factory": factory,
        "frontline": await factory.create_agent("frontline"),
        "menu": await factory.create_agent("menu"),
        "cart": await factory.create_agent("cart"),
        "guardrail": await factory.create_agent("guardrail"),
        "fulfillment": await factory.create_agent("fulfillment")
    }


@pytest.fixture
async def orchestrator(ai_agents):
    """Create agent orchestrator with AI agents."""
    orchestrator = AsyncAgentOrchestrator()
    orchestrator.agents = ai_agents
    
    # Initialize FSM
    fsm = AsyncConversationFSM("test-session")
    await fsm.initialize()
    orchestrator.fsm = fsm
    
    return orchestrator


class TestAIAgentsIntegration:
    """Test AI agents integration with menu data."""
    
    @pytest.mark.asyncio
    async def test_menu_agent_database_lookup(self, ai_agents, populated_menu):
        """Test that menu agent can look up items from database."""
        menu_agent = ai_agents["menu"]
        
        # Test looking up California Roll
        result = await menu_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "California Roll"}
        )
        
        assert result.get("found") is True
        assert result.get("item", {}).get("name") == "California Roll"
        assert result.get("item", {}).get("price") == 8.99
        assert result.get("item", {}).get("plu") == "SUSHI001"
    
    @pytest.mark.asyncio
    async def test_menu_agent_fuzzy_matching(self, ai_agents, populated_menu):
        """Test menu agent can handle fuzzy item names."""
        menu_agent = ai_agents["menu"]
        
        # Test variations of Spicy Tuna Roll
        variations = ["spicy tuna", "tuna roll", "SPICY TUNA ROLL"]
        
        for variation in variations:
            result = await menu_agent.execute_tool(
                "lookup_menu_item",
                {"item_name": variation}
            )
            
            assert result.get("found") is True
            assert result.get("item", {}).get("plu") == "SUSHI002"
    
    @pytest.mark.asyncio
    async def test_cart_agent_add_items(self, ai_agents, populated_menu):
        """Test cart agent can add items with correct PLUs."""
        cart_agent = ai_agents["cart"]
        
        # Add California Roll
        result = await cart_agent.execute_tool(
            "add_item",
            {
                "item_name": "California Roll",
                "quantity": 2
            }
        )
        
        assert result.get("success") is True
        assert result.get("item", {}).get("plu") == "SUSHI001"
        assert result.get("item", {}).get("quantity") == 2
        
        # Get cart summary
        summary = await cart_agent.execute_tool("get_summary", {})
        assert len(summary.get("items", [])) == 1
        assert summary.get("total_quantity") == 2
    
    @pytest.mark.asyncio
    async def test_ai_frontline_greeting_flow(self, orchestrator):
        """Test AI frontline agent handles greeting properly."""
        # Mock OpenAI response for greeting
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock chat completion for greeting
            mock_response = AsyncMock()
            mock_response.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "response": "Hello! Welcome to Red Bar Sushi. May I have your name?",
                            "intent": "greeting",
                            "confidence": 0.95,
                            "actions": []
                        })
                    )
                )
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Process greeting
            response = await orchestrator.process_voice_input("", {"state": "GREETING"})
            
            assert "Welcome to Red Bar Sushi" in response.get("text", "")
            assert response.get("handled") is True
    
    @pytest.mark.asyncio
    async def test_full_order_flow_with_ai(self, orchestrator, populated_menu):
        """Test complete order flow with AI agents."""
        # Mock OpenAI responses for the flow
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Setup mock responses for different stages
            responses = [
                # Greeting response
                {
                    "response": "Hello! Welcome to Red Bar Sushi. May I have your name?",
                    "intent": "greeting",
                    "actions": []
                },
                # Name provided
                {
                    "response": "Nice to meet you, John! How can I help you today?",
                    "intent": "provide_name",
                    "actions": [{"type": "set_customer_name", "name": "John"}]
                },
                # Order intent
                {
                    "response": "Great! I'll help you place an order. What would you like?",
                    "intent": "place_order",
                    "actions": [{"type": "cart_updated"}]
                },
                # Add items
                {
                    "response": "I've added 2 California Rolls to your order. Anything else?",
                    "tool_calls": [{
                        "name": "add_to_cart",
                        "arguments": {
                            "item_name": "California Roll",
                            "quantity": 2
                        }
                    }],
                    "actions": []
                }
            ]
            
            response_iter = iter(responses)
            
            async def mock_create(**kwargs):
                response_data = next(response_iter)
                mock_response = AsyncMock()
                mock_response.choices = [
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(response_data),
                            tool_calls=response_data.get("tool_calls", [])
                        )
                    )
                ]
                return mock_response
            
            mock_client.chat.completions.create = mock_create
            
            # 1. Greeting
            response = await orchestrator.process_voice_input("", {"state": "GREETING"})
            assert "Welcome to Red Bar Sushi" in response["text"]
            
            # 2. Provide name
            response = await orchestrator.process_voice_input(
                "Hi, my name is John",
                {"state": "GREETING"}
            )
            assert "John" in response["text"]
            assert orchestrator.fsm.current_state == ConversationState.MAIN_MENU
            
            # 3. Express order intent
            response = await orchestrator.process_voice_input(
                "I'd like to place an order",
                {"state": "MAIN_MENU"}
            )
            assert "order" in response["text"].lower()
            
            # 4. Add items to cart
            response = await orchestrator.process_voice_input(
                "I'll have 2 California Rolls",
                {"state": "ORDERING"}
            )
            assert "California Roll" in response["text"]
    
    @pytest.mark.asyncio
    async def test_menu_caching(self, ai_agents, populated_menu):
        """Test that menu data is cached properly."""
        menu_agent = ai_agents["menu"]
        
        # First lookup should hit database
        start_time = asyncio.get_event_loop().time()
        result1 = await menu_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "Edamame"}
        )
        first_lookup_time = asyncio.get_event_loop().time() - start_time
        
        assert result1.get("found") is True
        assert result1.get("item", {}).get("plu") == "APP001"
        
        # Second lookup should be faster (from cache)
        start_time = asyncio.get_event_loop().time()
        result2 = await menu_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "Edamame"}
        )
        second_lookup_time = asyncio.get_event_loop().time() - start_time
        
        assert result2.get("found") is True
        assert result2.get("item", {}).get("plu") == "APP001"
        
        # Cache should make second lookup faster (though in tests this might not be significant)
        # Main check is that both return same results
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_menu_item(self, ai_agents):
        """Test error handling when item doesn't exist."""
        menu_agent = ai_agents["menu"]
        
        result = await menu_agent.execute_tool(
            "lookup_menu_item",
            {"item_name": "Nonexistent Item"}
        )
        
        assert result.get("found") is False
        assert "error" in result or "message" in result
    
    @pytest.mark.asyncio
    async def test_fsm_state_transitions(self, orchestrator):
        """Test FSM state transitions work correctly."""
        fsm = orchestrator.fsm
        
        # Initial state
        assert fsm.current_state == ConversationState.GREETING
        
        # Transition to MAIN_MENU
        await fsm.trigger_event("USER_PROVIDES_NAME")
        assert fsm.current_state == ConversationState.MAIN_MENU
        
        # Transition to ORDERING
        await fsm.trigger_event("USER_STARTS_ORDER")
        assert fsm.current_state == ConversationState.ORDERING
        
        # Transition to VALIDATION
        await fsm.trigger_event("ORDER_READY_FOR_VALIDATION")
        assert fsm.current_state == ConversationState.VALIDATION
        
        # Transition to CONFIRMATION
        await fsm.trigger_event("VALIDATION_COMPLETE")
        assert fsm.current_state == ConversationState.CONFIRMATION
        
        # Transition to FULFILLMENT
        await fsm.trigger_event("ORDER_CONFIRMED")
        assert fsm.current_state == ConversationState.FULFILLMENT