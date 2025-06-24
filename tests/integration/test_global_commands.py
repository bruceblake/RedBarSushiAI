"""
Integration tests for global command handling.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.global_commands import GlobalCommand, GlobalCommandDetector
from app.fsm.core import ConversationState, ConversationEvent
from app.agents.base_async import BaseAsyncAgent


class TestGlobalCommandIntegration:
    """Test global command integration with orchestration."""
    
    @pytest_asyncio.fixture
    async def command_orchestrator(self, test_db, mock_redis, mock_openai_client):
        """Create orchestrator with global command support."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock initialization
        with patch('app.utils.agent_orchestration_async.async_agent_factory') as mock_factory:
            mock_voice_system = AsyncMock(spec=BaseAsyncAgent)
            mock_voice_system.specialist_agents = {}
            mock_factory.create_voice_agent_system.return_value = mock_voice_system
            
            # Create mock agents
            mock_agents = {}
            for agent_type in ['frontline', 'cart', 'menu', 'guardrail', 'fulfillment', 'escalation']:
                agent = AsyncMock(spec=BaseAsyncAgent)
                agent.name = agent_type
                mock_agents[agent_type] = agent
            
            async def get_agent_side_effect(agent_type, **kwargs):
                return mock_agents.get(agent_type)
            
            mock_factory.get_agent.side_effect = get_agent_side_effect
            
            await orchestrator.initialize(db=test_db)
            
            # Store mock agents for test access
            orchestrator._mock_agents = mock_agents
        
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_repeat_command_handling(self, command_orchestrator):
        """Test REPEAT command functionality."""
        orchestrator = command_orchestrator
        
        # Create session with history
        session_id = "test_repeat_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["last_response"] = "Your order total is $25.90. Would you like anything else?"
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Mock global command detection
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (GlobalCommand.REPEAT, 0.95)
            
            response = await orchestrator.process(
                session_id,
                "Can you repeat that?"
            )
        
        # Should return last response
        assert response["text"] == session["last_response"]
        assert response.get("repeated") is True
        assert response.get("global_command") == "REPEAT"
    
    @pytest.mark.asyncio
    async def test_start_over_command(self, command_orchestrator):
        """Test START_OVER command resets conversation."""
        orchestrator = command_orchestrator
        
        # Create session with order in progress
        session_id = "test_start_over_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        session["context"] = {
            "customer_name": "John",
            "cart": [
                {"name": "California Roll", "quantity": 2, "price": 12.95}
            ],
            "order_total": 25.90
        }
        
        # Mock responses
        orchestrator.frontline_agent.process = AsyncMock(return_value={
            "text": "Let's start fresh. Welcome to Red Bar Sushi! May I have your name?",
            "agent": "frontline",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (GlobalCommand.START_OVER, 0.9)
            
            response = await orchestrator.process(
                session_id,
                "Actually, let's start over"
            )
        
        # Verify reset
        assert session["fsm"].current_state == ConversationState.GREETING
        assert session["context"].get("cart") is None or len(session["context"]["cart"]) == 0
        assert session["context"].get("order_total") is None
        assert "start fresh" in response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_go_back_command(self, command_orchestrator):
        """Test GO_BACK command returns to previous state."""
        orchestrator = command_orchestrator
        
        # Create session
        session_id = "test_go_back_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        # Set up state history
        session["fsm"].current_state = ConversationState.VALIDATION
        session["fsm"].previous_state = ConversationState.ORDERING
        session["context"]["cart"] = [
            {"name": "Spicy Tuna Roll", "quantity": 1, "price": 14.95}
        ]
        
        # Mock agent response
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "No problem, let's go back to your order. You have 1 Spicy Tuna Roll. What else would you like?",
            "agent": "cart",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (GlobalCommand.GO_BACK, 0.85)
            
            response = await orchestrator.process(
                session_id,
                "Wait, go back"
            )
        
        # Should return to ordering state
        assert session["fsm"].current_state == ConversationState.ORDERING
        assert "back to your order" in response["text"]
        assert len(session["context"]["cart"]) == 1
    
    @pytest.mark.asyncio
    async def test_help_command(self, command_orchestrator):
        """Test HELP command provides assistance."""
        orchestrator = command_orchestrator
        
        session_id = "test_help_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Mock help response
        orchestrator.frontline_agent.process = AsyncMock(return_value={
            "text": (
                "I'm here to help! You can:\n"
                "- Tell me what you'd like to order\n"
                "- Ask about our menu items\n"
                "- Say 'repeat' if you need me to repeat something\n"
                "- Say 'start over' to begin a new order\n"
                "What would you like to do?"
            ),
            "agent": "frontline",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (GlobalCommand.HELP, 0.9)
            
            response = await orchestrator.process(
                session_id,
                "Help, I'm confused"
            )
        
        # Should provide helpful information
        assert "help" in response["text"].lower()
        assert "repeat" in response["text"]
        assert "start over" in response["text"]
    
    @pytest.mark.asyncio
    async def test_cancel_command(self, command_orchestrator):
        """Test CANCEL command enters cancellation flow."""
        orchestrator = command_orchestrator
        
        session_id = "test_cancel_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        session["context"]["cart"] = [
            {"name": "Salmon Sashimi", "quantity": 2, "price": 15.95}
        ]
        
        # Mock cancellation confirmation
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "Are you sure you want to cancel your order? You have 2 Salmon Sashimi in your cart.",
            "agent": "cart",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (GlobalCommand.CANCEL, 0.9)
            
            # Also mock intent detection for the cancellation event
            with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
                mock_intent.detect_intent = AsyncMock(
                    return_value=ConversationEvent.USER_REQUESTS_CANCELLATION
                )
                
                response = await orchestrator.process(
                    session_id,
                    "Cancel my order"
                )
        
        # Should enter cancellation pending state
        assert session["fsm"].current_state == ConversationState.CANCELLATION_PENDING
        assert "sure you want to cancel" in response["text"]
    
    @pytest.mark.asyncio
    async def test_command_context_preservation(self, command_orchestrator):
        """Test context is preserved when using global commands."""
        orchestrator = command_orchestrator
        
        session_id = "test_context_001"
        await orchestrator.create_session(session_id)
        
        # Set up rich context
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        original_context = {
            "customer_name": "Alice",
            "customer_phone": "+1234567890",
            "dietary_restrictions": ["vegetarian", "no nuts"],
            "cart": [
                {"name": "Vegetable Roll", "quantity": 2, "price": 10.95}
            ],
            "special_instructions": "Extra ginger please",
            "conversation_history": [
                {"role": "user", "content": "I'm vegetarian"},
                {"role": "assistant", "content": "I'll help you find vegetarian options"}
            ]
        }
        session["context"] = original_context.copy()
        
        # Test multiple global commands
        commands = [
            (GlobalCommand.REPEAT, "What did you say?"),
            (GlobalCommand.GO_BACK, "Go back please"),
            (GlobalCommand.HELP, "I need help")
        ]
        
        for command, transcript in commands:
            with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_detector:
                mock_detector.detect_command.return_value = (command, 0.9)
                
                # Mock appropriate response
                orchestrator.frontline_agent.process = AsyncMock(return_value={
                    "text": f"Handling {command.value} command",
                    "agent": "frontline",
                    "handled": True
                })
                
                await orchestrator.process(session_id, transcript)
            
            # Verify context preserved
            current_context = session["context"]
            assert current_context["customer_name"] == original_context["customer_name"]
            assert current_context["dietary_restrictions"] == original_context["dietary_restrictions"]
            assert len(current_context["cart"]) == len(original_context["cart"])
            assert current_context["special_instructions"] == original_context["special_instructions"]
    
    @pytest.mark.asyncio
    async def test_command_priority_over_intent(self, command_orchestrator):
        """Test global commands take priority over regular intents."""
        orchestrator = command_orchestrator
        
        session_id = "test_priority_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        session["last_response"] = "Would you like to add anything else?"
        
        # Set up competing detections
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_cmd:
            mock_cmd.detect_command.return_value = (GlobalCommand.REPEAT, 0.85)
            
            with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
                # Intent detector would normally detect ADD_ITEM
                mock_intent.detect_intent = AsyncMock(
                    return_value=ConversationEvent.ADD_ITEM
                )
                
                response = await orchestrator.process(
                    session_id,
                    "Can you repeat what rolls you have?"  # Ambiguous - could be REPEAT or menu query
                )
        
        # Global command should take precedence
        assert response["text"] == session["last_response"]
        assert response.get("repeated") is True
    
    @pytest.mark.asyncio
    async def test_command_with_low_confidence_fallback(self, command_orchestrator):
        """Test low confidence command detection falls back to intent."""
        orchestrator = command_orchestrator
        
        session_id = "test_fallback_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Mock cart agent for regular processing
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "I'll add that to your order.",
            "agent": "cart",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_cmd:
            # Low confidence detection
            mock_cmd.detect_command.return_value = (GlobalCommand.CANCEL, 0.3)
            
            with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
                mock_intent.detect_intent = AsyncMock(return_value=None)
                
                response = await orchestrator.process(
                    session_id,
                    "Can sell me two rolls?"  # Sounds like "cancel" but isn't
                )
        
        # Should process normally, not as cancel
        assert session["fsm"].current_state == ConversationState.ORDERING
        assert "add that to your order" in response["text"]
    
    @pytest.mark.asyncio
    async def test_command_error_recovery(self, command_orchestrator):
        """Test error recovery during command processing."""
        orchestrator = command_orchestrator
        
        session_id = "test_error_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        # No last_response set - will cause error for REPEAT
        
        # Mock fallback response
        orchestrator.frontline_agent.process = AsyncMock(return_value={
            "text": "I'm sorry, I don't have anything to repeat. How can I help you?",
            "agent": "frontline",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.global_command_detector') as mock_cmd:
            mock_cmd.detect_command.return_value = (GlobalCommand.REPEAT, 0.9)
            
            response = await orchestrator.process(
                session_id,
                "Repeat that"
            )
        
        # Should handle gracefully
        assert "don't have anything to repeat" in response["text"]
        assert session["fsm"].current_state == ConversationState.ORDERING  # State unchanged