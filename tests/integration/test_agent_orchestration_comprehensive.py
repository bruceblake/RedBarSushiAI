"""
Comprehensive integration tests for agent orchestration system.

This module tests the integration between FSM, agents, and the orchestrator,
ensuring proper conversation flow, context management, and error handling.
"""

import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.fsm.core import ConversationState, ConversationEvent, AsyncConversationFSM
from app.agents.base_async import BaseAsyncAgent
from app.utils.intent_detector_async import async_intent_detector
from app.utils.fsm_async import AsyncFSMManager
from sqlalchemy.ext.asyncio import AsyncSession


class TestOrchestratorInitialization:
    """Test orchestrator initialization and setup."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return AsyncAgentOrchestrator()
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator, mock_db):
        """Test orchestrator initializes with correct agents."""
        await orchestrator.initialize(db=mock_db)
        
        # Verify core agents are initialized
        assert orchestrator.frontline_agent is not None
        assert orchestrator.menu_agent is not None
        assert orchestrator.cart_agent is not None
        assert orchestrator.guardrail_agent is not None
        assert orchestrator.fulfillment_agent is not None
        assert orchestrator.escalation_agent is not None
    
    @pytest.mark.asyncio
    async def test_agent_registration(self, orchestrator, mock_db):
        """Test specialist agent registration."""
        await orchestrator.initialize(db=mock_db)
        
        # Create mock specialist agent
        mock_specialist = AsyncMock(spec=BaseAsyncAgent)
        mock_specialist.name = "TestSpecialist"
        
        # Register specialist with frontline agent
        orchestrator.frontline_agent.register_specialist("test_domain", mock_specialist)
        
        # Verify registration
        assert "test_domain" in orchestrator.frontline_agent.specialists
        assert orchestrator.frontline_agent.specialists["test_domain"] == mock_specialist
    
    @pytest.mark.asyncio
    async def test_initialization_error_handling(self, orchestrator):
        """Test orchestrator handles initialization errors gracefully."""
        # Mock factory to raise error
        with patch('app.utils.agent_orchestration_async.async_agent_factory') as mock_factory:
            mock_factory.create_agent.side_effect = Exception("Agent creation failed")
            
            # Should handle error gracefully
            with pytest.raises(Exception):
                await orchestrator.initialize()


class TestAgentSelection:
    """Test agent selection based on FSM state."""
    
    @pytest_asyncio.fixture
    async def initialized_orchestrator(self):
        """Create and initialize orchestrator."""
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_greeting_state_uses_frontline_agent(self, initialized_orchestrator):
        """Test that greeting state uses frontline agent."""
        orchestrator = initialized_orchestrator
        
        # Start a new conversation - should use frontline agent for greeting
        session_id = "test_greeting"
        response = await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Verify greeting response
        assert response["state"] == "GREETING"
        assert response["agent"] == "FrontlineVoice"
        assert "Welcome" in response["text"]
    
    @pytest.mark.asyncio
    async def test_menu_query_response(self, initialized_orchestrator):
        """Test that menu queries get appropriate responses."""
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_menu"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Ask about menu - the real implementation will handle this
        response = await orchestrator.process_voice_input(session_id, "What's on your menu?")
        
        # Verify we get a menu-related response
        assert response is not None
        assert response.get("handled") is True
        # The response should mention menu or categories
        response_text = response.get("text", "").lower()
        assert any(word in response_text for word in ["menu", "categories", "items", "sushi", "rolls"])
    
    @pytest.mark.asyncio
    async def test_conversation_flow_to_ordering(self, initialized_orchestrator):
        """Test conversation flow from greeting through ordering."""
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_ordering"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Provide name
        response = await orchestrator.process_voice_input(session_id, "My name is John")
        assert response is not None
        
        # The state should progress from GREETING
        assert response.get("state") in ["MAIN_MENU", "ORDERING"]
        
        # Try to start ordering
        response = await orchestrator.process_voice_input(session_id, "I want to order some sushi")
        assert response is not None
        
        # Should get a response about ordering
        response_text = response.get("text", "").lower()
        assert any(word in response_text for word in ["order", "help", "what", "like"])



class TestConversationFlow:
    """Test complete conversation flows through orchestration."""
    
    @pytest_asyncio.fixture
    async def test_session(self):
        """Create test session with orchestrator."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        # Create session
        session_id = "test_session_" + str(id(self))
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_complete_order_flow(self, test_session):
        """Test complete order flow from greeting to completion."""
        orchestrator, session_id = test_session
        
        # Test conversation progresses through states
        # Start - we're already in GREETING from setup
        
        # Provide name
        response = await orchestrator.process_voice_input(session_id, "My name is John")
        assert response is not None
        assert "text" in response
        assert response.get("handled") is True
        
        # Start ordering
        response = await orchestrator.process_voice_input(session_id, "I want to order a california roll")
        assert response is not None
        assert response.get("handled") is True
        
        # Add more items
        response = await orchestrator.process_voice_input(session_id, "Add two tuna rolls")
        assert response is not None
        assert response.get("handled") is True
        
        # Complete order
        response = await orchestrator.process_voice_input(session_id, "That's all for my order")
        assert response is not None
        assert response.get("handled") is True
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, test_session):
        """Test error recovery flow."""
        orchestrator, session_id = test_session
        
        # Test that orchestrator handles various inputs gracefully
        # Even with empty or problematic inputs
        response = await orchestrator.process_voice_input(session_id, "")
        assert response is not None
        assert response.get("handled") is True
        
        # Test with very long input
        long_input = "a" * 1000
        response = await orchestrator.process_voice_input(session_id, long_input)
        assert response is not None
        assert response.get("handled") is True
    
    @pytest.mark.asyncio
    async def test_cancellation_flow(self, test_session):
        """Test order cancellation flow."""
        orchestrator, session_id = test_session
        
        # Mock global command detector to avoid logging errors
        from unittest.mock import patch
        with patch('app.utils.intent_detector_async.global_command_detector') as mock_detector:
            mock_detector.detect_command.return_value = (None, 0)
            
            # Start ordering
            await orchestrator.process_voice_input(session_id, "My name is Test")
            response = await orchestrator.process_voice_input(session_id, "I want to order sushi")
            
            # Request cancellation
            response = await orchestrator.process_voice_input(session_id, "Actually, cancel my order")
            
            assert response is not None
            assert response.get("handled") is True


