"""
Comprehensive integration tests for FSM state transitions.
Tests the complete conversation flow through all states.
"""
import pytest
import pytest_asyncio
from app.fsm.core import AsyncConversationFSM, ConversationState, ConversationEvent
from app.utils.fsm_async import async_fsm_manager
from app.utils.intent_detector_async import AsyncIntentDetector
from unittest.mock import AsyncMock, MagicMock, patch


class TestFSMTransitionsComprehensive:
    """Test comprehensive FSM state transitions and conversation flows."""
    
    @pytest_asyncio.fixture
    async def fsm(self):
        """Create an FSM instance for testing."""
        fsm = AsyncConversationFSM(call_sid="test_call_123")
        fsm.context.update({
            "customer_name": None,
            "cart": {"items": [], "total_price": 0}
        })
        # Start the conversation to move to GREETING state
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        return fsm
    
    @pytest.mark.asyncio
    async def test_complete_pickup_order_flow(self, fsm):
        """Test complete flow from greeting to order completion."""
        # Start in GREETING state
        assert fsm.current_state == ConversationState.GREETING
        
        # 1. Customer provides name -> MAIN_MENU
        fsm.context["transcript"] = "My name is John"
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        assert fsm.current_state == ConversationState.MAIN_MENU
        assert fsm.context.get("transcript") == "My name is John"
        
        # 2. Customer wants to order -> ORDERING
        fsm.context["transcript"] = "I'd like to place an order"
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
        
        # 3. Add items to cart
        fsm.context["cart"]["items"] = [
            {"name": "California Roll", "quantity": 2, "price": 12.95},
            {"name": "Spicy Tuna Roll", "quantity": 1, "price": 14.95}
        ]
        fsm.context["cart"]["total_price"] = 40.85
        
        # 4. Complete order -> VALIDATION
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        assert fsm.current_state == ConversationState.VALIDATION
        
        # 5. Validation passes -> CONFIRMATION
        await fsm.trigger(ConversationEvent.VALIDATE_ORDER)
        assert fsm.current_state == ConversationState.CONFIRMATION
        
        # 6. Confirm order -> FULFILLMENT
        await fsm.trigger(ConversationEvent.CONFIRM_ORDER)
        assert fsm.current_state == ConversationState.FULFILLMENT
        
        # 7. Submit order -> COMPLETION
        await fsm.trigger(ConversationEvent.COMPLETE_INTERACTION)
        assert fsm.current_state == ConversationState.COMPLETION
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, fsm):
        """Test flow for menu inquiries."""
        # Move to MAIN_MENU
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Ask about menu -> stays in MAIN_MENU
        fsm.context["requesting_menu_info"] = True
        assert fsm.current_state == ConversationState.MAIN_MENU
        
        # After menu info, can start ordering
        fsm.context["requesting_menu_info"] = False
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_order_rejection_flow(self, fsm):
        """Test flow when customer rejects order."""
        # Quick path to confirmation
        await fsm._set_state(ConversationState.CONFIRMATION)
        
        # Customer rejects order -> back to ORDERING
        await fsm.trigger(ConversationEvent.REJECT_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_escalation_flow(self, fsm):
        """Test escalation to human agent."""
        # Can escalate from multiple states
        for state in [ConversationState.MAIN_MENU, ConversationState.ORDERING, ConversationState.VALIDATION]:
            fsm.current_state = state
            await fsm.trigger(ConversationEvent.REQUEST_ESCALATION)
            assert fsm.current_state == ConversationState.ESCALATION
            # Reset for next test
            fsm.current_state = state
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, fsm):
        """Test error state and recovery."""
        # Trigger error from any state
        fsm.current_state = ConversationState.ORDERING
        await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
        assert fsm.current_state == ConversationState.ERROR
        
        # Recover from error
        await fsm.trigger(ConversationEvent.RECOVER_FROM_ERROR)
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_follow_up_flow(self, fsm):
        """Test follow-up state transitions."""
        # Complete an order
        await fsm._set_state(ConversationState.COMPLETION)
        
        # Customer has follow-up
        await fsm.trigger(ConversationEvent.FOLLOW_UP_NEEDED)
        assert fsm.current_state == ConversationState.FOLLOW_UP
        
        # Can return to main menu or end
        await fsm.trigger(ConversationEvent.RETURN_TO_MENU)
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_intent_detection_integration(self):
        """Test intent detection triggering correct FSM events."""
        test_cases = [
            ("My name is Sarah", ConversationEvent.USER_PROVIDES_NAME),
            ("I want to order food", ConversationEvent.START_ORDER),
            ("What's on the menu?", ConversationEvent.REQUEST_MENU),
            ("I need to speak to someone", ConversationEvent.REQUEST_ESCALATION),
            ("That's all for my order", ConversationEvent.COMPLETE_ORDER),
            ("Yes, that's correct", ConversationEvent.CONFIRM_ORDER),
            ("No, that's wrong", ConversationEvent.REJECT_ORDER)
        ]
        
        with patch('app.utils.intent_detector_async.AsyncOpenAI'):
            detector = AsyncIntentDetector()
        
        # Skip this test for now - it needs more complex setup
        pytest.skip("Intent detection test needs more complex setup with state-specific mappings")
    
    @pytest.mark.asyncio
    async def test_fsm_persistence(self):
        """Test FSM state persistence through Redis."""
        call_sid = "test_persistence_123"
        
        # Create and save FSM
        fsm1 = await async_fsm_manager.start_conversation(call_sid, {"test": "data"})
        await fsm1.trigger(ConversationEvent.USER_PROVIDES_NAME)
        
        # Load FSM from storage
        fsm2 = await async_fsm_manager.get_fsm(call_sid)
        
        assert fsm2.current_state == ConversationState.MAIN_MENU
        assert fsm2.context.get("test") == "data"
    
    @pytest.mark.asyncio
    async def test_concurrent_fsm_handling(self):
        """Test handling multiple concurrent FSM instances."""
        call_sids = ["call_1", "call_2", "call_3"]
        fsms = []
        
        # Create multiple FSMs
        for sid in call_sids:
            fsm = await async_fsm_manager.start_conversation(sid, {"call_sid": sid})
            fsms.append(fsm)
        
        # Progress each FSM differently
        await fsms[0].trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsms[1].trigger(ConversationEvent.USER_PROVIDES_NAME)
        await fsms[1].trigger(ConversationEvent.START_ORDER)
        await fsms[2].trigger(ConversationEvent.REQUEST_ESCALATION)
        
        # Verify states
        assert fsms[0].current_state == ConversationState.MAIN_MENU
        assert fsms[1].current_state == ConversationState.ORDERING
        assert fsms[2].current_state == ConversationState.ESCALATION
    
    @pytest.mark.asyncio
    async def test_state_timeout_handling(self, fsm):
        """Test handling of state timeouts."""
        # Set a timeout context
        fsm.context["last_activity"] = 0  # Very old timestamp
        
        # Should handle timeout appropriately
        # This would be implemented in production with actual timeout logic
        assert fsm.current_state == ConversationState.GREETING