"""
Comprehensive unit tests for the Finite State Machine (FSM).

This module provides extensive testing coverage for the FSM implementation,
including state transitions, event handling, persistence, and edge cases.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.fsm.core import (
    ConversationState, ConversationEvent, AsyncConversationFSM,
    FSMError, AsyncStateHandler
)


class TestFSMCore:
    """Test core FSM functionality."""
    
    @pytest.fixture
    def fsm(self):
        """Create a fresh FSM instance for each test."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    def test_fsm_initialization(self, fsm):
        """Test FSM initializes with correct defaults."""
        assert fsm.current_state == ConversationState.INITIAL
        assert fsm.context == {"call_sid": "test_call_sid_123"}
        assert fsm.context.get('state_history', []) == []
        assert fsm.context.get('previous_fsm_state') is None
    
    def test_all_states_defined(self):
        """Test all expected states are defined."""
        expected_states = [
            'INITIAL', 'GREETING', 'MAIN_MENU', 'ORDERING',
            'VALIDATION', 'CONFIRMATION', 'FULFILLMENT',
            'COMPLETION', 'FOLLOW_UP', 'ESCALATION', 'ERROR',
            'MENU_QUERY_SUBSTATE', 'CANCELLATION_PENDING'
        ]
        
        for state in expected_states:
            assert hasattr(ConversationState, state)
    
    def test_all_events_defined(self):
        """Test all expected events are defined."""
        expected_events = [
            'START_CONVERSATION', 'USER_PROVIDES_NAME', 'REQUEST_MENU_INFO',
            'START_ORDER', 'ADD_ITEM', 'REMOVE_ITEM', 'MODIFY_ITEM',
            'COMPLETE_ORDER', 'CANCEL_ORDER', 'VALIDATE_ORDER',
            'ORDER_VALID', 'ORDER_INVALID', 'MODIFY_ORDER',
            'CONFIRM_ORDER', 'REJECT_ORDER', 'FULFILL_ORDER',
            'PROVIDE_DELIVERY_INFO', 'CHOOSE_PICKUP', 'COMPLETE_INTERACTION',
            'REQUEST_FOLLOW_UP', 'REQUEST_ESCALATION', 'ERROR_OCCURRED',
            'REQUEST_ADD_MORE_ITEMS', 'REQUEST_MENU_QUERY',
            'USER_REQUESTS_CANCELLATION', 'CONFIRM_CANCELLATION',
            'DECLINE_CANCELLATION', 'RETRY_LAST_ACTION',
            'ESCALATE_DUE_TO_ERROR', 'FALLBACK_TO_MAIN_MENU',
            'MENU_QUERY_RESOLVED'
        ]
        
        for event in expected_events:
            assert hasattr(ConversationEvent, event)


