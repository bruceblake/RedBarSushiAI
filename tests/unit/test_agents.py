"""
Unit tests for AI agents.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
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
        assert hasattr(agent, 'tools')
        assert hasattr(agent, '_menu_cache')
        assert hasattr(agent, 'instructions')
    
    @pytest.mark.asyncio
    async def test_menu_agent_process_input(self):
        """Test processing menu-related input."""
        agent = AsyncMenuAgent(db=None)
        
        # Mock the AI processing
        with patch.object(agent, 'process_with_ai') as mock_ai:
            mock_ai.return_value = {
                "response": "We have various sushi rolls available.",
                "tool_calls": [],
                "intent": "menu_inquiry"
            }
            
            result = await agent.process_input(
                "What sushi do you have?",
                {"call_sid": "test_sid"}
            )
            
            # Check the result format from process_with_ai mock
            assert "response" in result
            assert result["response"] == "We have various sushi rolls available."
    
    @pytest.mark.asyncio
    async def test_menu_agent_list_categories(self):
        """Test listing categories method."""
        agent = AsyncMenuAgent(db=None)
        
        # Test _list_categories method - it will create its own db session
        result = await agent._list_categories()
        
        assert "categories" in result
        assert isinstance(result["categories"], list)
        # Either has error or count
        assert "error" in result or "count" in result


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
    async def test_cart_agent_add_item(self):
        """Test adding item to cart."""
        agent = AsyncCartAgent(db=None)
        
        # Mock all the required dependencies
        with patch.object(agent, '_get_current_call_sid', return_value="test_call_sid"):
            with patch('app.utils.menu_db_store_async.async_menu_db_store.get_item_by_plu', 
                      new_callable=AsyncMock) as mock_get_item:
                mock_get_item.return_value = {
                    "plu": "CALI_001",
                    "name": "California Roll", 
                    "price": 1295
                }
                
                with patch('app.agents.cart_async.async_agents_conversation_store') as mock_store:
                    # Mock all the async methods
                    mock_store.get_conversation = AsyncMock(return_value={
                        "context": {"cart": {"items": [], "total_price": 0}}
                    })
                    mock_store.save_conversation = AsyncMock()
                    mock_store.add_to_cart = AsyncMock(return_value={
                        "items": [{
                            "plu": "CALI_001",
                            "name": "California Roll",
                            "quantity": 2,
                            "price": 1295
                        }],
                        "total_price": 2590
                    })
                    
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
    async def test_cart_agent_process_input(self):
        """Test processing natural language order."""
        # Create a mock database session
        mock_db = MagicMock()
        agent = AsyncCartAgent(db=mock_db)
        
        # Mock the necessary methods
        with patch.object(agent, 'process_with_ai') as mock_ai:
            mock_ai.return_value = {
                "text": "I've added 2 California Rolls to your cart.",
                "actions": [],
                "handled": True
            }
            
            # Mock the conversation store's methods
            with patch('app.agents.cart_async.async_agents_conversation_store') as mock_conv_store:
                # Mock get_conversation
                mock_conv_store.get_conversation = AsyncMock(return_value={"context": {}})
                # Mock get_cart
                mock_conv_store.get_cart = AsyncMock(return_value={
                    "items": [{"name": "California Roll", "quantity": 2}],
                    "total_price": 2590
                })
                
                result = await agent.process_input(
                    "I want two California rolls",
                    {"call_sid": "test_call_sid"}
                )
                
                assert result["text"] == "I've added 2 California Rolls to your cart."
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
        
        # Mock the database session
        mock_db = MagicMock()
        
        # Mock DeliverectService at the class level
        with patch('app.agents.fulfillment_async.DeliverectService') as mock_deliverect_class:
            # Create a mock service instance
            mock_service = MagicMock()
            mock_service.submit_order = AsyncMock(return_value={
                "success": True,
                "deliverect_order_id": "DEL123",
                "estimated_time": 15
            })
            mock_deliverect_class.return_value = mock_service
            
            # Mock create_order
            with patch('app.agents.fulfillment_async.create_order') as mock_create:
                mock_order = MagicMock()
                mock_order.id = "TEST123"
                mock_create.return_value = mock_order
                
                result = await agent.submit_order(
                    "test_call_sid",
                    order_details,
                    fsm_context,
                    db=mock_db
                )
        
        assert result["success"] is True
        assert "order_id" in result
        assert result["handled"] is True
        assert fsm_context["call_specific_data"]["next_fsm_event_name"] == "COMPLETE_INTERACTION"


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
        
        # Mock the AI processing from AIIntelligenceMixin
        with patch.object(agent, 'process_with_ai') as mock_ai:
            mock_ai.return_value = {
                "response": "Hello! Welcome to Red Bar Sushi. May I have your name please?",
                "tool_calls": [],
                "intent": "greeting"
            }
            
            result = await agent.process_voice_input(
                "Hello",
                {"call_sid": "test_call_sid"}
            )
            
            # Check the response - agent returns 'text' not 'response'
            assert "text" in result
            assert result["text"]  # Should have some text response
    
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
        agent.conversation_state = "MAIN_MENU"
        assert agent.conversation_state == "MAIN_MENU"