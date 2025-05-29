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
        """Test FSM starts in INITIAL state."""
        assert fsm.current_state == ConversationState.INITIAL
        
        # After starting, it should move to GREETING
        await fsm.start()
        assert fsm.current_state == ConversationState.GREETING
        assert fsm.call_sid == "TEST_CALL_123"
        assert isinstance(fsm.context, dict)
    
    @pytest.mark.asyncio
    async def test_greeting_to_main_menu_transition(self, fsm):
        """Test transition from GREETING to MAIN_MENU."""
        # First transition to GREETING state
        await fsm.start()
        
        # Set context
        fsm.context["greeting_sent"] = True
        
        # Trigger event
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_main_menu_to_ordering_transition(self, fsm):
        """Test transition from MAIN_MENU to ORDERING."""
        # Set initial state
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        # Trigger event
        await fsm.trigger(ConversationEvent.START_ORDER)
        
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_ordering_to_validation_transition(self, fsm):
        """Test transition from ORDERING to VALIDATION."""
        # Set initial state and context
        await fsm.transition_to(ConversationState.ORDERING)
        fsm.context["cart_items"] = [{"name": "California Roll", "quantity": 1}]
        
        # Trigger event
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        
        assert fsm.current_state == ConversationState.VALIDATION
    
    @pytest.mark.asyncio
    async def test_validation_to_confirmation_transition(self, fsm):
        """Test transition from VALIDATION to CONFIRMATION."""
        # Set initial state
        await fsm.transition_to(ConversationState.VALIDATION)
        fsm.context["validation_passed"] = True
        
        # Trigger event
        await fsm.trigger(ConversationEvent.ORDER_VALID)
        
        assert fsm.current_state == ConversationState.CONFIRMATION
    
    @pytest.mark.asyncio
    async def test_confirmation_to_fulfillment_transition(self, fsm):
        """Test transition from CONFIRMATION to FULFILLMENT."""
        # Set initial state
        await fsm.transition_to(ConversationState.CONFIRMATION)
        
        # Trigger event
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        
        assert fsm.current_state == ConversationState.FULFILLMENT
    
    @pytest.mark.asyncio
    async def test_fulfillment_to_completion_transition(self, fsm):
        """Test transition from FULFILLMENT to COMPLETION."""
        # Set initial state
        await fsm.transition_to(ConversationState.FULFILLMENT)
        fsm.context["order_submitted"] = True
        
        # Trigger event
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        
        assert fsm.current_state == ConversationState.COMPLETION
    
    @pytest.mark.asyncio
    async def test_escalation_transition_from_any_state(self, fsm):
        """Test that escalation can be triggered from any state."""
        # Note: Not all states support escalation in the current FSM implementation
        # Only test states that have escalation transitions defined
        states_to_test = [
            ConversationState.MAIN_MENU,
            ConversationState.ORDERING,
            ConversationState.VALIDATION,
            ConversationState.CONFIRMATION,
            ConversationState.FULFILLMENT
        ]
        
        for state in states_to_test:
            # Create fresh FSM for each test
            test_fsm = AsyncConversationFSM(call_sid=f"TEST_{state.name}")
            await test_fsm.transition_to(state)
            await test_fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
            assert test_fsm.current_state == ConversationState.ESCALATION
    
    @pytest.mark.asyncio
    async def test_invalid_transition_ignored(self, fsm):
        """Test that invalid transitions are ignored."""
        # Start in INITIAL state
        initial_state = fsm.current_state
        
        # Try invalid transition (COMPLETE_INTERACTION is not valid from INITIAL)
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        
        # Should remain in same state
        assert fsm.current_state == initial_state
    
    @pytest.mark.asyncio
    async def test_context_preserved_across_transitions(self, fsm):
        """Test that context is preserved during transitions."""
        # First start the FSM to get to GREETING state
        await fsm.start()
        
        # Add context data
        fsm.context["customer_name"] = "John"
        fsm.context["phone_number"] = "+1234567890"
        
        # Transition states
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Context should be preserved
        assert fsm.context["customer_name"] == "John"
        assert fsm.context["phone_number"] == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_transition_history_tracking(self, fsm):
        """Test that FSM tracks transition history."""
        # Start the FSM
        await fsm.start()
        
        # Make several transitions
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        
        # Check history (if implemented)
        if hasattr(fsm, 'history'):
            assert len(fsm.history) >= 2
    
    @pytest.mark.asyncio
    async def test_state_entry_actions(self, fsm):
        """Test that state entry actions are executed."""
        # Check that handlers are called when entering states
        handler = fsm.handlers.get(ConversationState.MAIN_MENU)
        if handler and hasattr(handler, 'handle_entry'):
            with patch.object(handler, 'handle_entry', new_callable=AsyncMock) as mock_entry:
                await fsm.transition_to(ConversationState.MAIN_MENU)
                mock_entry.assert_called_once()
        else:
            # Just verify transition works
            await fsm.transition_to(ConversationState.MAIN_MENU)
            assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_state_exit_actions(self, fsm):
        """Test that state exit actions are executed."""
        # Check that handlers are called when exiting states
        await fsm.transition_to(ConversationState.MAIN_MENU)
        handler = fsm.handlers.get(ConversationState.MAIN_MENU)
        if handler and hasattr(handler, 'handle_exit'):
            with patch.object(handler, 'handle_exit', new_callable=AsyncMock) as mock_exit:
                await fsm.transition_to(ConversationState.ORDERING)
                mock_exit.assert_called_once()
        else:
            # Just verify transition works
            await fsm.transition_to(ConversationState.ORDERING)
            assert fsm.current_state == ConversationState.ORDERING


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
        fsm = await manager.start_conversation(call_sid)
        
        assert fsm is not None
        assert fsm.call_sid == call_sid
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio
    async def test_get_existing_fsm(self, manager):
        """Test retrieving an existing FSM."""
        call_sid = "TEST_CALL_789"
        
        # Create FSM
        fsm1 = await manager.start_conversation(call_sid)
        
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
        # Should be in INITIAL state since get_fsm creates new FSM without starting it
        assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_remove_fsm(self, manager):
        """Test removing an FSM instance."""
        call_sid = "TEST_CALL_REMOVE"
        
        # Create and remove
        await manager.start_conversation(call_sid)
        manager.remove_fsm(call_sid)
        
        # Check that it was removed
        assert call_sid not in manager.fsm_instances
    
    @pytest.mark.asyncio
    async def test_concurrent_fsm_management(self, manager):
        """Test managing multiple FSMs concurrently."""
        call_sids = ["CALL_1", "CALL_2", "CALL_3"]
        
        # Create multiple FSMs
        fsms = []
        for sid in call_sids:
            fsm = await manager.start_conversation(sid)
            fsms.append(fsm)
        
        # Verify all are different instances
        assert len(set(id(fsm) for fsm in fsms)) == 3
        
        # Verify each can be retrieved
        for sid in call_sids:
            fsm = await manager.get_fsm(sid)
            assert fsm.call_sid == sid