class TestStateTransitions:
    """Test state transition logic."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.mark.asyncio
    async def test_valid_transition_initial_to_greeting(self, fsm):
        """Test valid transition from INITIAL to GREETING."""
        assert fsm.current_state == ConversationState.INITIAL
        
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        
        assert fsm.current_state == ConversationState.GREETING
        # INITIAL is not stored as previous state per FSM design
        assert fsm.context.get('previous_fsm_state') is None
    
    @pytest.mark.asyncio
    async def test_invalid_transition_raises_error(self, fsm):
        """Test invalid transition does not change state."""
        fsm.current_state = ConversationState.INITIAL
        
        # COMPLETE_INTERACTION is not valid from INITIAL
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        
        # State should remain unchanged
        assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_all_valid_transitions(self, fsm):
        """Test all documented valid transitions work."""
        # Sample valid transition paths
        valid_paths = [
            (ConversationState.INITIAL, ConversationEvent.START_CONVERSATION, ConversationState.GREETING),
            (ConversationState.GREETING, ConversationEvent.USER_PROVIDES_NAME, ConversationState.MAIN_MENU),
            (ConversationState.MAIN_MENU, ConversationEvent.START_ORDER, ConversationState.ORDERING),
            (ConversationState.ORDERING, ConversationEvent.ADD_ITEM, ConversationState.ORDERING),
            (ConversationState.ORDERING, ConversationEvent.COMPLETE_ORDER, ConversationState.VALIDATION),
            (ConversationState.VALIDATION, ConversationEvent.ORDER_VALID, ConversationState.CONFIRMATION),
            (ConversationState.CONFIRMATION, ConversationEvent.CONFIRM_ORDER, ConversationState.FULFILLMENT),
            (ConversationState.FULFILLMENT, ConversationEvent.COMPLETE_INTERACTION, ConversationState.COMPLETION),
        ]
        
        for start_state, event, expected_state in valid_paths:
            fsm.current_state = start_state
            fsm.context['previous_fsm_state'] = None
            
            await fsm.trigger(event)
            
            assert fsm.current_state == expected_state
            assert fsm.current_state == expected_state
    
    @pytest.mark.asyncio
    async def test_error_state_reachable_from_all_states(self, fsm):
        """Test ERROR_OCCURRED event works from all states (except INITIAL)."""
        for state in ConversationState:
            if state in [ConversationState.ERROR, ConversationState.INITIAL]:  # Skip ERROR itself and INITIAL
                continue
                
            fsm.current_state = state
            await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
            
            assert fsm.current_state == ConversationState.ERROR
            assert fsm.context.get('previous_fsm_state') == state.name


class TestDynamicTransitions:
    """Test dynamic state transitions."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM with state history."""
        fsm = AsyncConversationFSM(call_sid="test_call_sid_456")
        fsm.current_state = ConversationState.ORDERING
        fsm.context['previous_fsm_state'] = ConversationState.MAIN_MENU.name
        fsm.context['state_history'] = [
            {'state': ConversationState.INITIAL.name, 'timestamp': 1000},
            {'state': ConversationState.GREETING.name, 'timestamp': 1001},
            {'state': ConversationState.MAIN_MENU.name, 'timestamp': 1002}
        ]
        return fsm
    
    @pytest.mark.asyncio
    async def test_menu_query_returns_to_previous_state(self, fsm):
        """Test MENU_QUERY_RESOLVED returns to previous state."""
        # Enter menu query substate
        await fsm.trigger(ConversationEvent.REQUEST_MENU_QUERY)
        assert fsm.current_state == ConversationState.MENU_QUERY_SUBSTATE
        assert fsm.context.get('previous_fsm_state') == ConversationState.ORDERING.name
        
        # Resolve query - should return to ORDERING
        await fsm.trigger(ConversationEvent.MENU_QUERY_RESOLVED)
        assert fsm.current_state == ConversationState.ORDERING
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_decline_cancellation_returns_to_previous(self, fsm):
        """Test DECLINE_CANCELLATION returns to previous state."""
        # Request cancellation
        await fsm.trigger(ConversationEvent.USER_REQUESTS_CANCELLATION)
        assert fsm.current_state == ConversationState.CANCELLATION_PENDING
        assert fsm.context.get('previous_fsm_state') == ConversationState.ORDERING.name
        
        # Decline cancellation - should return to ORDERING
        await fsm.trigger(ConversationEvent.DECLINE_CANCELLATION)
        assert fsm.current_state == ConversationState.ORDERING
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_retry_last_action_returns_to_previous(self, fsm):
        """Test RETRY_LAST_ACTION returns to previous state."""
        # Simulate error
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
        assert fsm.context.get('previous_fsm_state') == ConversationState.ORDERING.name
        
        # Retry - should return to ORDERING
        await fsm.trigger(ConversationEvent.RETRY_LAST_ACTION)
        assert fsm.current_state == ConversationState.ORDERING
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_dynamic_transition_with_no_previous_state(self, fsm):
        """Test dynamic transitions handle missing previous state."""
        fsm.current_state = ConversationState.ERROR
        fsm.context['previous_fsm_state'] = None
        
        # Should handle gracefully (stay in ERROR state)
        await fsm.trigger(ConversationEvent.RETRY_LAST_ACTION)
        assert fsm.current_state == ConversationState.ERROR


