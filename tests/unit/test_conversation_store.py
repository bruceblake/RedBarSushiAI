"""
Comprehensive unit tests for conversation store operations - Task 2.3.3.


@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def mock_redis_functions():
    """Mock Redis functions."""
    with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
         patch('app.utils.conversation_store_async.redis_set') as mock_set, \
         patch('app.utils.conversation_store_async.redis_delete') as mock_delete, \
         patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get, \
         patch('app.utils.conversation_store_async.memory_cache_set') as mock_mem_set:
        yield mock_get, mock_set, mock_delete, mock_mem_get, mock_mem_set

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

@pytest.fixture
def store():
    """Create a fresh conversation store instance."""
    return AsyncConversationStore()

This module tests the AsyncConversationStore functionality including:
- Redis-based conversation persistence
- Memory fallback mechanisms
- JSON serialization/deserialization
- Message history management
- Error handling and recovery
- Expiration and TTL handling
"""
import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.utils.conversation_store_async import AsyncConversationStore, async_conversation_store, DEFAULT_EXPIRATION


class TestAsyncConversationStoreBasics:
    """Test basic conversation store functionality."""
    
    @pytest.fixture
    async def sample_conversation(self):
        """Sample conversation data."""
        return {
            "id": "test_session_123",
            "created_at": 1234567890.0,
            "updated_at": 1234567890.0,
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": 1234567890.0},
                {"role": "assistant", "content": "Hi there!", "timestamp": 1234567891.0}
            ],
            "context": {"customer_name": "John Doe"},
            "resolved": False,
            "items": []
        }
    
    def test_store_initialization(self, store):
        """Test conversation store initialization."""
        assert store.memory_store == {}
    
    def test_singleton_instance(self):
        """Test that singleton instance is available."""
        assert async_conversation_store is not None
        assert isinstance(async_conversation_store, AsyncConversationStore)


