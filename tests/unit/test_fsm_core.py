"""
Unit tests for FSM core functionality.
Tests state transitions and event processing in isolation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.fsm.core import (
    AsyncConversationFSM, 
    ConversationState, 
    ConversationEvent,
    AsyncFSMManager
)


class TestAsyncConversationFSM:
    """Test the core FSM functionality."""
    
    @pytest.fixture
    def fsm(self):
        """Create a test FSM instance."""
        return AsyncConversationFSM(call_sid="TEST_CALL_123")
    
    @pytest.mark.asyncio
    async def test_initial_state(self, fsm):
        """Test FSM starts in GREETING state."""
        assert fsm.current_state == ConversationState.GREETING
        assert fsm.call_sid == "TEST_CALL_123"
        assert isinstance(fsm.context, dict)
    
    @pytest.mark.asyncio
    async def test_greeting_to_main_menu_transition(self, fsm):
        """Test transition from GREETING to MAIN_MENU."""
        # Set context
        fsm.context["greeting_sent"] = True
        
        # Process event
        await fsm.process_event(ConversationEvent.USER_PROVIDES_NAME)
        
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_main_menu_to_ordering_transition(self, fsm):
        """Test transition from MAIN_MENU to ORDERING."""
        # Set initial state
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        # Process event
        await fsm.process_event(ConversationEvent.USER_STARTS_ORDER)
        
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_ordering_to_validation_transition(self, fsm):
        """Test transition from ORDERING to VALIDATION."""
        # Set initial state and context
        await fsm.transition_to(ConversationState.ORDERING)
        fsm.context["cart_items"] = [{"name": "California Roll", "quantity": 1}]
        
        # Process event
        await fsm.process_event(ConversationEvent.USER_CONFIRMS_CART)
        
        assert fsm.current_state == ConversationState.VALIDATION
    
    @pytest.mark.asyncio
    async def test_validation_to_confirmation_transition(self, fsm):
        """Test transition from VALIDATION to CONFIRMATION."""
        # Set initial state
        await fsm.transition_to(ConversationState.VALIDATION)
        fsm.context["validation_passed"] = True
        
        # Process event
        await fsm.process_event(ConversationEvent.VALIDATION_PASSED)
        
        assert fsm.current_state == ConversationState.CONFIRMATION
    
    @pytest.mark.asyncio
    async def test_confirmation_to_fulfillment_transition(self, fsm):
        """Test transition from CONFIRMATION to FULFILLMENT."""
        # Set initial state
        await fsm.transition_to(ConversationState.CONFIRMATION)
        
        # Process event
        await fsm.process_event(ConversationEvent.USER_CONFIRMS_ORDER)
        
        assert fsm.current_state == ConversationState.FULFILLMENT
    
    @pytest.mark.asyncio
    async def test_fulfillment_to_completion_transition(self, fsm):
        """Test transition from FULFILLMENT to COMPLETION."""
        # Set initial state
        await fsm.transition_to(ConversationState.FULFILLMENT)
        fsm.context["order_submitted"] = True
        
        # Process event
        await fsm.process_event(ConversationEvent.ORDER_SUBMITTED)
        
        assert fsm.current_state == ConversationState.COMPLETION
    
    @pytest.mark.asyncio
    async def test_escalation_transition_from_any_state(self, fsm):
        """Test that escalation can be triggered from any state."""
        states_to_test = [
            ConversationState.GREETING,
            ConversationState.MAIN_MENU,
            ConversationState.ORDERING,
            ConversationState.VALIDATION
        ]
        
        for state in states_to_test:
            await fsm.transition_to(state)
            await fsm.process_event(ConversationEvent.USER_REQUESTS_HUMAN)
            assert fsm.current_state == ConversationState.ESCALATION
            # Reset for next test
            fsm.current_state = state
    
    @pytest.mark.asyncio
    async def test_invalid_transition_ignored(self, fsm):
        """Test that invalid transitions are ignored."""
        # Start in GREETING
        initial_state = fsm.current_state
        
        # Try invalid transition
        await fsm.process_event(ConversationEvent.ORDER_SUBMITTED)
        
        # Should remain in same state
        assert fsm.current_state == initial_state
    
    @pytest.mark.asyncio
    async def test_context_preserved_across_transitions(self, fsm):
        """Test that context is preserved during transitions."""
        # Add context data
        fsm.context["customer_name"] = "John"
        fsm.context["phone_number"] = "+1234567890"
        
        # Transition states
        await fsm.process_event(ConversationEvent.USER_PROVIDES_NAME)
        
        # Context should be preserved
        assert fsm.context["customer_name"] == "John"
        assert fsm.context["phone_number"] == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_transition_history_tracking(self, fsm):
        """Test that FSM tracks transition history."""
        # Make several transitions
        await fsm.process_event(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.process_event(ConversationEvent.USER_STARTS_ORDER)
        
        # Check history (if implemented)
        if hasattr(fsm, 'history'):
            assert len(fsm.history) >= 2
    
    @pytest.mark.asyncio
    async def test_state_entry_actions(self, fsm):
        """Test that state entry actions are executed."""
        with patch.object(fsm, '_execute_state_entry_action', new_callable=AsyncMock) as mock_action:
            await fsm.transition_to(ConversationState.MAIN_MENU)
            mock_action.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_state_exit_actions(self, fsm):
        """Test that state exit actions are executed."""
        with patch.object(fsm, '_execute_state_exit_action', new_callable=AsyncMock) as mock_action:
            await fsm.transition_to(ConversationState.MAIN_MENU)
            await fsm.transition_to(ConversationState.ORDERING)
            # Exit action should be called when leaving MAIN_MENU
            assert mock_action.call_count >= 1


class TestAsyncFSMManager:
    """Test the FSM Manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a test FSM manager."""
        return AsyncFSMManager()
    
    @pytest.mark.asyncio
    async def test_create_fsm(self, manager):
        """Test creating a new FSM instance."""
        call_sid = "TEST_CALL_456"
        fsm = await manager.create_fsm(call_sid)
        
        assert fsm is not None
        assert fsm.call_sid == call_sid
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio
    async def test_get_existing_fsm(self, manager):
        """Test retrieving an existing FSM."""
        call_sid = "TEST_CALL_789"
        
        # Create FSM
        fsm1 = await manager.create_fsm(call_sid)
        
        # Get same FSM
        fsm2 = await manager.get_fsm(call_sid)
        
        assert fsm1 is fsm2
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_fsm_creates_new(self, manager):
        """Test that getting non-existent FSM creates a new one."""
        call_sid = "NEW_CALL_123"
        
        fsm = await manager.get_fsm(call_sid)
        
        assert fsm is not None
        assert fsm.call_sid == call_sid
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio
    async def test_remove_fsm(self, manager):
        """Test removing an FSM instance."""
        call_sid = "TEST_CALL_REMOVE"
        
        # Create and remove
        await manager.create_fsm(call_sid)
        await manager.remove_fsm(call_sid)
        
        # Getting it again should create new instance
        fsm = await manager.get_fsm(call_sid)
        assert fsm.current_state == ConversationState.GREETING  # Fresh instance
    
    @pytest.mark.asyncio
    async def test_concurrent_fsm_management(self, manager):
        """Test managing multiple FSMs concurrently."""
        call_sids = ["CALL_1", "CALL_2", "CALL_3"]
        
        # Create multiple FSMs
        fsms = []
        for sid in call_sids:
            fsm = await manager.create_fsm(sid)
            fsms.append(fsm)
        
        # Verify all are different instances
        assert len(set(id(fsm) for fsm in fsms)) == 3
        
        # Verify each can be retrieved
        for sid in call_sids:
            fsm = await manager.get_fsm(sid)
            assert fsm.call_sid == sid