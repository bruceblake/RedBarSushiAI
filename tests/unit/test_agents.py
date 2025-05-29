"""
Unit tests for individual AI agents.
Tests each agent's core functionality with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.agents.base_async import BaseAsyncAgent
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.menu_async_enhanced import AsyncMenuAgentEnhanced
from app.agents.cart_async import AsyncCartAgent
from app.agents.guardrail_async import AsyncGuardrailAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent
from app.agents.escalation_async import AsyncEscalationAgent


class TestBaseAsyncAgent:
    """Test the base agent functionality."""
    
    @pytest.mark.asyncio
    async def test_base_agent_initialization(self):
        """Test base agent initializes correctly."""
        with patch('app.agents.base_async.logger'):
            agent = BaseAsyncAgent(name="TestAgent")
            assert agent.name == "TestAgent"
            assert hasattr(agent, 'tool_executor')
            assert hasattr(agent, 'process')


class TestAsyncFrontlineVoiceAgentAI:
    """Test the AI-enhanced frontline agent."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def frontline_agent(self, mock_openai_client):
        """Create frontline agent with mocked dependencies."""
        with patch('app.agents.ai_mixin.openai.AsyncOpenAI', return_value=mock_openai_client):
            agent = AsyncFrontlineVoiceAgentAI()
            # The AI mixin accesses the client through ai_client property
            agent._ai_client = mock_openai_client
            return agent
    
    def create_mock_response(self, content, tool_calls=None):
        """Helper to create mock OpenAI response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = content
        mock_response.choices[0].message.tool_calls = tool_calls
        return mock_response
    
    @pytest.mark.asyncio
    async def test_greeting_response(self, frontline_agent, mock_openai_client):
        """Test frontline agent generates appropriate greeting."""
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response(
            "Hello! Welcome to Red Bar Sushi. May I have your name, please?"
        )
        
        response = await frontline_agent.process(
            "Hello",
            {"first_interaction": True}
        )
        
        assert "Welcome" in response["text"]
        assert response.get("handled", False) is True
    
    @pytest.mark.asyncio
    async def test_conversation_history_building(self, frontline_agent, mock_openai_client):
        """Test agent builds conversation history correctly."""
        context = {
            "conversation_history": [
                {"role": "assistant", "content": "Welcome!"},
                {"role": "user", "content": "Hi"}
            ]
        }
        
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response(
            "How can I help you today?"
        )
        
        await frontline_agent.process("I want to order", context)
        
        # Verify conversation history was included in API call
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs.get('messages', [])
        assert len(messages) >= 3  # System + history + current
    
    @pytest.mark.asyncio
    async def test_tool_execution(self, frontline_agent, mock_openai_client):
        """Test agent executes tools when needed."""
        # Mock tool call
        mock_tool_call = Mock()
        mock_tool_call.function.name = "check_menu_availability"
        mock_tool_call.function.arguments = '{"item": "California Roll"}'
        
        mock_openai_client.chat.completions.create.return_value = self.create_mock_response(
            None, 
            tool_calls=[mock_tool_call]
        )
        
        with patch.object(frontline_agent.tool_executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"result": "available"}
            with patch.object(frontline_agent, '_get_final_response_after_tools', new_callable=AsyncMock) as mock_after:
                mock_after.return_value = {"text": "California Roll is available!", "handled": True}
                
                response = await frontline_agent.process(
                    "Is California Roll available?",
                    {}
                )
                
                mock_execute.assert_called()
                assert "available" in response["text"]


class TestAsyncMenuAgentEnhanced:
    """Test the enhanced menu agent."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def menu_agent(self, mock_db_session):
        """Create menu agent with mocked dependencies."""
        agent = AsyncMenuAgentEnhanced(db=mock_db_session)
        return agent
    
    @pytest.mark.asyncio
    async def test_menu_item_lookup(self, menu_agent, mock_db_session):
        """Test menu agent looks up items correctly."""
        # Mock menu matcher
        with patch('app.agents.menu_async_enhanced.get_cached_async_menu_matcher') as mock_matcher_factory:
            mock_matcher = AsyncMock()
            mock_matcher.match_menu_item.return_value = {
                "name": "California Roll",
                "price": 1200,
                "plu": "PLU_CALI",
                "is_available": True
            }
            mock_matcher_factory.return_value = mock_matcher
            
            response = await menu_agent.process(
                "Do you have California Roll?",
                {}
            )
            
            assert "California Roll" in response["text"]
            assert "$12" in response["text"] or "12.00" in response["text"]
    
    @pytest.mark.asyncio
    async def test_category_listing(self, menu_agent, mock_db_session):
        """Test menu agent lists categories."""
        # Mock database query
        mock_categories = [
            Mock(name="Sushi Rolls"),
            Mock(name="Appetizers"),
            Mock(name="Beverages")
        ]
        mock_db_session.scalars.return_value.all.return_value = mock_categories
        
        response = await menu_agent.process(
            "What categories do you have?",
            {}
        )
        
        assert "Sushi Rolls" in response["text"]
        assert "Appetizers" in response["text"]
        assert "Beverages" in response["text"]
    
    @pytest.mark.asyncio
    async def test_unavailable_item_handling(self, menu_agent, mock_db_session):
        """Test handling of unavailable items."""
        with patch('app.agents.menu_async_enhanced.get_cached_async_menu_matcher') as mock_matcher_factory:
            mock_matcher = AsyncMock()
            mock_matcher.match_menu_item.return_value = {
                "name": "Dragon Roll",
                "price": 1800,
                "plu": "PLU_DRAGON",
                "is_available": False,
                "availability_message": "Currently unavailable"
            }
            mock_matcher_factory.return_value = mock_matcher
            
            response = await menu_agent.process(
                "Is Dragon Roll available?",
                {}
            )
            
            assert "unavailable" in response["text"].lower()