class TestGetConversation:
    """Test conversation retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_get_conversation_from_redis_success(self, store):
        """Test successful retrieval from Redis."""
        conversation_data = {
            "id": "test_123",
            "messages": [{"role": "user", "content": "test"}],
            "context": {}
        }
        
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get:
            
            mock_get.return_value = json.dumps(conversation_data).encode('utf-8')
            
            result = await store.get_conversation("test_123")
            
            assert result["id"] == "test_123"
            assert len(result["messages"]) == 1
            mock_get.assert_called_once_with("conv:test_123")
            mock_mem_get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_conversation_redis_miss_memory_hit(self, store):
        """Test fallback to memory cache when Redis misses."""
        conversation_data = {
            "id": "test_456",
            "messages": [],
            "context": {"fallback": True}
        }
        
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get:
            
            mock_get.return_value = None
            mock_mem_get.return_value = conversation_data
            
            result = await store.get_conversation("test_456")
            
            assert result["context"]["fallback"] is True
            mock_get.assert_called_once_with("conv:test_456")
            mock_mem_get.assert_called_once_with("conv:test_456")
    
    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, store):
        """Test behavior when conversation is not found."""
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get:
            
            mock_get.return_value = None
            mock_mem_get.return_value = None
            
            result = await store.get_conversation("not_found")
            
            # Should return new conversation structure
            assert result["id"] == "not_found"
            assert result["messages"] == []
            assert result["context"] == {}
            assert result["resolved"] is False
            assert result["items"] == []
            assert "created_at" in result
            assert "updated_at" in result
    
    @pytest.mark.asyncio
    async def test_get_conversation_invalid_json(self, store):
        """Test handling of invalid JSON data."""
        with patch('app.utils.conversation_store_async.redis_get') as mock_get:
            mock_get.return_value = b"invalid json {"
            
            result = await store.get_conversation("invalid_json")
            
            # Should return new conversation on JSON decode error
            assert result["id"] == "invalid_json"
            assert result["messages"] == []
    
    @pytest.mark.asyncio
    async def test_get_conversation_invalid_format(self, store):
        """Test handling of invalid conversation format."""
        invalid_data = {"id": "test", "messages": "not_a_list"}  # Invalid format
        
        with patch('app.utils.conversation_store_async.redis_get') as mock_get:
            mock_get.return_value = json.dumps(invalid_data).encode('utf-8')
            
            result = await store.get_conversation("test")
            
            # Should return new conversation for invalid format
            assert result["id"] == "test"
            assert result["messages"] == []
    
    @pytest.mark.asyncio
    async def test_get_conversation_redis_exception(self, store):
        """Test handling of Redis exceptions."""
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get:
            
            mock_get.side_effect = Exception("Redis connection failed")
            mock_mem_get.return_value = None
            
            result = await store.get_conversation("exception_test")
            
            # Should return new conversation on exception
            assert result["id"] == "exception_test"
            assert result["messages"] == []


class TestSaveConversation:
    """Test conversation saving functionality."""
    
    @pytest.mark.asyncio
    async def test_save_conversation_redis_success(self, store):
        """Test successful saving to Redis."""
        conversation_data = {
            "id": "save_test",
            "messages": [],
            "context": {}
        }
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await store.save_conversation("save_test", conversation_data)
            
            assert result is True
            mock_set.assert_called_once()
            call_args = mock_set.call_args[0]
            assert call_args[0] == "conv:save_test"
            
            # Verify JSON serialization
            saved_data = json.loads(call_args[1])
            assert saved_data["id"] == "save_test"
            assert "updated_at" in saved_data
    
    @pytest.mark.asyncio
    async def test_save_conversation_redis_failure_memory_fallback(self, store):
        """Test fallback to memory when Redis fails."""
        conversation_data = {"id": "fallback_test", "messages": []}
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set, \
             patch('app.utils.conversation_store_async.memory_cache_set') as mock_mem_set:
            
            mock_set.return_value = False
            
            result = await store.save_conversation("fallback_test", conversation_data)
            
            assert result is True
            mock_set.assert_called_once()
            mock_mem_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_conversation_both_fail(self, store):
        """Test when both Redis and memory fallback fail."""
        conversation_data = {"id": "fail_test", "messages": []}
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set, \
             patch('app.utils.conversation_store_async.memory_cache_set') as mock_mem_set:
            
            mock_set.side_effect = Exception("Redis error")
            mock_mem_set.side_effect = Exception("Memory error")
            
            result = await store.save_conversation("fail_test", conversation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_save_conversation_updates_timestamp(self, store):
        """Test that save_conversation updates the timestamp."""
        conversation_data = {
            "id": "timestamp_test",
            "messages": [],
            "updated_at": 1000.0  # Old timestamp
        }
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set, \
             patch('time.time', return_value=2000.0):
            
            mock_set.return_value = True
            
            await store.save_conversation("timestamp_test", conversation_data)
            
            # Verify timestamp was updated
            call_args = mock_set.call_args[0]
            saved_data = json.loads(call_args[1])
            assert saved_data["updated_at"] == 2000.0
    
    @pytest.mark.asyncio
    async def test_save_conversation_custom_expiration(self, store):
        """Test saving with custom expiration time."""
        conversation_data = {"id": "expire_test", "messages": []}
        custom_expiration = 7200  # 2 hours
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            await store.save_conversation("expire_test", conversation_data, custom_expiration)
            
            call_args = mock_set.call_args[0]
            assert call_args[2] == custom_expiration  # Expiration parameter


class TestUpdateConversation:
    """Test conversation update functionality."""
    
    @pytest.mark.asyncio
    async def test_update_conversation_success(self, store):
        """Test successful conversation update."""
        existing_conversation = {
            "id": "update_test",
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {"name": "John"},
            "updated_at": 1000.0
        }
        
        update_data = {
            "context": {"name": "John", "phone": "555-1234"},
            "resolved": True
        }
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save, \
             patch('time.time', return_value=2000.0):
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = True
            
            result = await store.update_conversation("update_test", update_data)
            
            assert result is True
            mock_get.assert_called_once_with("update_test")
            mock_save.assert_called_once()
            
            # Verify updated data
            saved_conversation = mock_save.call_args[0][1]
            assert saved_conversation["context"]["phone"] == "555-1234"
            assert saved_conversation["resolved"] is True
            assert saved_conversation["updated_at"] == 2000.0
    
    @pytest.mark.asyncio
    async def test_update_conversation_merge_behavior(self, store):
        """Test that update properly merges data."""
        existing_conversation = {
            "id": "merge_test",
            "messages": [{"role": "user", "content": "test"}],
            "context": {"key1": "value1", "key2": "value2"},
            "items": ["item1"]
        }
        
        update_data = {
            "context": {"key2": "updated", "key3": "new"},
            "items": ["item1", "item2"]
        }
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save:
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = True
            
            await store.update_conversation("merge_test", update_data)
            
            saved_conversation = mock_save.call_args[0][1]
            
            # Verify merge behavior (dict.update() semantics)
            assert saved_conversation["context"] == {"key2": "updated", "key3": "new"}
            assert saved_conversation["items"] == ["item1", "item2"]
            assert saved_conversation["messages"] == [{"role": "user", "content": "test"}]


class TestAddMessage:
    """Test message addition functionality."""
    
    @pytest.mark.asyncio
    async def test_add_message_to_existing_conversation(self, store):
        """Test adding message to existing conversation."""
        existing_conversation = {
            "id": "msg_test",
            "messages": [{"role": "user", "content": "Hello"}],
            "context": {}
        }
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save, \
             patch('time.time', return_value=1234567890.0):
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = True
            
            result = await store.add_message("msg_test", "assistant", "Hi there!")
            
            assert result is True
            
            saved_conversation = mock_save.call_args[0][1]
            assert len(saved_conversation["messages"]) == 2
            
            new_message = saved_conversation["messages"][1]
            assert new_message["role"] == "assistant"
            assert new_message["content"] == "Hi there!"
            assert new_message["timestamp"] == 1234567890.0
    
    @pytest.mark.asyncio
    async def test_add_message_initialize_messages_array(self, store):
        """Test adding message when messages array doesn't exist."""
        existing_conversation = {
            "id": "init_msg_test",
            "context": {}
            # No messages array
        }
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save:
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = True
            
            result = await store.add_message("init_msg_test", "user", "First message")
            
            assert result is True
            
            saved_conversation = mock_save.call_args[0][1]
            assert "messages" in saved_conversation
            assert len(saved_conversation["messages"]) == 1
            assert saved_conversation["messages"][0]["content"] == "First message"
    
    @pytest.mark.asyncio
    async def test_add_message_save_failure(self, store):
        """Test handling when save fails during message addition."""
        existing_conversation = {"id": "save_fail", "messages": []}
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save:
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = False
            
            result = await store.add_message("save_fail", "user", "Failed message")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_add_message_custom_expiration(self, store):
        """Test adding message with custom expiration."""
        existing_conversation = {"id": "expire_msg", "messages": []}
        custom_expiration = 3600
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save:
            
            mock_get.return_value = existing_conversation
            mock_save.return_value = True
            
            await store.add_message("expire_msg", "user", "Test", custom_expiration)
            
            # Verify custom expiration was passed to save_conversation
            assert mock_save.call_args[0][2] == custom_expiration


