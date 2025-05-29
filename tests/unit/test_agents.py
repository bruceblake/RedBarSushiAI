"""
Unit tests for AI agents.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.agents.base_async import BaseAsyncAgent
from app.agents.menu_async_enhanced import AsyncMenuAgent
from app.agents.cart_async import AsyncCartAgent
from app.agents.guardrail_async import AsyncGuardrailAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent
from app.agents.escalation_async import AsyncEscalationAgent
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgent


class TestBaseAgent:
    """Test base agent functionality."""
    
    @pytest.mark.asyncio
    async def test_base_agent_initialization(self):
        """Test base agent initialization."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        assert agent.name == "TestAgent"
        assert agent.tools == {}
        assert agent.logger is not None
    
    @pytest.mark.asyncio
    async def test_base_agent_tool_registration(self):
        """Test tool registration."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        async def test_tool():
            return "tool_result"
        
        agent.register_tool("test_tool", test_tool)
        
        assert "test_tool" in agent.tools
        assert agent.tools["test_tool"] == test_tool
    
    @pytest.mark.asyncio
    async def test_base_agent_tool_execution(self):
        """Test tool execution."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        async def add_numbers(a: int, b: int):
            return a + b
        
        agent.register_tool("add", add_numbers)
        
        result = await agent.execute_tool("add", {"a": 5, "b": 3})
        assert result == 8
    
    @pytest.mark.asyncio
    async def test_base_agent_invalid_tool(self):
        """Test executing invalid tool."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        with pytest.raises(ValueError, match="Unknown tool"):
            await agent.execute_tool("nonexistent", {})


class TestMenuAgent:
    """Test menu agent functionality."""
    
    @pytest.mark.asyncio
    async def test_menu_agent_initialization(self, db_session):
        """Test menu agent initialization."""
        agent = AsyncMenuAgent(db_session=db_session)
        
        assert agent.name == "MenuAgent"
        assert "get_menu_items" in agent.tools
        assert "check_availability" in agent.tools
        assert "search_menu" in agent.tools
    
    @pytest.mark.asyncio
    async def test_menu_agent_get_items(self, db_session, sample_menu_data):
        """Test getting menu items."""
        agent = AsyncMenuAgent(db_session=db_session)
        
        result = await agent.execute_tool("get_menu_items", {"category": "Sushi Rolls"})
        
        assert "items" in result
        assert len(result["items"]) == 2
        assert any(item["name"] == "California Roll" for item in result["items"])
        assert any(item["name"] == "Spicy Tuna Roll" for item in result["items"])
    
    @pytest.mark.asyncio
    async def test_menu_agent_check_availability(self, db_session, sample_menu_data):
        """Test checking item availability."""
        agent = AsyncMenuAgent(db_session=db_session)
        
        result = await agent.execute_tool(
            "check_availability", 
            {"item_name": "California Roll"}
        )
        
        assert result["available"] is True
        assert result["item"]["plu"] == "CALI_001"
    
    @pytest.mark.asyncio
    async def test_menu_agent_search(self, db_session, sample_menu_data):
        """Test menu search functionality."""
        agent = AsyncMenuAgent(db_session=db_session)
        
        result = await agent.execute_tool("search_menu", {"query": "spicy"})
        
        assert "results" in result
        assert len(result["results"]) >= 1
        assert any("Spicy" in item["name"] for item in result["results"])
    
    @pytest.mark.asyncio
    async def test_menu_agent_process_input(self, db_session, sample_menu_data, mock_openai_client):
        """Test processing natural language input."""
        agent = AsyncMenuAgent(db_session=db_session, llm_client=mock_openai_client)
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            "The California Roll is available for $12.95. It contains crab, avocado, and cucumber."
        )
        
        response = await agent.process_input("Do you have California rolls?")
        
        assert "response" in response
        assert "California Roll" in response["response"]
        assert "$12.95" in response["response"]


class TestCartAgent:
    """Test cart agent functionality."""
    
    @pytest.mark.asyncio
    async def test_cart_agent_initialization(self, db_session, mock_redis):
        """Test cart agent initialization."""
        agent = AsyncCartAgent(
            db_session=db_session,
            redis_client=mock_redis,
            session_id="test_session"
        )
        
        assert agent.name == "CartAgent"
        assert "add_to_cart" in agent.tools
        assert "remove_from_cart" in agent.tools
        assert "update_quantity" in agent.tools
        assert "get_cart" in agent.tools
    
    @pytest.mark.asyncio
    async def test_cart_agent_add_item(self, db_session, mock_redis, sample_menu_data):
        """Test adding item to cart."""
        agent = AsyncCartAgent(
            db_session=db_session,
            redis_client=mock_redis,
            session_id="test_session"
        )
        
        result = await agent.execute_tool(
            "add_to_cart",
            {
                "item_plu": "CALI_001",
                "quantity": 2,
                "modifiers": []
            }
        )
        
        assert result["success"] is True
        assert mock_redis.hset.called
    
    @pytest.mark.asyncio
    async def test_cart_agent_parse_order(self, db_session, sample_menu_data, mock_openai_client):
        """Test parsing natural language order."""
        agent = AsyncCartAgent(
            db_session=db_session,
            llm_client=mock_openai_client
        )
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            '{"items": [{"name": "California Roll", "quantity": 2, "modifiers": ["Extra Avocado"]}]}'
        )
        
        parsed = await agent._parse_order_text("I want two California rolls with extra avocado")
        
        assert len(parsed["items"]) == 1
        assert parsed["items"][0]["name"] == "California Roll"
        assert parsed["items"][0]["quantity"] == 2
        assert "Extra Avocado" in parsed["items"][0]["modifiers"]


class TestGuardrailAgent:
    """Test guardrail agent functionality."""
    
    @pytest.mark.asyncio
    async def test_guardrail_initialization(self, db_session):
        """Test guardrail agent initialization."""
        agent = AsyncGuardrailAgent(db_session=db_session)
        
        assert agent.name == "GuardrailAgent"
        assert "validate_order" in agent.tools
        assert "check_modifier_rules" in agent.tools
        assert "calculate_total" in agent.tools
    
    @pytest.mark.asyncio
    async def test_guardrail_validate_order(self, db_session, sample_menu_data):
        """Test order validation."""
        agent = AsyncGuardrailAgent(db_session=db_session)
        
        cart_data = {
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 2,
                    "modifiers": []
                }
            ]
        }
        
        result = await agent.execute_tool("validate_order", {"cart": cart_data})
        
        assert result["valid"] is True
        assert "errors" in result
        assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_guardrail_modifier_validation(self, db_session, sample_menu_data):
        """Test modifier rule validation."""
        agent = AsyncGuardrailAgent(db_session=db_session)
        
        result = await agent.execute_tool(
            "check_modifier_rules",
            {
                "item_plu": "CALI_001",
                "modifiers": ["MOD_AVO", "MOD_MAYO"]
            }
        )
        
        assert result["valid"] is True
    
    @pytest.mark.asyncio
    async def test_guardrail_price_calculation(self, db_session, sample_menu_data):
        """Test price calculation."""
        agent = AsyncGuardrailAgent(db_session=db_session)
        
        cart_data = {
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 2,
                    "modifiers": [{"plu": "MOD_AVO"}]
                }
            ]
        }
        
        result = await agent.execute_tool("calculate_total", {"cart": cart_data})
        
        # California Roll: $12.95 * 2 = $25.90
        # Extra Avocado: $2.00 * 2 = $4.00
        # Total: $29.90 = 2990 cents
        expected_total = (1295 * 2) + (200 * 2)
        assert result["total"] == expected_total
        assert result["breakdown"] is not None


class TestFulfillmentAgent:
    """Test fulfillment agent functionality."""
    
    @pytest.mark.asyncio
    async def test_fulfillment_initialization(self, db_session, mock_deliverect_client):
        """Test fulfillment agent initialization."""
        agent = AsyncFulfillmentAgent(
            db_session=db_session,
            deliverect_client=mock_deliverect_client
        )
        
        assert agent.name == "FulfillmentAgent"
        assert "submit_order" in agent.tools
        assert "get_order_status" in agent.tools
    
    @pytest.mark.asyncio
    async def test_fulfillment_submit_order(self, db_session, mock_deliverect_client, sample_menu_data):
        """Test order submission."""
        agent = AsyncFulfillmentAgent(
            db_session=db_session,
            deliverect_client=mock_deliverect_client
        )
        
        order_data = {
            "customer_name": "John Doe",
            "customer_phone": "+1234567890",
            "order_type": "pickup",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 1,
                    "modifiers": []
                }
            ]
        }
        
        result = await agent.execute_tool("submit_order", {"order": order_data})
        
        assert result["success"] is True
        assert "order_id" in result
        assert mock_deliverect_client.create_order.called


class TestEscalationAgent:
    """Test escalation agent functionality."""
    
    @pytest.mark.asyncio
    async def test_escalation_initialization(self):
        """Test escalation agent initialization."""
        agent = AsyncEscalationAgent()
        
        assert agent.name == "EscalationAgent"
        assert "transfer_to_human" in agent.tools
        assert "send_context" in agent.tools
    
    @pytest.mark.asyncio
    async def test_escalation_transfer(self, mock_twilio_client):
        """Test human transfer."""
        agent = AsyncEscalationAgent(twilio_client=mock_twilio_client)
        
        result = await agent.execute_tool(
            "transfer_to_human",
            {
                "reason": "Customer request",
                "context": {"order_status": "in_progress"}
            }
        )
        
        assert result["success"] is True
        assert "message" in result


class TestFrontlineAgent:
    """Test frontline agent functionality."""
    
    @pytest.mark.asyncio
    async def test_frontline_initialization(self, mock_openai_client):
        """Test frontline agent initialization."""
        agent = AsyncFrontlineVoiceAgent(llm_client=mock_openai_client)
        
        assert agent.name == "FrontlineVoiceAgent"
        assert "handoff_to_specialist" in agent.tools
        assert "escalate_to_human" in agent.tools
    
    @pytest.mark.asyncio
    async def test_frontline_greeting(self, mock_openai_client):
        """Test greeting generation."""
        agent = AsyncFrontlineVoiceAgent(llm_client=mock_openai_client)
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            "Hello! Welcome to Red Bar Sushi. May I have your name please?"
        )
        
        response = await agent.generate_greeting()
        
        assert "Welcome" in response
        assert "name" in response
    
    @pytest.mark.asyncio
    async def test_frontline_intent_detection(self, mock_openai_client):
        """Test intent detection for handoff."""
        agent = AsyncFrontlineVoiceAgent(llm_client=mock_openai_client)
        
        # Test menu inquiry
        result = await agent.determine_handoff("What sushi do you have?")
        assert result["agent"] == "menu"
        
        # Test order intent
        result = await agent.determine_handoff("I want to order two California rolls")
        assert result["agent"] == "cart"
        
        # Test human request
        result = await agent.determine_handoff("I need to speak to a person")
        assert result["agent"] == "escalation"