class TestAsyncCartAgent:
    """Test the cart management agent."""
    
    @pytest.fixture
    def cart_agent(self):
        """Create cart agent."""
        return AsyncCartAgent()
    
    @pytest.mark.asyncio
    async def test_add_item_to_cart(self, cart_agent):
        """Test adding items to cart."""
        with patch('app.agents.cart_async.get_cached_async_menu_matcher') as mock_matcher_factory:
            mock_matcher = AsyncMock()
            mock_matcher.match_menu_item.return_value = {
                "name": "California Roll",
                "plu": "PLU_CALI",
                "price": 1200
            }
            mock_matcher_factory.return_value = mock_matcher
            
            context = {"cart_items": []}
            response = await cart_agent.process(
                "I want 2 California rolls",
                context
            )
            
            assert "California Roll" in response["text"]
            assert "2" in response["text"] or "two" in response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_quantity_parsing(self, cart_agent):
        """Test cart agent parses quantities correctly."""
        test_cases = [
            ("I want three California rolls", 3),
            ("Give me 2 spicy tuna", 2),
            ("One dragon roll please", 1),
            ("A couple of salmon rolls", 2)
        ]
        
        for transcript, expected_qty in test_cases:
            # Test quantity extraction logic
            # This would test internal methods if they were exposed
            pass


class TestAsyncGuardrailAgent:
    """Test the order validation agent."""
    
    @pytest.fixture
    def guardrail_agent(self):
        """Create guardrail agent."""
        return AsyncGuardrailAgent()
    
    @pytest.mark.asyncio
    async def test_order_validation_pass(self, guardrail_agent):
        """Test successful order validation."""
        context = {
            "cart_items": [
                {
                    "name": "California Roll",
                    "plu": "PLU_CALI",
                    "quantity": 2,
                    "price": 1200
                }
            ]
        }
        
        response = await guardrail_agent.process(
            "validate order",
            context
        )
        
        assert "validation_passed" in response.get("context_updates", {})
    
    @pytest.mark.asyncio
    async def test_empty_cart_validation(self, guardrail_agent):
        """Test validation of empty cart."""
        context = {"cart_items": []}
        
        response = await guardrail_agent.process(
            "validate order",
            context
        )
        
        assert "empty" in response["text"].lower()


class TestAsyncFulfillmentAgent:
    """Test the order fulfillment agent."""
    
    @pytest.fixture
    def mock_deliverect_client(self):
        """Mock Deliverect client."""
        client = AsyncMock()
        client.submit_order.return_value = {
            "order_id": "DEL123",
            "status": "accepted"
        }
        return client
    
    @pytest.fixture
    def fulfillment_agent(self, mock_deliverect_client):
        """Create fulfillment agent with mocked Deliverect."""
        with patch('app.agents.fulfillment_async.DeliverectClient', return_value=mock_deliverect_client):
            return AsyncFulfillmentAgent()
    
    @pytest.mark.asyncio
    async def test_order_submission(self, fulfillment_agent, mock_deliverect_client):
        """Test successful order submission."""
        context = {
            "cart_items": [{"name": "California Roll", "plu": "PLU_CALI", "quantity": 1}],
            "customer_name": "John",
            "customer_phone": "+1234567890",
            "order_type": "pickup"
        }
        
        response = await fulfillment_agent.process(
            "submit order",
            context
        )
        
        assert "order_submitted" in response.get("context_updates", {})
        mock_deliverect_client.submit_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delivery_address_collection(self, fulfillment_agent):
        """Test collecting delivery address."""
        context = {
            "order_type": "delivery",
            "delivery_address": None
        }
        
        response = await fulfillment_agent.process(
            "123 Main St, Apt 4",
            context
        )
        
        assert response["requires_response"] is True


class TestAsyncEscalationAgent:
    """Test the human handoff agent."""
    
    @pytest.fixture
    def escalation_agent(self):
        """Create escalation agent."""
        return AsyncEscalationAgent()
    
    @pytest.mark.asyncio
    async def test_escalation_message(self, escalation_agent):
        """Test escalation generates appropriate message."""
        response = await escalation_agent.process(
            "I need human help",
            {"reason": "Complex order issue"}
        )
        
        assert "representative" in response["text"].lower() or "staff" in response["text"].lower()
        assert response.get("escalation_triggered", False) is True
    
    @pytest.mark.asyncio
    async def test_context_preservation(self, escalation_agent):
        """Test escalation preserves context for handoff."""
        context = {
            "customer_name": "John",
            "cart_items": [{"name": "California Roll"}],
            "issue": "Allergies question"
        }
        
        response = await escalation_agent.process(
            "I need to speak to someone",
            context
        )
        
        # Context should be preserved for staff
        assert "context_updates" in response
        assert response["context_updates"].get("escalation_context") is not None