class TestDeleteConversation:
    """Test conversation deletion functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, store):
        """Test successful conversation deletion."""
        with patch('app.utils.conversation_store_async.redis_delete') as mock_delete, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get, \
             patch('app.utils.conversation_store_async.memory_cache_set') as mock_mem_set:
            
            mock_mem_get.return_value = {"some": "data"}
            
            result = await store.delete_conversation("delete_test")
            
            assert result is True
            mock_delete.assert_called_once_with("conv:delete_test")
            mock_mem_set.assert_called_once_with("conv:delete_test", None)
    
    @pytest.mark.asyncio
    async def test_delete_conversation_no_memory_cache(self, store):
        """Test deletion when no memory cache exists."""
        with patch('app.utils.conversation_store_async.redis_delete') as mock_delete, \
             patch('app.utils.conversation_store_async.memory_cache_get') as mock_mem_get, \
             patch('app.utils.conversation_store_async.memory_cache_set') as mock_mem_set:
            
            mock_mem_get.return_value = None
            
            result = await store.delete_conversation("no_memory")
            
            assert result is True
            mock_delete.assert_called_once_with("conv:no_memory")
            mock_mem_set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_conversation_redis_exception(self, store):
        """Test deletion when Redis raises exception."""
        with patch('app.utils.conversation_store_async.redis_delete') as mock_delete:
            mock_delete.side_effect = Exception("Redis delete failed")
            
            result = await store.delete_conversation("delete_exception")
            
            assert result is False


class TestConversationStoreIntegration:
    """Test integration scenarios and complex workflows."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_lifecycle(self, store):
        """Test complete conversation lifecycle."""
        session_id = "lifecycle_test"
        
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.redis_set') as mock_set, \
             patch('app.utils.conversation_store_async.redis_delete') as mock_delete:
            
            # Initially no conversation exists
            mock_get.return_value = None
            mock_set.return_value = True
            
            # 1. Get new conversation
            conversation = await store.get_conversation(session_id)
            assert conversation["id"] == session_id
            assert len(conversation["messages"]) == 0
            
            # 2. Add first message
            await store.add_message(session_id, "user", "Hello")
            
            # 3. Update with context
            await store.update_conversation(session_id, {"context": {"name": "John"}})
            
            # 4. Add response message
            await store.add_message(session_id, "assistant", "Hi John!")
            
            # 5. Delete conversation
            result = await store.delete_conversation(session_id)
            assert result is True
            
            # Verify all operations were called
            assert mock_set.call_count >= 3  # Multiple saves
            mock_delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, store):
        """Test concurrent access to same conversation."""
        session_id = "concurrent_test"
        
        with patch('app.utils.conversation_store_async.redis_get') as mock_get, \
             patch('app.utils.conversation_store_async.redis_set') as mock_set:
            
            mock_get.return_value = json.dumps({"id": session_id, "messages": []}).encode()
            mock_set.return_value = True
            
            # Simulate concurrent message additions
            async def add_message_task(content):
                return await store.add_message(session_id, "user", content)
            
            results = await asyncio.gather(
                add_message_task("Message 1"),
                add_message_task("Message 2"),
                add_message_task("Message 3")
            )
            
            # All should succeed
            assert all(results)
            # Should have made multiple save calls
            assert mock_set.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_large_conversation_handling(self, store):
        """Test handling of large conversations."""
        large_messages = [
            {"role": "user", "content": f"Message {i}", "timestamp": time.time()}
            for i in range(1000)
        ]
        
        large_conversation = {
            "id": "large_test",
            "messages": large_messages,
            "context": {"large": True}
        }
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await store.save_conversation("large_test", large_conversation)
            
            assert result is True
            
            # Verify large data was serialized
            call_args = mock_set.call_args[0]
            serialized_data = call_args[1]
            assert len(serialized_data) > 10000  # Should be substantial
            
            # Should be valid JSON
            parsed = json.loads(serialized_data)
            assert len(parsed["messages"]) == 1000


class TestConversationStoreEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_session_id(self, store):
        """Test behavior with empty session ID."""
        with patch('app.utils.conversation_store_async.redis_get') as mock_get:
            mock_get.return_value = None
            
            result = await store.get_conversation("")
            
            assert result["id"] == ""
            mock_get.assert_called_once_with("conv:")
    
    @pytest.mark.asyncio
    async def test_none_conversation_data(self, store):
        """Test saving None conversation data."""
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.side_effect = TypeError("Object is not JSON serializable")
            
            result = await store.save_conversation("none_test", None)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_circular_reference_in_data(self, store):
        """Test handling of circular references in conversation data."""
        circular_data = {"id": "circular"}
        circular_data["self"] = circular_data  # Creates circular reference
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.side_effect = ValueError("Circular reference detected")
            
            result = await store.save_conversation("circular", circular_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_unicode_message_content(self, store):
        """Test handling of Unicode content in messages."""
        unicode_content = "Hello 世界! 🍣 emoji test"
        
        with patch.object(store, 'get_conversation') as mock_get, \
             patch.object(store, 'save_conversation') as mock_save:
            
            mock_get.return_value = {"id": "unicode", "messages": []}
            mock_save.return_value = True
            
            result = await store.add_message("unicode", "user", unicode_content)
            
            assert result is True
            
            saved_conversation = mock_save.call_args[0][1]
            assert saved_conversation["messages"][0]["content"] == unicode_content
    
    @pytest.mark.asyncio
    async def test_default_expiration_constant(self, store):
        """Test that default expiration is used correctly."""
        conversation_data = {"id": "expire_default", "messages": []}
        
        with patch('app.utils.conversation_store_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            await store.save_conversation("expire_default", conversation_data)
            
            call_args = mock_set.call_args[0]
            assert call_args[2] == DEFAULT_EXPIRATION  # Should use default