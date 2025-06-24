"""Integration tests for FSM with real Redis persistence - Task 3.2."""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import redis.asyncio as aioredis

from app.fsm.core import (
    AsyncConversationFSM,
    ConversationState,
    ConversationEvent,
    FSMError
)
from app.utils.fsm_async import AsyncFSMManager


class TestFSMRedisPersistence:
    """Test FSM state persistence with real Redis - Task 3.2.1."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_state_persistence_across_disconnections(self, real_redis_client):
        """Test that FSM state persists across disconnections."""
        call_sid = "test_persist_001"
        
        # Create FSM manager with real Redis
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        
        # Create and configure FSM
        fsm1 = await fsm_manager.get_fsm(call_sid)
        await fsm1.transition(ConversationState.MAIN_MENU)
        await fsm1.update_context({
            "customer_name": "John Doe",
            "order_started": True,
            "cart": [{"item": "California Roll", "quantity": 2}]
        })
        
        # Save current state
        original_state = fsm1.current_state
        original_context = fsm1.context.copy()
        
        # Simulate disconnection by creating new FSM manager
        del fsm1
        del fsm_manager
        
        # Reconnect with new manager
        fsm_manager2 = AsyncFSMManager(redis_client=real_redis_client)
        fsm2 = await fsm_manager2.get_fsm(call_sid)
        
        # Verify state was persisted
        assert fsm2.current_state == original_state
        assert fsm2.context["customer_name"] == original_context["customer_name"]
        assert fsm2.context["order_started"] == original_context["order_started"]
        assert len(fsm2.context["cart"]) == 1
        assert fsm2.context["cart"][0]["item"] == "California Roll"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_fsm_operations(self, real_redis_client):
        """Test concurrent FSM operations - Task 3.2.2."""
        call_sid = "test_concurrent_001"
        
        async def update_fsm_context(fsm_manager, update_data):
            """Helper to update FSM context."""
            fsm = await fsm_manager.get_fsm(call_sid)
            current_context = fsm.context.copy()
            current_context.update(update_data)
            await fsm.update_context(current_context)
            return fsm.context
        
        # Create multiple FSM managers simulating concurrent connections
        managers = []
        for i in range(3):
            manager = AsyncFSMManager(redis_client=real_redis_client)
            managers.append(manager)
        
        # Initialize FSM
        fsm_init = await managers[0].get_fsm(call_sid)
        await fsm_init.transition(ConversationState.ORDERING)
        await fsm_init.update_context({"cart": [], "updates": []})
        
        # Perform concurrent updates
        tasks = []
        for i, manager in enumerate(managers):
            update_task = update_fsm_context(
                manager,
                {"updates": fsm_init.context["updates"] + [f"Update from manager {i}"]}
            )
            tasks.append(update_task)
        
        # Wait for all updates
        results = await asyncio.gather(*tasks)
        
        # Verify final state
        final_fsm = await managers[0].get_fsm(call_sid)
        
        # Should have updates from all managers (last write wins)
        assert len(final_fsm.context["updates"]) > 0
        assert final_fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fsm_recovery_from_crashes(self, real_redis_client):
        """Test FSM recovery from crashes - Task 3.2.3."""
        call_sid = "test_recovery_001"
        
        # Create FSM and simulate partial update
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        fsm = await fsm_manager.get_fsm(call_sid)
        
        # Start a complex operation
        await fsm.transition(ConversationState.ORDERING)
        await fsm.update_context({
            "customer_name": "Jane",
            "cart": [{"item": "Spicy Tuna", "quantity": 1}],
            "operation_id": "op_12345"
        })
        
        # Simulate crash during state transition
        with patch.object(fsm, '_save_to_redis', side_effect=Exception("Simulated crash")):
            try:
                await fsm.transition(ConversationState.VALIDATION)
            except:
                pass  # Crash occurred
        
        # Create new manager to recover
        recovery_manager = AsyncFSMManager(redis_client=real_redis_client)
        recovered_fsm = await recovery_manager.get_fsm(call_sid)
        
        # Should recover to last known good state
        assert recovered_fsm.current_state == ConversationState.ORDERING
        assert recovered_fsm.context["customer_name"] == "Jane"
        assert recovered_fsm.context["operation_id"] == "op_12345"
        
        # Should be able to continue operations
        await recovered_fsm.transition(ConversationState.VALIDATION)
        assert recovered_fsm.current_state == ConversationState.VALIDATION
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fsm_event_queue_handling(self, real_redis_client):
        """Test FSM event queue handling - Task 3.2.4."""
        call_sid = "test_queue_001"
        
        # Create FSM with event tracking
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        fsm = await fsm_manager.get_fsm(call_sid)
        
        # Track processed events
        events_processed = []
        
        async def process_event(event: ConversationEvent):
            """Process an event and track it."""
            old_state = fsm.current_state
            
            # Map events to transitions
            if event == ConversationEvent.INITIAL_CONTACT:
                await fsm.transition(ConversationState.GREETING)
            elif event == ConversationEvent.CUSTOMER_GREETED:
                await fsm.transition(ConversationState.MAIN_MENU)
            elif event == ConversationEvent.ORDER_STARTED:
                await fsm.transition(ConversationState.ORDERING)
            elif event == ConversationEvent.CART_FINALIZED:
                await fsm.transition(ConversationState.VALIDATION)
            
            events_processed.append({
                "event": event,
                "from_state": old_state,
                "to_state": fsm.current_state,
                "timestamp": datetime.now()
            })
        
        # Queue multiple events
        events = [
            ConversationEvent.INITIAL_CONTACT,
            ConversationEvent.CUSTOMER_GREETED,
            ConversationEvent.ORDER_STARTED,
            ConversationEvent.CART_FINALIZED
        ]
        
        # Process events in sequence
        for event in events:
            await process_event(event)
            # Small delay to simulate real processing
            await asyncio.sleep(0.1)
        
        # Verify events were processed in order
        assert len(events_processed) == 4
        assert events_processed[0]["event"] == ConversationEvent.INITIAL_CONTACT
        assert events_processed[-1]["event"] == ConversationEvent.CART_FINALIZED
        
        # Verify state transitions were correct
        assert events_processed[0]["to_state"] == ConversationState.GREETING
        assert events_processed[1]["to_state"] == ConversationState.MAIN_MENU
        assert events_processed[2]["to_state"] == ConversationState.ORDERING
        assert events_processed[3]["to_state"] == ConversationState.VALIDATION
        
        # Verify final state in Redis
        recovered_fsm = await fsm_manager.get_fsm(call_sid)
        assert recovered_fsm.current_state == ConversationState.VALIDATION


class TestFSMRedisFailover:
    """Test FSM behavior during Redis failures."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fsm_redis_connection_loss(self, real_redis_client):
        """Test FSM behavior when Redis connection is lost."""
        call_sid = "test_failover_001"
        
        # Create FSM manager
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        fsm = await fsm_manager.get_fsm(call_sid)
        
        # Set initial state
        await fsm.transition(ConversationState.ORDERING)
        await fsm.update_context({"customer_name": "Bob"})
        
        # Simulate Redis connection loss
        with patch.object(real_redis_client, 'get', side_effect=aioredis.ConnectionError("Connection lost")):
            with patch.object(real_redis_client, 'set', side_effect=aioredis.ConnectionError("Connection lost")):
                
                # FSM should fallback to in-memory state
                current_state = fsm.current_state
                assert current_state == ConversationState.ORDERING
                
                # Should still be able to transition (in memory only)
                await fsm.transition(ConversationState.VALIDATION)
                assert fsm.current_state == ConversationState.VALIDATION
        
        # When Redis reconnects, should sync state
        await fsm._save_to_redis()
        
        # Verify state was saved
        new_fsm = await fsm_manager.get_fsm(call_sid)
        assert new_fsm.current_state == ConversationState.VALIDATION
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fsm_redis_timeout_handling(self, real_redis_client):
        """Test FSM handling of Redis timeouts."""
        call_sid = "test_timeout_001"
        
        # Create FSM with short timeout
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        fsm = await fsm_manager.get_fsm(call_sid)
        
        # Mock slow Redis operations
        async def slow_get(*args, **kwargs):
            await asyncio.sleep(5)  # Simulate slow response
            return None
        
        with patch.object(real_redis_client, 'get', side_effect=slow_get):
            # Should timeout and use default state
            start_time = time.time()
            fsm = await fsm_manager.get_fsm("new_call_001")
            elapsed = time.time() - start_time
            
            # Should not wait for full 5 seconds
            assert elapsed < 3
            assert fsm.current_state == ConversationState.INITIAL
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fsm_data_consistency(self, real_redis_client):
        """Test FSM data consistency across operations."""
        call_sid = "test_consistency_001"
        
        # Create FSM and perform multiple operations
        fsm_manager = AsyncFSMManager(redis_client=real_redis_client)
        fsm = await fsm_manager.get_fsm(call_sid)
        
        # Perform series of operations
        operations = [
            (ConversationState.GREETING, {"step": 1}),
            (ConversationState.MAIN_MENU, {"step": 2, "customer_name": "Alice"}),
            (ConversationState.ORDERING, {"step": 3, "cart": []}),
            (ConversationState.VALIDATION, {"step": 4, "total": 25.90})
        ]
        
        for state, context_update in operations:
            await fsm.transition(state)
            current_context = fsm.context.copy()
            current_context.update(context_update)
            await fsm.update_context(current_context)
        
        # Verify all updates are consistent
        final_fsm = await fsm_manager.get_fsm(call_sid)
        assert final_fsm.context["step"] == 4
        assert final_fsm.context["customer_name"] == "Alice"
        assert "cart" in final_fsm.context
        assert final_fsm.context["total"] == 25.90
        
        # Verify transition history if tracked
        if hasattr(final_fsm, 'transition_history'):
            assert len(final_fsm.transition_history) >= 4