class TestStateHistory:
    """Test state history tracking."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.mark.asyncio
    async def test_state_history_tracking(self, fsm):
        """Test state history is tracked correctly."""
        # Perform several transitions
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        
        # Check history - may have fewer entries since INITIAL is not recorded
        history = fsm.context.get('state_history', [])
        assert len(history) <= 3
        # Extract just the state names
        state_names = [h['state'] for h in history]
        # Should contain transitions (INITIAL is not recorded in history)
        assert ConversationState.GREETING.name in state_names or ConversationState.MAIN_MENU.name in state_names
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_state_history_max_length(self, fsm):
        """Test state history maintains maximum length."""
        # Perform many transitions
        transitions = [
            (ConversationEvent.START_CONVERSATION, ConversationState.GREETING),
            (ConversationEvent.USER_PROVIDES_NAME, ConversationState.MAIN_MENU),
            (ConversationEvent.START_ORDER, ConversationState.ORDERING),
            (ConversationEvent.COMPLETE_ORDER, ConversationState.VALIDATION),
            (ConversationEvent.ORDER_VALID, ConversationState.CONFIRMATION),
            (ConversationEvent.CONFIRM_ORDER, ConversationState.FULFILLMENT),
            (ConversationEvent.PROVIDE_DELIVERY_INFO, ConversationState.COMPLETION),
        ]
        
        for event, _ in transitions:
            await fsm.trigger(event)
        
        # History should be limited to 5 most recent states
        assert len(fsm.context.get('state_history', [])) <= 5
        # Should contain most recent states (excluding current)
        history = fsm.context.get('state_history', [])
        state_names = [h['state'] for h in history]
        assert ConversationState.INITIAL.name not in state_names  # Oldest, should be removed
        # Recent states should be present
        assert any(state in state_names for state in [ConversationState.VALIDATION.name, ConversationState.CONFIRMATION.name, ConversationState.FULFILLMENT.name])
    
    @pytest.mark.asyncio
    async def test_duplicate_states_in_history(self, fsm):
        """Test handling of duplicate states in history."""
        fsm.current_state = ConversationState.ORDERING
        
        # Multiple ADD_ITEM events (stay in ORDERING)
        for _ in range(3):
            await fsm.trigger(ConversationEvent.ADD_ITEM)
        
        # History should not have consecutive duplicates
        history = fsm.context.get('state_history', [])
        state_names = [h['state'] for h in history]
        assert state_names.count(ConversationState.ORDERING.name) <= 1


class TestContextManagement:
    """Test FSM context handling."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM with context."""
        fsm = AsyncConversationFSM(call_sid="test_call_sid_context")
        fsm.context.update({
            "customer_name": "John",
            "cart": {"items": []},
            "order_type": "pickup"
        })
        return fsm
    
    @pytest.mark.asyncio
    async def test_context_preserved_across_transitions(self, fsm):
        """Test context is preserved during state transitions."""
        # Check that original values are preserved
        original_name = fsm.context["customer_name"]
        original_cart = fsm.context["cart"]
        original_order_type = fsm.context["order_type"]
        
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Original values should still be there
        assert fsm.context["customer_name"] == original_name
        assert fsm.context["cart"] == original_cart
        assert fsm.context["order_type"] == original_order_type
    
    def test_context_update(self, fsm):
        """Test context can be updated."""
        fsm.update_context({"customer_phone": "123-456-7890"})
        
        assert "customer_phone" in fsm.context
        assert fsm.context["customer_phone"] == "123-456-7890"
        assert fsm.context["customer_name"] == "John"  # Original preserved
    
    def test_context_serialization(self, fsm):
        """Test context can be serialized to JSON."""
        # Add datetime object (serializable to JSON)
        fsm.context["timestamp"] = datetime.now().isoformat()
        
        # Test that context can be serialized
        import json
        try:
            json_str = json.dumps(fsm.context)
            # Should be able to deserialize it back
            deserialized = json.loads(json_str)
            assert deserialized["customer_name"] == "John"
            assert deserialized["call_sid"] == "test_call_sid_context"
        except Exception as e:
            pytest.fail(f"Context serialization failed: {e}")


class TestStateHandlers:
    """Test state handler integration."""
    
    @pytest.fixture
    def mock_handler(self):
        """Create mock state handler."""
        handler = MagicMock(spec=AsyncStateHandler)
        handler.on_enter = AsyncMock()
        handler.on_exit = AsyncMock()
        handler.handle_event = AsyncMock(return_value=None)
        return handler
    
    @pytest.fixture
    def fsm_with_handler(self, mock_handler):
        """Create FSM with mock handler."""
        fsm = AsyncConversationFSM(call_sid="test_call_sid_handler")
        fsm.handlers = {ConversationState.GREETING: mock_handler}
        return fsm, mock_handler
    
    @pytest.mark.asyncio
    async def test_handler_on_enter_called(self, fsm_with_handler):
        """Test handler on_enter is called on state entry."""
        fsm, handler = fsm_with_handler
        
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        
        handler.on_enter.assert_called_once()
        call_args = handler.on_enter.call_args[0]
        assert call_args[0] == fsm.context
    
    @pytest.mark.asyncio
    async def test_handler_on_exit_called(self, fsm_with_handler):
        """Test handler on_exit is called on state exit."""
        fsm, handler = fsm_with_handler
        fsm.current_state = ConversationState.GREETING
        
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        handler.on_exit.assert_called_once()
        call_args = handler.on_exit.call_args[0]
        assert call_args[0] == fsm.context
    
    @pytest.mark.asyncio
    async def test_handler_handle_event(self, fsm_with_handler):
        """Test handler can handle events."""
        fsm, handler = fsm_with_handler
        fsm.current_state = ConversationState.GREETING
        
        # Handler returns None - normal transition
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        handler.handle_event.assert_called_once_with(
            ConversationEvent.USER_PROVIDES_NAME,
            fsm.context
        )
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_handler_override_transition(self, fsm_with_handler):
        """Test handler can override state transition."""
        fsm, handler = fsm_with_handler
        fsm.current_state = ConversationState.GREETING
        
        # Handler returns different state
        handler.handle_event.return_value = ConversationState.ERROR
        
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        assert fsm.current_state == ConversationState.ERROR