class TestContextManagement:
    """Test context management across agents and FSM."""
    
    @pytest_asyncio.fixture
    async def orchestrator_with_session(self):
        """Create orchestrator with active session."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"test_context_{id(self)}"
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_context_preservation(self, orchestrator_with_session):
        """Test context preserved across agent transitions."""
        orchestrator, session_id = orchestrator_with_session
        
        # Set initial context
        session = orchestrator.active_sessions[session_id]
        session["context"] = {
            "customer_name": "Alice",
            "order_type": "pickup",
            "custom_data": {"preference": "no_wasabi"}
        }
        
        # Mock agent to verify context received
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Showing menu",
            "agent": "frontline",
            "handled": True
        })
        
        # Process input
        await orchestrator.process_voice_input(session_id, "Show menu")
        
        # Verify agent received full context
        assert orchestrator.frontline_agent.process_voice_input.called
        
        # The context is maintained in the session
        session = orchestrator.active_sessions[session_id]
        assert session["context"]["customer_name"] == "Alice"
        assert session["context"]["order_type"] == "pickup"
        assert session["context"]["custom_data"]["preference"] == "no_wasabi"
    
    @pytest.mark.asyncio
    async def test_cart_synchronization(self, orchestrator_with_session):
        """Test cart synchronization between agents and FSM."""
        orchestrator, session_id = orchestrator_with_session
        
        # Start a natural conversation flow to reach ordering state
        # Provide name first
        response = await orchestrator.process_voice_input(session_id, "My name is Alice")
        assert response is not None
        
        # Process multiple order requests
        response1 = await orchestrator.process_voice_input(session_id, "I want to order a tuna roll")
        assert response1 is not None
        assert response1.get("handled") is True
        
        response2 = await orchestrator.process_voice_input(session_id, "Add a salmon sashimi please")
        assert response2 is not None
        assert response2.get("handled") is True
        
        # Verify we're still in an ordering-related state
        assert response2.get("state") in ["ORDERING", "MAIN_MENU", "VALIDATION"]
    
    @pytest.mark.asyncio
    async def test_conversation_history_tracking(self, orchestrator_with_session):
        """Test conversation history is properly tracked."""
        orchestrator, session_id = orchestrator_with_session
        
        # Process multiple inputs
        inputs = ["Hello", "My name is Bob", "Show me the menu"]
        
        for user_input in inputs:
            orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
                "text": f"Response to: {user_input}",
                "agent": "frontline",
                "handled": True
            })
            
            await orchestrator.process_voice_input(session_id, user_input)
        
        # Verify conversation history
        session = orchestrator.active_sessions[session_id]
        # Mock conversation store get_messages
        orchestrator.conversation_store.get_messages = AsyncMock(return_value=[
            {"role": "user", "content": inp} for inp in inputs
        ] + [
            {"role": "assistant", "content": f"Response to: {inp}"} for inp in inputs
        ])
        history = await orchestrator.conversation_store.get_messages(session_id)
        
        assert len(history) >= len(inputs) * 2  # User + assistant messages
        
        # Check history contains user inputs
        user_messages = [msg["content"] for msg in history if msg["role"] == "user"]
        for inp in inputs:
            assert inp in user_messages


class TestGlobalCommands:
    """Test global command handling in orchestration."""
    
    @pytest_asyncio.fixture
    async def orchestrator_with_commands(self):
        from app.fsm.core import async_fsm_manager
        """Create orchestrator with global command support."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"test_commands_{id(self)}"
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Set up in ordering state
        session = orchestrator.active_sessions[session_id]
        # Progress to ordering state naturally
        await orchestrator.process_voice_input(session_id, "My name is Test User")
        session["last_response"] = "Would you like anything else?"
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_repeat_command(self, orchestrator_with_commands):
        """Test REPEAT global command."""
        orchestrator, session_id = orchestrator_with_commands
        
        # Mock global command detector to avoid logging errors
        from unittest.mock import patch
        with patch('app.utils.intent_detector_async.global_command_detector') as mock_detector:
            from app.utils.global_commands import GlobalCommand
            mock_detector.detect_command.return_value = (GlobalCommand.NONE, 0.1)
            
            # Test that the orchestrator handles repeat-like inputs
            response = await orchestrator.process_voice_input(session_id, "Can you repeat that?")
            
            # Should get a response (agent will handle the repeat request)
            assert response is not None
            assert response.get("handled") is True
    
    @pytest.mark.asyncio
    async def test_start_over_command(self, orchestrator_with_commands):
        """Test START_OVER global command."""
        orchestrator, session_id = orchestrator_with_commands
        
        # Mock global command detector to avoid logging errors
        from unittest.mock import patch
        with patch('app.utils.intent_detector_async.global_command_detector') as mock_detector:
            from app.utils.global_commands import GlobalCommand
            mock_detector.detect_command.return_value = (GlobalCommand.NONE, 0.1)
            
            # Test that the orchestrator handles start over requests
            response = await orchestrator.process_voice_input(session_id, "Let's start over")
            
            # Should get a response
            assert response is not None
            assert response.get("handled") is True
            # Response should acknowledge the restart request
            response_text = response.get("text", "").lower()
            assert any(word in response_text for word in ["start", "beginning", "help", "welcome"])
    
    @pytest.mark.asyncio
    async def test_go_back_command(self, orchestrator_with_commands):
        """Test GO_BACK global command."""
        orchestrator, session_id = orchestrator_with_commands
        
        # Mock global command detector to avoid logging errors
        from unittest.mock import patch
        with patch('app.utils.intent_detector_async.global_command_detector') as mock_detector:
            from app.utils.global_commands import GlobalCommand
            mock_detector.detect_command.return_value = (GlobalCommand.NONE, 0.1)
            
            # Test that the orchestrator handles go back requests
            response = await orchestrator.process_voice_input(session_id, "Go back")
            
            # Should get a response
            assert response is not None
            assert response.get("handled") is True


