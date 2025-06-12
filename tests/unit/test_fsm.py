"""
Unit tests for Finite State Machine (FSM).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from typing import Dict, Any, List, Optional

from app.fsm.core import AsyncConversationFSM
from app.fsm.handlers import GreetingHandler, OrderingHandler


@pytest.fixture
def fsm():
    """Create a basic FSM instance for testing."""
    return AsyncConversationFSM(call_sid="test_session_123")

@pytest.fixture
def mock_conversation_store():
    """Mock the conversation store."""
    with patch('app.fsm.core.async_conversation_store') as mock_store:
        mock_store.get_conversation.return_value = asyncio.coroutine(lambda: {})()
        mock_store.save_conversation.return_value = asyncio.coroutine(lambda: None)()
        yield mock_store

# Removed duplicate fsm fixture
# Removed duplicate mock_conversation_store fixture

This module contains comprehensive tests for the FSM core functionality,
state transitions, event handling, persistence, and handlers.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.fsm.core import (
    ConversationState, 
    ConversationEvent, 
    # FSMError, # Removed as FSMError class no longer exists
    AsyncConversationFSM,
    AsyncStateHandler
)
from app.utils.fsm_async import AsyncFSMManager


class TestFSMCore:
    """Test FSM core functionality - Task 2.2.1: State transitions and event handling."""
    
    def test_fsm_initialization(self):
        """Test FSM initialization with correct defaults."""
        fsm = AsyncConversationFSM(call_sid="test_123")
        
        assert fsm.call_sid == "test_123"
        assert fsm.current_state == ConversationState.INITIAL
        assert fsm.context["call_sid"] == "test_123"
        assert len(fsm.handlers) == 11  # All states should have handlers
        assert len(fsm.transitions) == 11  # All states with transitions
    
    @pytest.mark.asyncio
    async def test_fsm_start(self, fsm):
        """Test FSM start transitions to GREETING state."""
        assert fsm.current_state == ConversationState.INITIAL
        
        await fsm.start()
        
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio
    async def test_valid_state_transitions(self, fsm):
        """Test all valid state transitions work correctly."""
        # Start conversation
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
        
        # Greeting -> Main Menu
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        assert fsm.current_state == ConversationState.MAIN_MENU
        
        # Main Menu -> Ordering
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
        
        # Ordering -> Validation
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        assert fsm.current_state == ConversationState.VALIDATION
        
        # Validation -> Confirmation
        await fsm.trigger(ConversationEvent.ORDER_VALID)
        assert fsm.current_state == ConversationState.CONFIRMATION
        
        # Confirmation -> Fulfillment
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        assert fsm.current_state == ConversationState.FULFILLMENT
        
        # Fulfillment -> Completion
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        assert fsm.current_state == ConversationState.COMPLETION
    
    @pytest.mark.asyncio
    async def test_invalid_event_for_state(self, fsm):
        """Test that invalid events for current state are ignored."""
        # Start in INITIAL state
        assert fsm.current_state == ConversationState.INITIAL
        
        # Try invalid event for INITIAL state
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        
        # Should remain in INITIAL state
        assert fsm.current_state == ConversationState.INITIAL
        
        # Move to GREETING
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
        
        # Try invalid event for GREETING
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        
        # Should remain in GREETING
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio
    async def test_event_handling_with_handlers(self, fsm):
        """Test that state handlers are called during transitions."""
        # Mock handlers
        mock_greeting_handler = Mock(spec=['on_enter', 'on_exit'])
        mock_greeting_handler.on_enter = AsyncMock()
        mock_greeting_handler.on_exit = AsyncMock()
        
        mock_menu_handler = Mock(spec=['on_enter', 'on_exit'])
        mock_menu_handler.on_enter = AsyncMock()
        mock_menu_handler.on_exit = AsyncMock()
        
        fsm.handlers[ConversationState.GREETING] = mock_greeting_handler
        fsm.handlers[ConversationState.MAIN_MENU] = mock_menu_handler
        
        # Trigger transition INITIAL -> GREETING
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        
        # Verify greeting handler's on_enter was called
        mock_greeting_handler.on_enter.assert_called_once()
        
        # Trigger transition GREETING -> MAIN_MENU
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Verify handlers were called
        mock_greeting_handler.on_exit.assert_called_once()
        mock_menu_handler.on_enter.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_state_transitions(self, fsm):
        """Test transitions to ERROR state from various states."""
        # Start conversation and move to MAIN_MENU
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        assert fsm.current_state == ConversationState.MAIN_MENU
        
        # Trigger error
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
        
        # Can recover from error to ordering
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
        
        # Error from ordering
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
    
    @pytest.mark.asyncio
    async def test_escalation_transitions(self, fsm):
        """Test REQUEST_ESCALATION event from various states."""
        # Test escalation from MAIN_MENU
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
        assert fsm.current_state == ConversationState.ESCALATION
        
        # Reset and test from ORDERING
        fsm.current_state = ConversationState.ORDERING
        await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
        assert fsm.current_state == ConversationState.ESCALATION
        
        # Reset and test from CONFIRMATION
        fsm.current_state = ConversationState.CONFIRMATION
        await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
        assert fsm.current_state == ConversationState.ESCALATION
    
    @pytest.mark.asyncio
    async def test_context_preservation_during_transitions(self, fsm):
        """Test that context is preserved during state transitions."""
        # Add context data
        fsm.context.update({
            "customer_name": "John Doe",
            "order_type": "delivery",
            "items": ["sushi", "miso soup"]
        })
        
        # Perform transitions
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        
        # Verify context is preserved
        assert fsm.context["customer_name"] == "John Doe"
        assert fsm.context["order_type"] == "delivery"
        assert fsm.context["items"] == ["sushi", "miso soup"]
        assert fsm.context["call_sid"] == "test_session_123"


class TestFSMInvalidTransitionPrevention:
    """Test invalid transition prevention - Task 2.2.2."""
    
    @pytest.mark.asyncio
    async def test_invalid_transitions_from_initial(self, fsm):
        """Test that only START_CONVERSATION is valid from INITIAL."""
        assert fsm.current_state == ConversationState.INITIAL
        
        # These should all be ignored (no state change)
        invalid_events = [
            ConversationEvent.USER_PROVIDES_NAME,
            ConversationEvent.COMPLETE_ORDER,
            ConversationEvent.CONFIRM_ORDER,
            ConversationEvent.ORDER_VALID
        ]
        
        for event in invalid_events:
            await fsm.trigger(event)
            assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_cannot_skip_states(self, fsm):
        """Test that we cannot skip intermediate states."""
        # Start conversation
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
        
        # Cannot go directly to FULFILLMENT
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        assert fsm.current_state == ConversationState.GREETING  # No change
        
        # Cannot go to VALIDATION
        await fsm.trigger(ConversationEvent.ORDER_VALID)
        assert fsm.current_state == ConversationState.GREETING  # No change
    
    @pytest.mark.asyncio
    async def test_terminal_state_restrictions(self, fsm):
        """Test restrictions on terminal states."""
        # Move to ESCALATION
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
        assert fsm.current_state == ConversationState.ESCALATION
        
        # ESCALATION only allows ERROR_OCCURRED
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ESCALATION  # No change
        
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        assert fsm.current_state == ConversationState.ESCALATION  # No change
    
    @pytest.mark.asyncio
    async def test_validation_state_binary_outcomes(self, fsm):
        """Test VALIDATION state only allows ORDER_VALID or ORDER_INVALID."""
        # Navigate to VALIDATION
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        assert fsm.current_state == ConversationState.VALIDATION
        
        # These events should be ignored
        invalid_events = [
            ConversationEvent.START_CONVERSATION,
            ConversationEvent.USER_PROVIDES_NAME,
            ConversationEvent.CONFIRM_ORDER,
            ConversationEvent.COMPLETE_INTERACTION
        ]
        
        for event in invalid_events:
            await fsm.trigger(event)
            assert fsm.current_state == ConversationState.VALIDATION
    
    @pytest.mark.asyncio
    async def test_boundary_conditions(self, fsm):
        """Test FSM behavior at boundary conditions."""
        # Test None event
        await fsm.trigger(None)
        assert fsm.current_state == ConversationState.INITIAL
        
        # Test with invalid event type (if not caught by type system)
        try:
            await fsm.trigger("INVALID_EVENT")
        except (AttributeError, TypeError):
            pass
        assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_completion_state_limited_options(self, fsm):
        """Test COMPLETION state has limited transition options."""
        # Navigate to COMPLETION
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsm.trigger(ConversationEvent.START_ORDER)
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        await fsm.trigger(ConversationEvent.ORDER_VALID)
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        assert fsm.current_state == ConversationState.COMPLETION
        
        # Only REQUEST_FOLLOW_UP and ERROR_OCCURRED are valid
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.COMPLETION  # No change
        
        await fsm.trigger(ConversationEvent.REQUEST_FOLLOW_UP)
        assert fsm.current_state == ConversationState.FOLLOW_UP  # Valid transition


class TestFSMPersistenceAndRecovery:
    """Test FSM persistence and recovery - Task 2.2.3."""
    
    @pytest.fixture
    async def fsm(self):
        """Create FSM instance."""
        return AsyncConversationFSM(call_sid="persist_123")
    
    @pytest.mark.asyncio
    async def test_state_saving_after_transitions(self, fsm, mock_conversation_store):
        """Test that state is saved after each transition."""
        # Mock the _save_state method
        with patch.object(fsm, '_save_state', new=AsyncMock()) as mock_save:
            # Perform transitions
            await fsm.trigger(ConversationEvent.START_CONVERSATION)
            await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
            await fsm.trigger(ConversationEvent.START_ORDER)
            
            # Verify save was called after each transition
            assert mock_save.call_count == 3
    
    @pytest.mark.asyncio
    async def test_context_serialization(self, fsm):
        """Test that context is properly serialized for storage."""
        # Add various data types to context
        fsm.context.update({
            "string": "value",
            "number": 123,
            "float": 45.67,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "data"},
            "agent": Mock()  # Non-serializable
        })
        
        # Get serializable context
        with patch('app.fsm.core.async_conversation_store') as mock_store:
            mock_store.update_conversation = AsyncMock()
            
            # This should trigger serialization
            await fsm._save_state()
            
            # Get the saved data
            saved_args = mock_store.update_conversation.call_args[0]
            assert saved_args[0] == "persist_123"  # call_sid
            
            saved_data = mock_store.update_conversation.call_args[0][1]
            assert "fsm_state" in saved_data
            assert "fsm_context" in saved_data
            
            # Parse the serialized context
            import json
            context_data = json.loads(saved_data["fsm_context"])
            
            # Verify serializable data is preserved
            assert context_data["string"] == "value"
            assert context_data["number"] == 123
            
            # Non-serializable objects should be excluded
            assert "agent" not in context_data
    
    @pytest.mark.asyncio
    async def test_state_loading_from_store(self, mock_conversation_store):
        """Test loading FSM state from conversation store."""
        # Setup mock data
        context_data = {
            "customer_name": "John Doe",
            "order_type": "delivery",
            "cart": {"items": ["sushi", "tempura"]}
        }
        stored_data = {
            "fsm_state": "ORDERING",
            "fsm_context": json.dumps(context_data)
        }
        mock_conversation_store.get_conversation.return_value = stored_data
        
        # Create FSM and load state
        fsm = AsyncConversationFSM(call_sid="load_123")
        await fsm.load_state()
        
        # Verify state was loaded
        assert fsm.current_state == ConversationState.ORDERING
        assert fsm.context["customer_name"] == "John Doe"
        assert fsm.context["order_type"] == "delivery"
        assert fsm.context["cart"]["items"] == ["sushi", "tempura"]
    
    @pytest.mark.asyncio
    async def test_recovery_after_service_restart(self, mock_conversation_store):
        """Test FSM recovery after service restart."""
        # Simulate existing conversation in storage
        context_data = {
            "call_sid": "restart_123",
            "customer_name": "Jane Smith",
            "order_total": 45.99,
            "items": [{"name": "California Roll", "quantity": 2}]
        }
        stored_data = {
            "fsm_state": "CONFIRMATION",
            "fsm_context": json.dumps(context_data)
        }
        mock_conversation_store.get_conversation.return_value = stored_data
        
        # Create new FSM instance (simulating restart)
        fsm = AsyncConversationFSM(call_sid="restart_123")
        await fsm.load_state()
        
        # Verify recovery
        assert fsm.current_state == ConversationState.CONFIRMATION
        assert fsm.context["customer_name"] == "Jane Smith"
        assert fsm.context["order_total"] == 45.99
        
        # Should be able to continue from recovered state
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        assert fsm.current_state == ConversationState.FULFILLMENT
    
    @pytest.mark.asyncio
    async def test_handling_corrupted_state_data(self, mock_conversation_store):
        """Test handling of corrupted or invalid state data."""
        # Test with invalid state name
        mock_conversation_store.get_conversation.return_value = {
            "state": "INVALID_STATE",
            "data": "corrupted"
        }
        
        fsm = AsyncConversationFSM(call_sid="corrupt_123")
        
        # Should handle gracefully
        try:
            await fsm.load_state()
        except Exception:
            pass
        
        # Should remain in INITIAL state
        assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    async def test_concurrent_state_operations(self, fsm, mock_conversation_store):
        """Test handling of concurrent state operations."""
        # Simulate concurrent transitions
        async def transition_1():
            await fsm.trigger(ConversationEvent.START_CONVERSATION)
            await asyncio.sleep(0.01)
            await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        async def transition_2():
            await asyncio.sleep(0.005)  # Start slightly after
            await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        
        # Run concurrently
        await asyncio.gather(
            transition_1(),
            transition_2(),
            return_exceptions=True
        )
        
        # FSM should be in a valid state
        assert fsm.current_state in [
            ConversationState.MAIN_MENU,
            ConversationState.ERROR
        ]
    
    @pytest.mark.asyncio
    async def test_state_persistence_with_large_context(self, fsm, mock_conversation_store):
        """Test persistence with large context data."""
        # Add large context
        large_list = ["item_" + str(i) for i in range(1000)]
        fsm.context["large_data"] = large_list
        fsm.context["nested"] = {
            "level1": {
                "level2": {
                    "level3": {"data": "deep"}
                }
            }
        }
        
        # Save state
        await fsm._save_state()
        
        # Verify save was called
        mock_conversation_store.update_conversation.assert_called_once()
        
        # Verify data integrity
        saved_data = mock_conversation_store.update_conversation.call_args[0][1]
        context_data = json.loads(saved_data["fsm_context"])
        assert len(context_data["large_data"]) == 1000
        assert context_data["nested"]["level1"]["level2"]["level3"]["data"] == "deep"


class TestFSMHandlers:
    """Test FSM state handlers - Task 2.2.4."""
    
    @pytest.mark.asyncio
    async def test_state_handler_lifecycle(self):
        """Test handler on_enter and on_exit lifecycle methods."""
        handler = AsyncStateHandler(ConversationState.GREETING)
        
        # Mock the methods to track calls
        handler.on_enter = AsyncMock()
        handler.on_exit = AsyncMock()
        
        context = {"test": "data"}
        
        # Test on_enter
        await handler.on_enter(context)
        handler.on_enter.assert_called_once_with(context)
        
        # Test on_exit
        await handler.on_exit(context)
        handler.on_exit.assert_called_once_with(context)
    
    @pytest.mark.asyncio
    async def test_handler_event_processing(self):
        """Test handler event processing returns next state."""
        handler = AsyncStateHandler(ConversationState.GREETING)
        
        # Test default implementation returns None
        result = await handler.handle_event(
            ConversationEvent.USER_PROVIDES_NAME,
            {"context": "data"}
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_greeting_handler_integration(self):
        """Test greeting handler with FSM integration."""
        fsm = AsyncConversationFSM(call_sid="handler_test")
        
        # Ensure we have greeting handler
        assert ConversationState.GREETING in fsm.handlers
        handler = fsm.handlers[ConversationState.GREETING]
        assert handler is not None
        
        # Test transition to greeting
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
    
    @pytest.mark.asyncio 
    async def test_error_handler_recovery(self):
        """Test error handler allows recovery."""
        fsm = AsyncConversationFSM(call_sid="error_test")
        
        # Navigate to ERROR state
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
        
        # Should be able to recover
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING


class TestFSMManager:
    """Test FSM manager functionality."""
    
    @pytest.mark.asyncio
    async def test_fsm_manager_get_or_create(self):
        """Test FSM manager get_or_create functionality."""
        manager = AsyncFSMManager()
        
        # First call creates new FSM
        fsm1 = await manager.get_or_create_fsm("session_001")
        assert fsm1.call_sid == "session_001"
        
        # Second call returns existing FSM
        fsm2 = await manager.get_or_create_fsm("session_001")
        assert fsm1 is fsm2
    
    @pytest.mark.asyncio
    async def test_fsm_manager_with_state_recovery(self):
        """Test FSM manager loads existing state."""
        with patch('app.utils.fsm_async.async_conversation_store') as mock_store:
            context_data = {"customer_name": "Test User"}
            mock_store.get_conversation.return_value = {
                "fsm_state": "ORDERING",
                "fsm_context": json.dumps(context_data)
            }
            
            manager = AsyncFSMManager()
            fsm = await manager.get_or_create_fsm("existing_session")
            
            # Should load existing state
            assert fsm.current_state == ConversationState.ORDERING
            assert fsm.context["customer_name"] == "Test User"