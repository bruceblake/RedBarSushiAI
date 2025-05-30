"""
Unit tests for AI agents.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.agents.base_async import BaseAsyncAgent
from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced as AsyncMenuAgent
from app.agents.cart_async import AsyncCartAgent
from app.agents.guardrail_async import AsyncGuardrailAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent
from app.agents.escalation_async import AsyncEscalationAgent
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI as AsyncFrontlineVoiceAgent


class TestBaseAgent:
    """Test base agent functionality."""
    
    @pytest.mark.asyncio
    async def test_base_agent_initialization(self):
        """Test base agent initialization."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        assert agent.name == "TestAgent"
        assert agent.agent_name == "TestAgent"  # Test the alias
        assert agent.specialists == {}
        assert agent.context == {}
        assert agent.agent_id is not None
    
    @pytest.mark.asyncio
    async def test_base_agent_specialist_registration(self):
        """Test specialist registration."""
        agent = BaseAsyncAgent(name="MainAgent")
        specialist = BaseAsyncAgent(name="SpecialistAgent")
        
        agent.register_specialist("menu", specialist)
        
        assert "menu" in agent.specialists
        assert agent.specialists["menu"] == specialist
    
    @pytest.mark.asyncio
    async def test_base_agent_context_management(self):
        """Test context management."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        # Test initial context
        assert agent.get_context() == {}
        
        # Test updating context
        agent.update_context({"user": "John", "session": "123"})
        context = agent.get_context()
        assert context["user"] == "John"
        assert context["session"] == "123"
    
    @pytest.mark.asyncio
    async def test_base_agent_process_input(self):
        """Test processing input."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        result = await agent.process_input("Hello", {"session": "123"})
        
        assert "text" in result
        assert result["agent"] == "TestAgent"
        assert result["handled"] is True
        
    @pytest.mark.asyncio 
    async def test_base_agent_execute_tool(self):
        """Test tool execution returns error for unimplemented tools."""
        agent = BaseAsyncAgent(name="TestAgent")
        
        result = await agent.execute_tool("nonexistent", {})
        
        assert result["status"] == "error"
        assert "not implemented" in result["message"]


class TestMenuAgent:
    """Test menu agent functionality."""
    
    @pytest.mark.asyncio
    async def test_menu_agent_initialization(self):
        """Test menu agent initialization."""
        agent = AsyncMenuAgent(db=None)
        
        assert agent.name == "MenuEnhanced"
        assert agent.db is None
        assert hasattr(agent, '_menu_cache')
        assert hasattr(agent, 'instructions')
    
    @pytest.mark.asyncio
    async def test_menu_agent_process_input(self):
        """Test processing menu-related input."""
        agent = AsyncMenuAgent(db=None)
        
        # Test without database (should handle gracefully)
        result = await agent.process_input("What sushi do you have?")
        
        assert "text" in result
        assert result["agent"] == "MenuEnhanced"
    
    @pytest.mark.asyncio
    async def test_menu_agent_list_categories(self):
        """Test listing categories without database."""
        agent = AsyncMenuAgent(db=None)
        
        # Without db, should handle gracefully
        result = await agent._list_categories()
        
        assert "categories" in result
        assert isinstance(result["categories"], list)