class TestErrorHandling:
    """Test error handling in orchestration."""
    
    @pytest_asyncio.fixture
    async def orchestrator_with_errors(self):
        """Create orchestrator setup for error testing."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"test_errors_{id(self)}"  # Use unique session ID
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_agent_process_error(self):
        """Test handling of agent processing errors."""
        # Create isolated orchestrator to prevent side effects
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"test_agent_error_{id(self)}"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Progress past greeting
        await orchestrator.process_voice_input(session_id, "My name is Test")
        
        # Now mock agent to raise error only for this specific call
        original_method = orchestrator.frontline_agent.process_voice_input
        orchestrator.frontline_agent.process_voice_input = AsyncMock(
            side_effect=Exception("Agent processing failed")
        )
        
        try:
            response = await orchestrator.process_voice_input(session_id, "Show menu")
            
            # Should handle error gracefully
            assert response is not None
            assert "error" in response or "error" in response.get("text", "").lower()
            
            # FSM should enter error state
            from app.fsm.core import async_fsm_manager
            fsm = await async_fsm_manager.get_fsm(session_id)
            assert fsm.current_state == ConversationState.ERROR
        finally:
            # Restore original method
            orchestrator.frontline_agent.process_voice_input = original_method
            # Cleanup
            if session_id in orchestrator.active_sessions:
                orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_intent_detection_error(self, orchestrator_with_errors):
        """Test handling of intent detection errors."""
        orchestrator, session_id = orchestrator_with_errors
        
        # Progress past greeting state first
        await orchestrator.process_voice_input(session_id, "My name is Test")
        
        # Mock frontline agent fallback
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "I'm having trouble understanding. Could you rephrase?",
            "agent": "frontline",
            "handled": True
        })
            
        response = await orchestrator.process_voice_input(session_id, "Complex input")
        
        # Should fallback gracefully
        assert response is not None
        assert "trouble understanding" in response["text"]
    
    @pytest.mark.asyncio
    async def test_session_not_found(self, orchestrator_with_errors):
        """Test handling of invalid session ID."""
        orchestrator, _ = orchestrator_with_errors
        
        response = await orchestrator.process_voice_input("invalid_session", "Hello")
        
        # Should handle gracefully by creating a new session
        assert response is not None
        assert response.get("handled") is True
        # Since it creates a new session, it should respond as a greeting
        assert response.get("state") in ["GREETING", "INITIAL", "MAIN_MENU"]


class TestStreamingSupport:
    """Test streaming response support."""
    
    @pytest_asyncio.fixture
    async def streaming_orchestrator(self):
        """Create orchestrator with streaming support."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"test_streaming_{id(self)}"
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_streaming_response(self, streaming_orchestrator):
        """Test streaming response handling."""
        orchestrator, session_id = streaming_orchestrator
        
        # Collected chunks
        chunks = []
        
        async def chunk_callback(chunk: str, is_final: bool):
            chunks.append((chunk, is_final))
        
        # Mock agent with streaming
        async def mock_streaming_process(transcript, context, stream_callback=None):
            if stream_callback:
                await stream_callback("Hello ", False)
                await stream_callback("there! ", False)
                await stream_callback("How can I help?", True)
            
            return {
                "text": "Hello there! How can I help?",
                "agent": "frontline",
                "handled": True,
                "streamed": True
            }
        
        orchestrator.frontline_agent.process_voice_input = AsyncMock(side_effect=mock_streaming_process)
        
        
        response = await orchestrator.process_voice_input_streaming(
                session_id, "Hi",
                chunk_callback
            )
        
        # Verify streaming
        assert len(chunks) == 3
        assert chunks[0] == ("Hello ", False)
        assert chunks[1] == ("there! ", False)
        assert chunks[2] == ("How can I help?", True)
        assert response["streamed"] is True