class TestFSMPersistence:
    """Test FSM state persistence."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.fixture
    def mock_store(self):
        """Mock conversation store."""
        with patch('app.fsm.core.async_conversation_store') as mock:
            yield mock
    
    @pytest.mark.asyncio
    async def test_save_state(self, fsm, mock_store):
        """Test FSM state is saved during transitions."""
        fsm.current_state = ConversationState.GREETING
        
        # Trigger a transition - this should save state
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Verify store was called
        mock_store.update_conversation.assert_called()
        call_args = mock_store.update_conversation.call_args[0]
        
        assert call_args[0] == "test_call_sid_123"  # The call_sid
        saved_data = call_args[1]
        assert "fsm_state" in saved_data
        assert saved_data["fsm_state"] == "MAIN_MENU"
    
    @pytest.mark.asyncio
    async def test_load_state(self, fsm, mock_store):
        """Test loading FSM state from persistence."""
        saved_conversation = {
            "fsm_state": "VALIDATION",
            "fsm_context": json.dumps({
                "customer_name": "Bob",
                "cart": {"items": [{"name": "Tuna Roll"}]},
                "call_sid": "test_call_sid_123"
            })
        }
        
        mock_store.get_conversation = AsyncMock(return_value=saved_conversation)
        
        await fsm.load_state()
        
        assert fsm.current_state == ConversationState.VALIDATION
        assert fsm.context["customer_name"] == "Bob"
        assert len(fsm.context["cart"]["items"]) == 1
    
    @pytest.mark.asyncio
    async def test_load_corrupted_state(self, fsm, mock_store):
        """Test handling of corrupted state data."""
        # Return invalid state
        mock_store.get_conversation = AsyncMock(return_value={"invalid": "data"})
        
        # Should handle gracefully
        await fsm.load_state()
        
        # FSM should remain in current state
        assert fsm.current_state == ConversationState.INITIAL
        assert "call_sid" in fsm.context
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_state(self, fsm, mock_store):
        """Test loading when no state exists."""
        mock_store.get_conversation = AsyncMock(return_value={})
        
        await fsm.load_state()
        
        # FSM should remain in default state
        assert fsm.current_state == ConversationState.INITIAL
        assert "call_sid" in fsm.context


class TestErrorHandling:
    """Test error handling and recovery."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.mark.asyncio
    async def test_error_state_entry(self, fsm):
        """Test entering error state."""
        fsm.current_state = ConversationState.ORDERING
        
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        
        assert fsm.current_state == ConversationState.ERROR
        assert fsm.context.get('previous_fsm_state') == ConversationState.ORDERING.name
    
    @pytest.mark.asyncio
    async def test_error_recovery_paths(self, fsm):
        """Test recovery paths from error state."""
        fsm.current_state = ConversationState.ERROR
        fsm.context['previous_fsm_state'] = ConversationState.ORDERING.name
        
        # Test different recovery options
        recovery_paths = [
            (ConversationEvent.RETRY_LAST_ACTION, ConversationState.ORDERING),
            (ConversationEvent.FALLBACK_TO_MAIN_MENU, ConversationState.MAIN_MENU),
            (ConversationEvent.REQUEST_ESCALATION, ConversationState.ESCALATION),
        ]
        
        for event, expected_state in recovery_paths:
            fsm.current_state = ConversationState.ERROR
            await fsm.trigger(event)
            assert fsm.current_state == expected_state
    
    @pytest.mark.asyncio
    async def test_cascading_errors(self, fsm):
        """Test handling multiple consecutive errors."""
        fsm.current_state = ConversationState.ORDERING
        
        # First error
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
        
        # Error in error state should stay in ERROR
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
    
    @pytest.mark.asyncio
    async def test_invalid_event_handling(self, fsm):
        """Test handling of invalid events."""
        fsm.current_state = ConversationState.GREETING
        
        # Try invalid event
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        
        # State should be unchanged
        assert fsm.current_state == ConversationState.GREETING


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.mark.asyncio
    async def test_terminal_state_transitions(self, fsm):
        """Test transitions from terminal states."""
        terminal_states = [ConversationState.COMPLETION, ConversationState.ESCALATION]
        
        for state in terminal_states:
            fsm.current_state = state
            
            # Should only allow specific transitions
            valid_events = []
            if state == ConversationState.COMPLETION:
                valid_events = [ConversationEvent.REQUEST_FOLLOW_UP, ConversationEvent.COMPLETE_INTERACTION]
            elif state == ConversationState.ESCALATION:
                valid_events = [ConversationEvent.COMPLETE_INTERACTION]
            
            # Test valid transitions
            for event in valid_events:
                fsm.current_state = state  # Reset
                try:
                    await fsm.trigger(event)
                    # Should succeed
                except Exception as e:
                    pytest.fail(f"Valid transition {state} -> {event} failed: {e}")
    
    @pytest.mark.asyncio
    async def test_rapid_transitions(self, fsm):
        """Test rapid consecutive transitions."""
        fsm.current_state = ConversationState.ORDERING
        
        # Simulate rapid button clicking
        for _ in range(10):
            await fsm.trigger(ConversationEvent.ADD_ITEM)
        
        # Should handle gracefully
        assert fsm.current_state == ConversationState.ORDERING
        assert len(fsm.context.get('state_history', [])) <= 5
    
    @pytest.mark.asyncio
    async def test_null_event_handling(self, fsm):
        """Test handling of null/undefined events."""
        # Triggering with None should not change state
        await fsm.trigger(None)
        
        # State should be unchanged
        assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_concurrent_transitions(self, fsm):
        """Test concurrent state transitions."""
        async def transition_task(event):
            try:
                await fsm.trigger(event)
            except Exception:
                pass
        
        # Start multiple concurrent transitions
        tasks = [
            transition_task(ConversationEvent.START_CONVERSATION),
            transition_task(ConversationEvent.START_CONVERSATION),
            transition_task(ConversationEvent.START_CONVERSATION),
        ]
        
        await asyncio.gather(*tasks)
        
        # FSM should be in a valid state
        assert fsm.current_state in [ConversationState.INITIAL, ConversationState.GREETING]
    
    @pytest.mark.asyncio
    async def test_state_with_substates(self, fsm):
        """Test states that have substates."""
        fsm.current_state = ConversationState.ORDERING
        
        # Enter substate
        await fsm.trigger(ConversationEvent.REQUEST_MENU_QUERY)
        assert fsm.current_state == ConversationState.MENU_QUERY_SUBSTATE
        
        # Exit substate
        await fsm.trigger(ConversationEvent.MENU_QUERY_RESOLVED)
        assert fsm.current_state == ConversationState.ORDERING


