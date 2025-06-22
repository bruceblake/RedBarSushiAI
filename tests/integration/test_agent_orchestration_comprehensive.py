"""
Comprehensive integration tests for Agent Orchestration.
Tests coordination between agents, FSM, and conversation flow.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.fsm.core import ConversationState, ConversationEvent
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.cart_async import AsyncCartAgent
from app.agents.fulfillment_async import AsyncFulfillmentAgent


class TestAgentOrchestrationComprehensive:
    """Comprehensive tests for agent orchestration."""
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator instance with mocked agents."""
        orch = AsyncAgentOrchestrator()
        
        # Mock database session
        with patch('app.db_async.get_db') as mock_db:
            mock_db.return_value = AsyncMock()
            await orch.initialize()
        
        return orch
    
    @pytest.fixture
    def mock_fsm(self):
        """Create mock FSM."""
        fsm = MagicMock()
        fsm.current_state = ConversationState.GREETING
        fsm.context = {
            "call_sid": "test_123",
            "customer_name": None,
            "cart": {"items": [], "total_price": 0}
        }
        fsm.trigger = AsyncMock()
        fsm.update_context = MagicMock()
        fsm.process_transcript = AsyncMock()
        return fsm
    
    @pytest.mark.asyncio
    async def test_complete_order_flow_orchestration(self, orchestrator, mock_fsm):
        """Test complete order flow through orchestrator."""
        call_sid = "test_order_flow"
        
        with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
            # Step 1: Greeting
            mock_fsm.current_state = ConversationState.GREETING
            response = await orchestrator.process_voice_input(call_sid, "", {"first_interaction": True})
            assert response["state"] == "GREETING"
            
            # Step 2: Name provided -> MAIN_MENU
            mock_fsm.current_state = ConversationState.MAIN_MENU
            response = await orchestrator.process_voice_input(call_sid, "My name is John")
            assert response["handled"] is True
            
            # Step 3: Start order -> ORDERING
            mock_fsm.current_state = ConversationState.ORDERING
            response = await orchestrator.process_voice_input(call_sid, "I want to order")
            assert response["agent"] == "Cart"
            
            # Step 4: Order complete -> CONFIRMATION
            mock_fsm.current_state = ConversationState.CONFIRMATION
            mock_fsm.context["cart"] = {
                "items": [{"name": "California Roll", "quantity": 2, "price": 12.95}],
                "total_price": 25.90
            }
            response = await orchestrator.process_voice_input(call_sid, "That's all")
            
            # Step 5: Confirm -> FULFILLMENT
            mock_fsm.current_state = ConversationState.FULFILLMENT
            response = await orchestrator.process_voice_input(call_sid, "Yes, confirm")
            assert response["agent"] == "FulfillmentAgent"
    
    @pytest.mark.asyncio
    async def test_agent_selection_logic(self, orchestrator, mock_fsm):
        """Test correct agent selection for each state."""
        call_sid = "test_agent_selection"
        
        test_cases = [
            (ConversationState.GREETING, "FrontlineVoice"),
            (ConversationState.MAIN_MENU, "FrontlineVoice"),
            (ConversationState.ORDERING, "Cart"),
            (ConversationState.VALIDATION, "GuardrailAgent"),
            (ConversationState.CONFIRMATION, "FrontlineVoice"),
            (ConversationState.FULFILLMENT, "FulfillmentAgent"),
            (ConversationState.ESCALATION, "EscalationAgent"),
            (ConversationState.ERROR, "FrontlineVoice")
        ]
        
        with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
            for state, expected_agent in test_cases:
                mock_fsm.current_state = state
                agent, _ = await orchestrator._process_with_appropriate_agent(
                    mock_fsm, "test input", {"call_sid": call_sid}
                )
                assert expected_agent in agent.__class__.__name__
    
    @pytest.mark.asyncio
    async def test_cart_state_synchronization(self, orchestrator, mock_fsm):
        """Test cart state synchronization between agents and FSM."""
        call_sid = "test_cart_sync"
        
        # Mock conversation store with cart data
        with patch('app.utils.agent_orchestration_async.async_agents_conversation_store') as mock_store:
            mock_store.get_conversation = AsyncMock(return_value={
                "context": {
                    "cart": {
                        "items": [
                            {"plu": "SUSHI001", "name": "California Roll", "quantity": 2, "price": 12.95}
                        ],
                        "total_price": 25.90
                    }
                }
            })
            
            with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
                mock_fsm.current_state = ConversationState.ORDERING
                
                # Process cart update
                await orchestrator.process_voice_input(call_sid, "Add spicy tuna roll", {})
                
                # Verify FSM context was updated with cart
                assert mock_fsm.update_context.called
                cart_update = [call for call in mock_fsm.update_context.call_args_list 
                             if "cart" in call[0][0]]
                assert len(cart_update) > 0
    
    @pytest.mark.asyncio
    async def test_error_state_recovery(self, orchestrator, mock_fsm):
        """Test error state handling and recovery."""
        call_sid = "test_error_recovery"
        
        with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
            # Simulate error state
            mock_fsm.current_state = ConversationState.ERROR
            
            # Process recovery attempt
            response = await orchestrator.process_voice_input(
                call_sid, 
                "Can we start over?",
                {"error_context": "Previous API failure"}
            )
            
            # Should use frontline agent for recovery
            assert "FrontlineVoice" in response["agent"]
    
    @pytest.mark.asyncio
    async def test_concurrent_session_handling(self, orchestrator):
        """Test handling multiple concurrent sessions."""
        sessions = ["call_1", "call_2", "call_3"]
        
        # Start multiple sessions
        for sid in sessions:
            response = await orchestrator.start_new_conversation(sid)
            assert sid in orchestrator.active_sessions
            assert response["is_greeting"] is True
        
        # Verify each session is independent
        assert len(orchestrator.active_sessions) == 3
        
        # Process different inputs for each session
        responses = []
        for i, sid in enumerate(sessions):
            response = await orchestrator.process_voice_input(
                sid, f"My name is User{i}", {}
            )
            responses.append(response)
        
        # Each should have processed independently
        assert all(r["handled"] for r in responses)
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, orchestrator):
        """Test inactive session cleanup."""
        # Create sessions with different activity times
        import time
        current_time = time.time()
        
        orchestrator.active_sessions = {
            "old_session": {
                "started_at": current_time - 7200,  # 2 hours old
                "last_activity": current_time - 3700  # Inactive for > 1 hour
            },
            "recent_session": {
                "started_at": current_time - 600,   # 10 minutes old
                "last_activity": current_time - 60   # Active 1 minute ago
            }
        }
        
        # Clean up with 1 hour timeout
        cleaned = await orchestrator.cleanup_inactive_sessions(max_idle_time=3600)
        
        assert cleaned == 1
        assert "old_session" not in orchestrator.active_sessions
        assert "recent_session" in orchestrator.active_sessions
    
    @pytest.mark.asyncio
    async def test_interruption_handling(self, orchestrator, mock_fsm):
        """Test user interruption handling."""
        call_sid = "test_interruption"
        
        with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
            await orchestrator.handle_interruption(call_sid)
            
            # Verify interruption was recorded
            assert mock_fsm.update_context.called
            context_updates = mock_fsm.update_context.call_args[0][0]
            assert context_updates.get("user_interrupted") is True
            assert "last_interruption_time" in context_updates
    
    @pytest.mark.asyncio
    async def test_tool_call_routing(self, orchestrator, mock_fsm):
        """Test tool call routing to appropriate agents."""
        call_sid = "test_tool_routing"
        
        with patch.object(orchestrator, 'get_fsm', return_value=mock_fsm):
            # Test menu tool
            with patch.object(orchestrator.menu_agent, 'execute_tool', new_callable=AsyncMock) as mock_menu:
                mock_menu.return_value = {"success": True}
                result = await orchestrator.process_tool_call(
                    call_sid, "menu_lookup", {"item": "california roll"}, {}
                )
                assert mock_menu.called
            
            # Test cart tool
            with patch.object(orchestrator.cart_agent, 'execute_tool', new_callable=AsyncMock) as mock_cart:
                mock_cart.return_value = {"success": True}
                result = await orchestrator.process_tool_call(
                    call_sid, "cart_add_item", {"item": "spicy tuna"}, {}
                )
                assert mock_cart.called
    
    @pytest.mark.asyncio
    async def test_state_persistence_integration(self, orchestrator):
        """Test state persistence across orchestrator restarts."""
        call_sid = "test_persistence"
        
        # Start conversation and progress state
        response1 = await orchestrator.start_new_conversation(call_sid)
        await orchestrator.process_voice_input(call_sid, "John Smith", {})
        
        # Get current state
        state1 = await orchestrator.get_session_state(call_sid)
        
        # Simulate orchestrator restart
        new_orchestrator = AsyncAgentOrchestrator()
        with patch('app.db_async.get_db') as mock_db:
            mock_db.return_value = AsyncMock()
            await new_orchestrator.initialize()
        
        # Load state in new orchestrator
        state2 = await new_orchestrator.get_session_state(call_sid)
        
        # States should match
        assert state1["fsm_state"] == state2["fsm_state"]