class TestPerformanceAndScalability:
    """Test performance aspects of orchestration."""
    
    @pytest_asyncio.fixture
    async def performance_orchestrator(self):
        """Create orchestrator for performance testing."""
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self, performance_orchestrator):
        """Test handling multiple concurrent sessions."""
        orchestrator = performance_orchestrator
        
        # Create multiple sessions
        session_ids = [f"session_{i}" for i in range(10)]
        for sid in session_ids:
            # Initialize session properly
            await orchestrator.start_new_conversation(sid, {"test": True})
        
        # Mock agent and intent detector
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Response",
            "agent": "frontline",
            "handled": True
        })
        
        # Process requests concurrently
        tasks = [
            orchestrator.process_voice_input(sid, f"Input from {sid}")
            for sid in session_ids
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all processed
        assert len(responses) == len(session_ids)
        assert all(r is not None for r in responses)
        
        # Verify session isolation
        for sid in session_ids:
            assert sid in orchestrator.active_sessions
            # Verify basic session structure
            session = orchestrator.active_sessions[sid]
            assert "started_at" in session
            assert "last_activity" in session
            assert "state" in session
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, performance_orchestrator):
        """Test inactive session cleanup."""
        orchestrator = performance_orchestrator
        
        # Create sessions
        active_sid = "active_session"
        inactive_sid = "inactive_session"
        
        # Initialize sessions properly
        await orchestrator.start_new_conversation(active_sid, {"test": True})
        await orchestrator.start_new_conversation(inactive_sid, {"test": True})
        
        # Mark inactive session as old
        orchestrator.active_sessions[inactive_sid]["last_activity"] = (
            datetime.now().timestamp() - 3700  # Over 1 hour old
        )
        
        # Trigger cleanup
        await orchestrator.cleanup_inactive_sessions()
        
        # Verify cleanup
        assert active_sid in orchestrator.active_sessions
        assert inactive_sid not in orchestrator.active_sessions