class TestCartAgent:
    """Test cart agent functionality."""
    
    @pytest.mark.asyncio
    async def test_cart_agent_initialization(self, db_session):
        """Test cart agent initialization."""
        agent = AsyncCartAgent(
            agent_id="test-123",
            db=db_session
        )
        
        assert agent.name == "Cart"
        assert agent.agent_name == "Cart"  # Test the alias
        assert agent.db == db_session
        assert agent.agent_id == "test-123"
        
        # Check tools
        assert hasattr(agent, 'tools')
        assert len(agent.tools) > 0
        
        # Check specific tools exist
        tool_names = [t["function"]["name"] for t in agent.tools]
        assert "add_item_to_cart" in tool_names
        assert "remove_from_cart" in tool_names
        assert "modify_cart_item" in tool_names
        assert "lookup_menu_item" in tool_names
        assert "get_current_cart" in tool_names
        assert "suggest_additions" in tool_names
        assert "clear_cart" in tool_names
    
    @pytest.mark.asyncio
    async def test_cart_agent_add_item(self, db_session, sample_menu_data):
        """Test adding item to cart."""
        agent = AsyncCartAgent(db=db_session)
        
        # Set a call SID for context
        agent.set_current_call("test_call_sid")
        
        # Mock the menu_db_store to return an item
        with patch('app.agents.cart_async.menu_db_store.get_item_by_plu') as mock_get_item:
            mock_get_item.return_value = {
                "plu": "CALI_001",
                "name": "California Roll",
                "price": 1295
            }
            
            # Mock the conversation store
            with patch('app.agents.cart_async.async_agents_conversation_store.add_to_cart') as mock_add:
                mock_add.return_value = {
                    "items": [{
                        "plu": "CALI_001",
                        "name": "California Roll",
                        "quantity": 2,
                        "price": 1295
                    }],
                    "total_price": 2590
                }
                
                result = await agent.execute_tool(
                    "add_item_to_cart",
                    {
                        "plu": "CALI_001",
                        "quantity": 2,
                        "modifiers": []
                    }
                )
                
                assert result["success"] is True
                assert result["total_price"] == 2590
                assert len(result["items"]) == 1
    
    @pytest.mark.asyncio
    async def test_cart_agent_process_input(self, db_session):
        """Test processing natural language order."""
        agent = AsyncCartAgent(db=db_session)
        
        # Mock the necessary methods
        with patch.object(agent, '_generate_cart_response') as mock_generate:
            mock_generate.return_value = "I've added 2 California Rolls to your cart."
            
            with patch('app.agents.cart_async.async_agents_conversation_store.get_cart') as mock_get_cart:
                mock_get_cart.return_value = {
                    "items": [{"name": "California Roll", "quantity": 2}],
                    "total_price": 2590
                }
                
                result = await agent.process_input(
                    "I want two California rolls",
                    {"call_sid": "test_call_sid"}
                )
                
                assert result["text"] == "I've added 2 California Rolls to your cart."
                assert result["agent"] == "Cart"
                assert result["handled"] is True
                assert "cart" in result


class TestGuardrailAgent:
    """Test guardrail agent functionality."""
    
    @pytest.mark.asyncio
    async def test_guardrail_initialization(self):
        """Test guardrail agent initialization."""
        agent = AsyncGuardrailAgent(agent_name="GuardrailAgent")
        
        assert agent.agent_name == "GuardrailAgent"
        assert agent.name == "GuardrailAgent"  # Test the alias
        assert hasattr(agent, 'validate_order')
        assert hasattr(agent, 'validate_modifiers')
    
    @pytest.mark.asyncio
    async def test_guardrail_validate_order(self):
        """Test order validation."""
        agent = AsyncGuardrailAgent()
        
        order_details = {
            "items": [
                {
                    "plu": "CALI_001",
                    "name": "California Roll",
                    "quantity": 2,
                    "modifiers": []
                }
            ]
        }
        
        fsm_context = {
            "call_specific_data": {}
        }
        
        result = await agent.validate_order(
            "test_call_sid",
            order_details,
            fsm_context
        )
        
        assert result["is_valid"] is True
        assert "issues" in result
        assert len(result["issues"]) == 0
        assert result["handled"] is True
    
    @pytest.mark.asyncio
    async def test_guardrail_empty_order_validation(self):
        """Test validation of empty order."""
        agent = AsyncGuardrailAgent()
        
        order_details = {
            "items": []
        }
        
        fsm_context = {
            "call_specific_data": {}
        }
        
        result = await agent.validate_order(
            "test_call_sid",
            order_details,
            fsm_context
        )
        
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert "empty" in result["issues"][0].lower()