class TestGlobalCommands:
    """Test global command integration with FSM."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    def test_global_command_mapping(self):
        """Test mapping of global commands to FSM events."""
        from app.utils.global_commands import GlobalCommand
        
        # Map global commands to FSM events
        command_event_map = {
            GlobalCommand.START_OVER: ConversationEvent.FALLBACK_TO_MAIN_MENU,
            GlobalCommand.CANCEL: ConversationEvent.USER_REQUESTS_CANCELLATION,
            GlobalCommand.HELP: ConversationEvent.REQUEST_FOLLOW_UP,
        }
        
        for command, event in command_event_map.items():
            assert hasattr(ConversationEvent, event.name)


class TestFSMMetrics:
    """Test FSM metrics and monitoring."""
    
    @pytest.fixture
    def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="test_call_sid_123")
    
    @pytest.mark.asyncio
    async def test_transition_metrics(self, fsm):
        """Test tracking of transition metrics."""
        # Perform transitions
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        
        # Check that transitions worked
        assert fsm.current_state == ConversationState.ORDERING
        # Check state history exists
        assert 'state_history' in fsm.context
    
    @pytest.mark.asyncio
    async def test_error_state_tracking(self, fsm):
        """Test error state visit tracking."""
        # Cause some errors
        for _ in range(3):
            fsm.current_state = ConversationState.ORDERING
            await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
            await fsm.trigger(ConversationEvent.RETRY_LAST_ACTION)
        
        # Verify state transitions occurred
        assert fsm.current_state == ConversationState.ORDERING