"""
Integration tests for agent orchestration with FSM.
Tests the interaction between orchestrator, FSM, intent detector, and agents.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.agents.factory_async import AsyncAgentFactory
from app.fsm.core import ConversationState, ConversationEvent, AsyncConversationFSM
from app.utils.intent_detector_async import AsyncIntentDetector


class TestAgentOrchestrationIntegration:
    """Test agent orchestration with FSM integration."""
    
    @pytest.fixture
    async def mock_agents(self):
        """Create mock agents for testing."""
        agents = {
            'frontline': AsyncMock(name="FrontlineAgent"),
            'menu': AsyncMock(name="MenuAgent"),
            'cart': AsyncMock(name="CartAgent"),
            'guardrail': AsyncMock(name="GuardrailAgent"),
            'fulfillment': AsyncMock(name="FulfillmentAgent"),
            'escalation': AsyncMock(name="EscalationAgent")
        }
        
        # Set default responses
        for agent in agents.values():
            agent.process_input.return_value = {
                "text": "Test response",
                "requires_response": True,
                "context_updates": {}
            }
        
        return agents
    
    @pytest.fixture
    async def mock_factory(self, mock_agents):
        """Create mock agent factory."""
        factory = AsyncMock(spec=AsyncAgentFactory)
        
        async def get_agent_side_effect(agent_type):
            return mock_agents.get(agent_type)
        
        factory.get_agent.side_effect = get_agent_side_effect
        factory.create_voice_agent_system.return_value = mock_agents['frontline']
        
        return factory
    
    @pytest.fixture
    async def mock_intent_detector(self):
        """Create mock intent detector."""
        detector = AsyncMock(spec=AsyncIntentDetector)
        detector.detect_intent.return_value = None  # Default no intent
        return detector
    
    @pytest.fixture
    async def orchestrator(self, mock_factory, mock_intent_detector):
        """Create orchestrator with mocked dependencies."""
        with patch('app.utils.agent_orchestration_async.AsyncAgentFactory', return_value=mock_factory):
            with patch('app.utils.agent_orchestration_async.AsyncIntentDetector', return_value=mock_intent_detector):
                orchestrator = AsyncAgentOrchestrator(mock_factory)
                orchestrator.intent_detector = mock_intent_detector
                await orchestrator.initialize()
                return orchestrator
    
    @pytest.mark.asyncio
    async def test_complete_greeting_flow(self, orchestrator, mock_agents, mock_intent_detector):
        """Test complete greeting flow from start to main menu."""
        call_sid = "TEST_GREETING_FLOW"
        
        # Configure intent detector to return name provision event
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_PROVIDES_NAME
        
        # Configure frontline agent response
        mock_agents['frontline'].process_input.return_value = {
            "text": "Nice to meet you, John! How can I help you today?",
            "requires_response": True,
            "context_updates": {"customer_name": "John"}
        }
        
        # Process greeting
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="My name is John",
            is_final=True
        )
        
        # Verify response
        assert "Nice to meet you" in response["text"]
        assert response["requires_response"] is True
        
        # Verify FSM state transition
        fsm = await orchestrator.get_fsm(call_sid)
        assert fsm.current_state == ConversationState.MAIN_MENU
        assert fsm.context.get("customer_name") == "John"
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, orchestrator, mock_agents, mock_intent_detector):
        """Test menu inquiry flow."""
        call_sid = "TEST_MENU_FLOW"
        
        # Setup FSM in main menu state
        fsm = await orchestrator.create_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        # Configure intent detector
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_ASKS_MENU
        
        # Configure menu agent response
        mock_agents['menu'].process_input.return_value = {
            "text": "We have Sushi Rolls, Sashimi, and Appetizers. What interests you?",
            "requires_response": True,
            "agent_name": "menu"
        }
        
        # Process menu inquiry
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="What's on your menu?",
            is_final=True
        )
        
        # Verify menu agent was called
        mock_agents['menu'].process_input.assert_called_once()
        assert "Sushi Rolls" in response["text"]
    
    @pytest.mark.asyncio
    async def test_ordering_flow_with_cart_agent(self, orchestrator, mock_agents, mock_intent_detector):
        """Test ordering flow with cart agent."""
        call_sid = "TEST_ORDER_FLOW"
        
        # Setup FSM
        fsm = await orchestrator.create_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        # Configure for order start
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_STARTS_ORDER
        
        # Process order start
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="I'd like to order",
            is_final=True
        )
        
        # Verify transition to ORDERING
        assert fsm.current_state == ConversationState.ORDERING
        
        # Now add item to cart
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_ADDS_ITEM
        mock_agents['cart'].process_input.return_value = {
            "text": "I've added 2 California Rolls to your order. Anything else?",
            "requires_response": True,
            "context_updates": {
                "cart_items": [{"name": "California Roll", "quantity": 2, "plu": "PLU_CALI"}]
            }
        }
        
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="Two California rolls please",
            is_final=True
        )
        
        # Verify cart agent was called
        mock_agents['cart'].process_input.assert_called()
        assert "California Rolls" in response["text"]
        assert len(fsm.context.get("cart_items", [])) > 0
    
    @pytest.mark.asyncio
    async def test_validation_flow(self, orchestrator, mock_agents, mock_intent_detector):
        """Test order validation flow."""
        call_sid = "TEST_VALIDATION_FLOW"
        
        # Setup FSM with cart
        fsm = await orchestrator.create_fsm(call_sid)
        await fsm.transition_to(ConversationState.ORDERING)
        fsm.context["cart_items"] = [
            {"name": "California Roll", "quantity": 2, "plu": "PLU_CALI", "price": 1200}
        ]
        
        # Confirm cart to trigger validation
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_CONFIRMS_CART
        
        # Configure guardrail agent
        mock_agents['guardrail'].process_input.return_value = {
            "text": "Your order of 2 California Rolls totals $24.00. Is this correct?",
            "requires_response": True,
            "context_updates": {
                "validation_passed": True,
                "order_total": 2400
            }
        }
        
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="That's all",
            is_final=True
        )
        
        # Should transition through validation
        assert fsm.current_state in [ConversationState.VALIDATION, ConversationState.CONFIRMATION]
        mock_agents['guardrail'].process_input.assert_called()
    
    @pytest.mark.asyncio
    async def test_fulfillment_flow(self, orchestrator, mock_agents, mock_intent_detector):
        """Test order fulfillment flow."""
        call_sid = "TEST_FULFILLMENT_FLOW"
        
        # Setup FSM in confirmation state
        fsm = await orchestrator.create_fsm(call_sid)
        await fsm.transition_to(ConversationState.CONFIRMATION)
        fsm.context.update({
            "cart_items": [{"name": "California Roll", "quantity": 1, "plu": "PLU_CALI"}],
            "order_total": 1200,
            "validation_passed": True
        })
        
        # Confirm order
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_CONFIRMS_ORDER
        
        # Configure fulfillment agent
        mock_agents['fulfillment'].process_input.return_value = {
            "text": "Order submitted! Your order will be ready in 15 minutes.",
            "requires_response": False,
            "context_updates": {
                "order_id": "ORD123",
                "order_submitted": True
            }
        }
        
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="Yes, that's correct",
            is_final=True
        )
        
        # Verify fulfillment
        assert fsm.current_state == ConversationState.FULFILLMENT
        mock_agents['fulfillment'].process_input.assert_called()
        assert "submitted" in response["text"]
    
    @pytest.mark.asyncio
    async def test_escalation_from_any_state(self, orchestrator, mock_agents, mock_intent_detector):
        """Test escalation can be triggered from any state."""
        call_sid = "TEST_ESCALATION"
        
        # Test escalation from MAIN_MENU
        fsm = await orchestrator.create_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        # Configure for escalation
        mock_intent_detector.detect_intent.return_value = ConversationEvent.USER_REQUESTS_HUMAN
        mock_agents['escalation'].process_input.return_value = {
            "text": "I'll connect you with a staff member right away.",
            "requires_response": False,
            "escalation_triggered": True
        }
        
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="I need to speak to a person",
            is_final=True
        )
        
        # Verify escalation
        assert fsm.current_state == ConversationState.ESCALATION
        mock_agents['escalation'].process_input.assert_called()
        assert response.get("escalation_triggered") is True
    
    @pytest.mark.asyncio
    async def test_agent_selection_by_state(self, orchestrator, mock_agents):
        """Test correct agent selection based on FSM state."""
        call_sid = "TEST_AGENT_SELECTION"
        
        # Test state to agent mapping
        state_agent_map = {
            ConversationState.GREETING: 'frontline',
            ConversationState.MAIN_MENU: 'frontline',
            ConversationState.ORDERING: 'cart',
            ConversationState.VALIDATION: 'guardrail',
            ConversationState.CONFIRMATION: 'frontline',
            ConversationState.FULFILLMENT: 'fulfillment',
            ConversationState.ESCALATION: 'escalation'
        }
        
        for state, expected_agent in state_agent_map.items():
            # Reset mocks
            for agent in mock_agents.values():
                agent.process_input.reset_mock()
            
            # Set FSM state
            fsm = await orchestrator.get_fsm(call_sid)
            await fsm.transition_to(state)
            
            # Process input
            await orchestrator.process_voice_input(
                call_sid=call_sid,
                transcript="Test input",
                is_final=True
            )
            
            # Verify correct agent was called
            if expected_agent in mock_agents:
                mock_agents[expected_agent].process_input.assert_called()
    
    @pytest.mark.asyncio
    async def test_context_updates_propagation(self, orchestrator, mock_agents):
        """Test context updates from agents are properly propagated."""
        call_sid = "TEST_CONTEXT_UPDATES"
        
        # Configure agent to return context updates
        mock_agents['frontline'].process_input.return_value = {
            "text": "Response",
            "requires_response": True,
            "context_updates": {
                "customer_name": "Jane",
                "preferences": ["no spicy"]
            }
        }
        
        # Process input
        await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="My name is Jane and I don't like spicy food",
            is_final=True
        )
        
        # Verify context was updated
        fsm = await orchestrator.get_fsm(call_sid)
        assert fsm.context.get("customer_name") == "Jane"
        assert "no spicy" in fsm.context.get("preferences", [])
    
    @pytest.mark.asyncio
    async def test_error_handling_with_fallback(self, orchestrator, mock_agents):
        """Test error handling provides graceful fallback."""
        call_sid = "TEST_ERROR_HANDLING"
        
        # Make agent raise error
        mock_agents['frontline'].process_input.side_effect = Exception("Agent error")
        
        # Process input
        response = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="Hello",
            is_final=True
        )
        
        # Should get fallback response
        assert "trouble" in response["text"].lower() or "sorry" in response["text"].lower()
        assert response["requires_response"] is True
    
    @pytest.mark.asyncio
    async def test_fsm_persistence_across_calls(self, orchestrator):
        """Test FSM state persists across multiple calls."""
        call_sid = "TEST_PERSISTENCE"
        
        # First interaction
        fsm1 = await orchestrator.create_fsm(call_sid)
        fsm1.context["test_value"] = "preserved"
        await fsm1.transition_to(ConversationState.MAIN_MENU)
        
        # Second interaction (simulating new request)
        fsm2 = await orchestrator.get_fsm(call_sid)
        
        # State and context should be preserved
        assert fsm2.current_state == ConversationState.MAIN_MENU
        assert fsm2.context.get("test_value") == "preserved"