class TestFulfillmentAgent:
    """Test fulfillment agent functionality."""
    
    @pytest.mark.asyncio
    async def test_fulfillment_initialization(self):
        """Test fulfillment agent initialization."""
        agent = AsyncFulfillmentAgent(agent_name="FulfillmentAgent")
        
        assert agent.agent_name == "FulfillmentAgent"
        assert agent.name == "FulfillmentAgent"  # Test the alias
        assert hasattr(agent, 'submit_order')
        assert hasattr(agent, 'process_input')
    
    @pytest.mark.asyncio
    async def test_fulfillment_submit_order(self):
        """Test order submission."""
        agent = AsyncFulfillmentAgent()
        
        order_details = {
            "customer_name": "John Doe",
            "customer_phone": "+1234567890",
            "order_type": "pickup",
            "items": [
                {
                    "plu": "CALI_001",
                    "name": "California Roll",
                    "quantity": 1,
                    "modifiers": []
                }
            ]
        }
        
        fsm_context = {
            "call_specific_data": {}
        }
        
        result = await agent.submit_order(
            "test_call_sid",
            order_details,
            fsm_context
        )
        
        assert result["success"] is True
        assert "order_id" in result
        assert result["handled"] is True
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "ORDER_SUBMITTED"


class TestEscalationAgent:
    """Test escalation agent functionality."""
    
    @pytest.mark.asyncio
    async def test_escalation_initialization(self):
        """Test escalation agent initialization."""
        agent = AsyncEscalationAgent()
        
        assert agent.agent_name == "EscalationAgent"
        assert agent.name == "EscalationAgent"  # Test the alias
        assert hasattr(agent, 'handle_escalation')
        assert hasattr(agent, 'process_input')
    
    @pytest.mark.asyncio
    async def test_escalation_transfer(self):
        """Test human transfer."""
        agent = AsyncEscalationAgent()
        
        context = {
            "call_specific_data": {
                "order_status": "in_progress"
            }
        }
        
        result = await agent.handle_escalation(
            "test_call_sid",
            "Customer request",
            context
        )
        
        assert result["handled"] is True
        assert "text" in result
        assert "escalation_reason" in result
        assert context["call_specific_data"]["next_fsm_event_name"] == "ESCALATION_INITIATED"


class TestFrontlineAgent:
    """Test frontline agent functionality."""
    
    @pytest.mark.asyncio
    async def test_frontline_initialization(self):
        """Test frontline agent initialization."""
        agent = AsyncFrontlineVoiceAgent(agent_id="test-123")
        
        assert agent.name == "FrontlineVoiceAI"
        assert agent.agent_name == "FrontlineVoiceAI"  # Test the alias
        assert hasattr(agent, 'tools')
        assert len(agent.tools) > 0
        
        # Check specific tools exist
        tool_names = [t["function"]["name"] for t in agent.tools]
        assert "lookup_menu_item" in tool_names
        assert "get_menu_categories" in tool_names
        assert "add_to_cart" in tool_names
        assert "update_customer_info" in tool_names
    
    @pytest.mark.asyncio
    async def test_frontline_process_input(self):
        """Test processing user input."""
        agent = AsyncFrontlineVoiceAgent()
        
        # Mock the AI response generation
        with patch.object(agent, '_generate_ai_response') as mock_generate:
            mock_generate.return_value = {
                "text": "Hello! Welcome to Red Bar Sushi. May I have your name please?",
                "tool_calls": [],
                "state_change": None
            }
            
            result = await agent.process_input(
                "Hello",
                {"call_sid": "test_call_sid"}
            )
            
            assert "Welcome" in result["text"]
            assert result["agent"] == "FrontlineVoiceAI"
    
    @pytest.mark.asyncio
    async def test_frontline_state_management(self):
        """Test conversation state management."""
        agent = AsyncFrontlineVoiceAgent()
        
        # Test initial state
        assert agent.conversation_state == "GREETING"
        assert agent.greeting_done is False
        
        # Test context updates
        agent.update_context({"customer_name": "John"})
        assert agent.context["customer_name"] == "John"
        
        # Test state transitions
        agent.conversation_state = "MAIN_MENU"
        assert agent.conversation_state == "MAIN_MENU"