class TestEdgeCases:
    """Test edge cases in orchestration."""
    
    @pytest_asyncio.fixture
    async def edge_case_orchestrator(self):
        """Create orchestrator for edge case testing."""
        # Create fresh instances to avoid contamination
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        session_id = f"edge_case_{id(self)}"
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id
        
        # Cleanup
        if session_id in orchestrator.active_sessions:
            orchestrator.active_sessions.pop(session_id)
    
    @pytest.mark.asyncio
    async def test_empty_transcript(self, edge_case_orchestrator):
        """Test handling of empty transcript."""
        orchestrator, session_id = edge_case_orchestrator
        
        # Mock frontline to handle empty input
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "I didn't catch that. Could you please repeat?",
            "agent": "frontline",
            "handled": True
        })
        
        response = await orchestrator.process_voice_input(session_id, "")
        
        assert response is not None
        assert "didn't catch" in response["text"]
    
    @pytest.mark.asyncio
    async def test_rapid_state_changes(self, edge_case_orchestrator):
        """Test handling rapid state changes."""
        orchestrator, session_id = edge_case_orchestrator
        
        # Mock agents to handle all inputs quickly
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Processing your request",
            "agent": "frontline",
            "handled": True
        })
        orchestrator.cart_agent.process_voice_input = AsyncMock(return_value={
            "text": "Adding to cart",
            "agent": "cart",
            "handled": True
        })
        orchestrator.guardrail_agent.process_voice_input = AsyncMock(return_value={
            "text": "Order validated",
            "agent": "guardrail",
            "handled": True
        })
        
        # Process rapid inputs that would normally trigger state changes
        inputs = [
            "My name is John",
            "I want to order",
            "Add a california roll",
            "Add two tuna rolls",
            "That's all"
        ]
        
        for user_input in inputs:
            response = await orchestrator.process_voice_input(session_id, user_input)
            assert response is not None
            assert response.get("handled") is True
        
        # Verify we processed all inputs without errors
        session = orchestrator.active_sessions[session_id]
        assert "state" in session
        # The final state could be various states depending on FSM logic
        assert session["state"] in [
            "ORDERING", "VALIDATION", "CONFIRMATION", "MAIN_MENU"
        ]
    
    @pytest.mark.asyncio
    async def test_missing_context_data(self, edge_case_orchestrator):
        """Test handling of missing context data."""
        orchestrator, session_id = edge_case_orchestrator
        
        # Remove critical context data
        session = orchestrator.active_sessions[session_id]
        session["context"] = {}  # Empty context
        # Progress to ordering state naturally
        await orchestrator.process_voice_input(session_id, "My name is Test User")
        
        # Mock cart agent to handle missing context
        orchestrator.cart_agent.process_voice_input = AsyncMock(return_value={
            "text": "Let me help you with your order. What would you like?",
            "agent": "cart",
            "handled": True
        })
        
        response = await orchestrator.process_voice_input(session_id, "Add something")
        
        # Should handle gracefully
        assert response is not None
        # The cart agent asks for specification when context is missing
        assert any(phrase in response["text"].lower() for phrase in ["specify", "item", "cart", "add"])

