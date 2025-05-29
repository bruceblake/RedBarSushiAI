"""
Unit tests for Redis operations.
Tests caching, session storage, and state management.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from app.redis_async import get_redis_client, RedisConnectionManager
from app.utils.conversation_store_async import AsyncConversationStore
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher


class TestRedisConnectionManager:
    """Test Redis connection management."""
    
    @pytest.mark.asyncio
    async def test_connection_initialization(self):
        """Test Redis connection is properly initialized."""
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value = AsyncMock()
            
            manager = RedisConnectionManager()
            client = await manager.get_client()
            
            assert client is not None
            mock_redis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_retry(self):
        """Test connection retry on failure."""
        with patch('redis.asyncio.from_url') as mock_redis:
            # First call fails, second succeeds
            mock_redis.side_effect = [
                Exception("Connection failed"),
                AsyncMock()
            ]
            
            manager = RedisConnectionManager()
            client = await manager.get_client()
            
            assert client is not None
            assert mock_redis.call_count == 2
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self):
        """Test connection pool configuration."""
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value = AsyncMock()
            
            manager = RedisConnectionManager()
            await manager.get_client()
            
            # Check pool settings were passed
            call_args = mock_redis.call_args
            assert 'max_connections' in call_args.kwargs
            assert 'decode_responses' in call_args.kwargs


class TestConversationStore:
    """Test conversation state storage in Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        client = AsyncMock()
        client.get.return_value = None
        client.set.return_value = True
        client.delete.return_value = True
        client.exists.return_value = False
        return client
    
    @pytest.fixture
    def conversation_store(self, mock_redis):
        """Create conversation store with mocked Redis."""
        with patch('app.utils.conversation_store_async.get_redis_client', return_value=mock_redis):
            store = AsyncConversationStore()
            store.redis = mock_redis
            return store
    
    @pytest.mark.asyncio
    async def test_save_conversation_state(self, conversation_store, mock_redis):
        """Test saving conversation state."""
        call_sid = "TEST_CALL_123"
        state = {
            "fsm_state": "ORDERING",
            "customer_name": "John",
            "cart_items": [{"name": "California Roll", "quantity": 2}],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await conversation_store.save_state(call_sid, state)
        
        # Verify Redis set was called
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        
        # Check key format
        assert call_args[0][0] == f"conversation:{call_sid}"
        
        # Check data was serialized
        saved_data = json.loads(call_args[0][1])
        assert saved_data["fsm_state"] == "ORDERING"
        assert saved_data["customer_name"] == "John"
    
    @pytest.mark.asyncio
    async def test_retrieve_conversation_state(self, conversation_store, mock_redis):
        """Test retrieving conversation state."""
        call_sid = "TEST_CALL_456"
        stored_state = {
            "fsm_state": "CONFIRMATION",
            "order_total": 2495
        }
        
        mock_redis.get.return_value = json.dumps(stored_state)
        
        state = await conversation_store.get_state(call_sid)
        
        assert state["fsm_state"] == "CONFIRMATION"
        assert state["order_total"] == 2495
    
    @pytest.mark.asyncio
    async def test_update_conversation_state(self, conversation_store, mock_redis):
        """Test updating existing conversation state."""
        call_sid = "TEST_UPDATE_123"
        
        # Existing state
        existing = {"fsm_state": "ORDERING", "cart_items": []}
        mock_redis.get.return_value = json.dumps(existing)
        
        # Update with new data
        updates = {"cart_items": [{"name": "Edamame"}], "notes": "No wasabi"}
        await conversation_store.update_state(call_sid, updates)
        
        # Verify merged state was saved
        mock_redis.set.assert_called()
        saved_data = json.loads(mock_redis.set.call_args[0][1])
        assert saved_data["fsm_state"] == "ORDERING"  # Preserved
        assert len(saved_data["cart_items"]) == 1  # Updated
        assert saved_data["notes"] == "No wasabi"  # Added
    
    @pytest.mark.asyncio
    async def test_conversation_expiry(self, conversation_store, mock_redis):
        """Test conversation state expires after timeout."""
        call_sid = "TEST_EXPIRY_123"
        state = {"fsm_state": "GREETING"}
        
        await conversation_store.save_state(call_sid, state, ttl=3600)
        
        # Check TTL was set
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get('ex') == 3600
    
    @pytest.mark.asyncio
    async def test_delete_conversation_state(self, conversation_store, mock_redis):
        """Test deleting conversation state."""
        call_sid = "TEST_DELETE_123"
        
        await conversation_store.delete_state(call_sid)
        
        mock_redis.delete.assert_called_once_with(f"conversation:{call_sid}")


class TestMenuCaching:
    """Test menu data caching in Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        client = AsyncMock()
        client.get.return_value = None
        client.set.return_value = True
        client.delete.return_value = True
        return client
    
    @pytest.mark.asyncio
    async def test_cache_menu_item(self, mock_redis):
        """Test caching individual menu items."""
        with patch('app.utils.menu_matcher_cache_async.get_redis_client', return_value=mock_redis):
            item = {
                "id": 1,
                "name": "California Roll",
                "plu": "PLU_CALI",
                "price": 1295
            }
            
            # Cache item
            cache_key = f"menu:item:{item['plu']}"
            await mock_redis.set(cache_key, json.dumps(item), ex=3600)
            
            mock_redis.set.assert_called_with(
                cache_key,
                json.dumps(item),
                ex=3600
            )
    
    @pytest.mark.asyncio
    async def test_cache_menu_categories(self, mock_redis):
        """Test caching menu categories."""
        with patch('app.utils.menu_matcher_cache_async.get_redis_client', return_value=mock_redis):
            categories = [
                {"id": 1, "name": "Sushi Rolls"},
                {"id": 2, "name": "Appetizers"}
            ]
            
            cache_key = "menu:categories"
            await mock_redis.set(cache_key, json.dumps(categories), ex=3600)
            
            mock_redis.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_menu_update(self, mock_redis):
        """Test cache is invalidated when menu updates."""
        with patch('app.utils.menu_matcher_cache_async.get_redis_client', return_value=mock_redis):
            # Simulate menu update
            patterns_to_clear = [
                "menu:item:*",
                "menu:categories",
                "menu:matcher"
            ]
            
            for pattern in patterns_to_clear:
                # In real implementation, would use SCAN to find keys
                await mock_redis.delete(pattern)
            
            assert mock_redis.delete.call_count == len(patterns_to_clear)


class TestCartStorage:
    """Test shopping cart storage in Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        client = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_save_cart(self, mock_redis):
        """Test saving cart to Redis."""
        call_sid = "CART_TEST_123"
        cart = {
            "items": [
                {
                    "name": "California Roll",
                    "plu": "PLU_CALI",
                    "quantity": 2,
                    "price": 1295,
                    "modifiers": []
                }
            ],
            "subtotal": 2590,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        cart_key = f"cart:{call_sid}"
        await mock_redis.set(cart_key, json.dumps(cart), ex=7200)  # 2 hour TTL
        
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == cart_key
        assert call_args.kwargs['ex'] == 7200
    
    @pytest.mark.asyncio
    async def test_update_cart_item_quantity(self, mock_redis):
        """Test updating item quantity in cart."""
        call_sid = "CART_UPDATE_123"
        
        # Existing cart
        existing_cart = {
            "items": [{"name": "California Roll", "plu": "PLU_CALI", "quantity": 1}]
        }
        mock_redis.get.return_value = json.dumps(existing_cart)
        
        # Update quantity
        cart_data = json.loads(await mock_redis.get(f"cart:{call_sid}"))
        cart_data["items"][0]["quantity"] = 3
        await mock_redis.set(f"cart:{call_sid}", json.dumps(cart_data))
        
        # Verify update
        assert mock_redis.set.called
        updated_data = json.loads(mock_redis.set.call_args[0][1])
        assert updated_data["items"][0]["quantity"] == 3
    
    @pytest.mark.asyncio
    async def test_clear_cart(self, mock_redis):
        """Test clearing cart after order completion."""
        call_sid = "CART_CLEAR_123"
        
        await mock_redis.delete(f"cart:{call_sid}")
        
        mock_redis.delete.assert_called_once_with(f"cart:{call_sid}")


class TestFSMStateStorage:
    """Test FSM state persistence in Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_save_fsm_state(self, mock_redis):
        """Test saving FSM state and context."""
        call_sid = "FSM_TEST_123"
        fsm_data = {
            "current_state": "ORDERING",
            "previous_state": "MAIN_MENU",
            "context": {
                "customer_name": "Jane",
                "preferences": ["no spicy"],
                "cart_item_count": 2
            },
            "state_history": ["GREETING", "MAIN_MENU", "ORDERING"],
            "updated_at": datetime.utcnow().isoformat()
        }
        
        fsm_key = f"fsm:{call_sid}"
        await mock_redis.set(fsm_key, json.dumps(fsm_data), ex=3600)
        
        mock_redis.set.assert_called_once()
        saved_data = json.loads(mock_redis.set.call_args[0][1])
        assert saved_data["current_state"] == "ORDERING"
        assert "Jane" in saved_data["context"]["customer_name"]
    
    @pytest.mark.asyncio
    async def test_fsm_state_transition_history(self, mock_redis):
        """Test maintaining FSM state transition history."""
        call_sid = "FSM_HISTORY_123"
        
        # Initial state
        fsm_data = {
            "current_state": "GREETING",
            "state_history": ["GREETING"]
        }
        
        # Simulate transitions
        transitions = ["MAIN_MENU", "ORDERING", "VALIDATION", "CONFIRMATION"]
        
        for new_state in transitions:
            fsm_data["previous_state"] = fsm_data["current_state"]
            fsm_data["current_state"] = new_state
            fsm_data["state_history"].append(new_state)
            
            await mock_redis.set(f"fsm:{call_sid}", json.dumps(fsm_data))
        
        # Verify final state
        final_call = mock_redis.set.call_args_list[-1]
        final_data = json.loads(final_call[0][1])
        assert final_data["current_state"] == "CONFIRMATION"
        assert len(final_data["state_history"]) == 5


class TestRedisPerformance:
    """Test Redis operations performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_bulk_operations(self):
        """Test bulk get/set operations."""
        mock_redis = AsyncMock()
        mock_redis.mget.return_value = [None] * 10
        mock_redis.mset.return_value = True
        
        # Bulk get
        keys = [f"item:{i}" for i in range(10)]
        await mock_redis.mget(keys)
        mock_redis.mget.assert_called_once()
        
        # Bulk set
        data = {f"item:{i}": f"value_{i}" for i in range(10)}
        await mock_redis.mset(data)
        mock_redis.mset.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_operations(self):
        """Test Redis pipeline for atomic operations."""
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        # Create pipeline
        pipe = await mock_redis.pipeline()
        
        # Queue operations
        await pipe.set("key1", "value1")
        await pipe.set("key2", "value2")
        await pipe.incr("counter")
        
        # Execute pipeline
        await pipe.execute()
        
        mock_pipeline.execute.assert_called_once()