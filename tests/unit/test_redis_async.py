"""Tests for Redis async operations - Task 2.5."""

import pytest
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, call
import redis.asyncio as aioredis

from app.redis_async import (
    init_redis, get_redis, get_redis_client,
    redis_get, redis_set, redis_delete,
    memory_cache_get, memory_cache_set,
    cache_menu_data, get_cached_menu_data,
    cache_menu_item, get_cached_menu_item,
    clear_menu_cache,
    _redis_client, _memory_cache, _memory_cache_timestamps,
    DEFAULT_REDIS_CACHE_DURATION, DEFAULT_MEMORY_CACHE_DURATION
)


class TestRedisInitialization:
    """Test Redis initialization and connection - Task 2.5.1."""
    
    @pytest.mark.asyncio
    async def test_init_redis_success(self):
        """Test successful Redis initialization."""
        with patch('app.redis_async.aioredis.Redis.from_url') as mock_redis:
            # Mock Redis client
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_redis.return_value = mock_client
            
            with patch('app.redis_async.settings') as mock_settings:
                mock_settings.REDIS_URL = "redis://localhost:6379/0"
                mock_settings.CELERY_BROKER_URL = None
                
                # Initialize Redis
                result = await init_redis()
                
                assert result == mock_client
                assert mock_client.ping.called
                mock_redis.assert_called_with(
                    "redis://localhost:6379/0",
                    socket_timeout=2.0,
                    socket_connect_timeout=5.0,
                    decode_responses=False
                )
    
    @pytest.mark.asyncio
    async def test_init_redis_docker_environment(self):
        """Test Redis initialization in Docker environment."""
        with patch('app.redis_async.aioredis.Redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_redis.return_value = mock_client
            
            with patch('app.redis_async.settings') as mock_settings:
                mock_settings.REDIS_URL = "redis://localhost:6379/0"
                mock_settings.CELERY_BROKER_URL = None
                
                with patch('app.redis_async.os.environ.get') as mock_env:
                    mock_env.side_effect = lambda key, default="": "true" if key == "DOCKER" else default
                    
                    result = await init_redis()
                    
                    # Should replace localhost with redis
                    mock_redis.assert_called_with(
                        "redis://redis:6379/0",
                        socket_timeout=2.0,
                        socket_connect_timeout=5.0,
                        decode_responses=False
                    )
    
    @pytest.mark.asyncio
    async def test_init_redis_connection_failure(self):
        """Test Redis initialization with connection failure."""
        with patch('app.redis_async.aioredis.Redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=Exception("Connection refused"))
            mock_redis.return_value = mock_client
            
            with patch('app.redis_async.settings') as mock_settings:
                mock_settings.REDIS_URL = "redis://localhost:6379/0"
                mock_settings.CELERY_BROKER_URL = None
                
                result = await init_redis()
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_get_redis_when_not_initialized(self):
        """Test getting Redis client when not initialized."""
        # Clear global client
        import app.redis_async
        app.redis_async._redis_client = None
        
        with patch('app.redis_async.init_redis') as mock_init:
            mock_client = AsyncMock()
            mock_init.return_value = mock_client
            
            result = await get_redis()
            
            assert result == mock_client
            assert mock_init.called
    
    @pytest.mark.asyncio
    async def test_get_redis_not_available(self):
        """Test getting Redis client when not available."""
        import app.redis_async
        app.redis_async._redis_client = None
        
        with patch('app.redis_async.init_redis') as mock_init:
            mock_init.return_value = None
            
            with pytest.raises(Exception, match="Redis client not available"):
                await get_redis()


class TestRedisBasicOperations:
    """Test basic Redis get/set/delete operations - Task 2.5.1."""
    
    @pytest.mark.asyncio
    async def test_redis_set_string_value(self):
        """Test setting string value in Redis."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_set("test_key", "test_value")
            
            assert result is True
            mock_client.set.assert_called_with(
                "test_key",
                b"test_value",
                ex=DEFAULT_REDIS_CACHE_DURATION
            )
    
    @pytest.mark.asyncio
    async def test_redis_set_bytes_value(self):
        """Test setting bytes value in Redis."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_set("test_key", b"test_bytes", expire=60)
            
            assert result is True
            mock_client.set.assert_called_with(
                "test_key",
                b"test_bytes",
                ex=60
            )
    
    @pytest.mark.asyncio
    async def test_redis_set_error_handling(self):
        """Test error handling in redis_set."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(side_effect=Exception("Redis error"))
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_set("test_key", "test_value")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_redis_get_success(self):
        """Test getting value from Redis."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=b"test_value")
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_get("test_key")
            
            assert result == b"test_value"
            mock_client.get.assert_called_with("test_key")
    
    @pytest.mark.asyncio
    async def test_redis_get_not_found(self):
        """Test getting non-existent key from Redis."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_get("non_existent_key")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_redis_get_error_handling(self):
        """Test error handling in redis_get."""
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.side_effect = Exception("Connection error")
            
            result = await redis_get("test_key")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_redis_delete_success(self):
        """Test deleting key from Redis."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_delete("test_key")
            
            assert result is True
            mock_client.delete.assert_called_with("test_key")
    
    @pytest.mark.asyncio
    async def test_redis_delete_error_handling(self):
        """Test error handling in redis_delete."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=Exception("Delete error"))
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await redis_delete("test_key")
            
            assert result is False


class TestMemoryCache:
    """Test memory cache operations for fallback - Task 2.5.1."""
    
    def test_memory_cache_set_and_get(self):
        """Test setting and getting from memory cache."""
        # Clear cache first
        import app.redis_async
        app.redis_async._memory_cache.clear()
        app.redis_async._memory_cache_timestamps.clear()
        
        # Set value
        result = memory_cache_set("test_key", "test_value")
        assert result is True
        
        # Get value
        value = memory_cache_get("test_key")
        assert value == "test_value"
    
    def test_memory_cache_expiration(self):
        """Test memory cache expiration - Task 2.5.3."""
        import app.redis_async
        app.redis_async._memory_cache.clear()
        app.redis_async._memory_cache_timestamps.clear()
        
        # Set value with timestamp in the past
        app.redis_async._memory_cache["expired_key"] = "old_value"
        app.redis_async._memory_cache_timestamps["expired_key"] = time.time() - DEFAULT_MEMORY_CACHE_DURATION - 1
        
        # Try to get expired value
        value = memory_cache_get("expired_key")
        assert value is None
        
        # Verify cleanup
        assert "expired_key" not in app.redis_async._memory_cache
        assert "expired_key" not in app.redis_async._memory_cache_timestamps
    
    def test_memory_cache_size_limit(self):
        """Test memory cache size limit and cleanup."""
        import app.redis_async
        app.redis_async._memory_cache.clear()
        app.redis_async._memory_cache_timestamps.clear()
        
        # Add more than 100 items
        for i in range(110):
            memory_cache_set(f"key_{i}", f"value_{i}")
            time.sleep(0.001)  # Small delay to ensure different timestamps
        
        # Should keep only 50 most recent items
        assert len(app.redis_async._memory_cache) == 50
        
        # Verify most recent items are kept
        assert memory_cache_get("key_109") is not None
        assert memory_cache_get("key_0") is None
    
    def test_memory_cache_error_handling(self):
        """Test memory cache error handling."""
        import app.redis_async
        
        # Mock an error during cache operation
        original_update = app.redis_async._memory_cache.update
        app.redis_async._memory_cache.update = MagicMock(side_effect=Exception("Update error"))
        
        # Should handle error gracefully
        result = memory_cache_set("error_key", "error_value")
        # Restore original method
        app.redis_async._memory_cache.update = original_update
        
        # The set operation should still succeed despite the error in cleanup
        assert "error_key" in app.redis_async._memory_cache


class TestMenuCaching:
    """Test menu-specific caching operations."""
    
    @pytest.mark.asyncio
    async def test_cache_menu_data_success(self):
        """Test caching complete menu data."""
        mock_client = AsyncMock()
        
        menu_data = {
            "items": [{"id": "1", "name": "Item 1"}],
            "modifiers": [{"id": "2", "name": "Modifier 1"}],
            "modifier_groups": [{"id": "3", "name": "Group 1"}],
            "variants": [{"id": "4", "phrase": "Variant 1"}]
        }
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await cache_menu_data(menu_data, ttl=7200)
            
            assert result is True
            # Should cache complete data and individual components
            assert mock_set.call_count == 5
            
            # Verify calls
            calls = mock_set.call_args_list
            assert calls[0][0][0] == "menu:complete"
            assert calls[1][0][0] == "menu:items"
            assert calls[2][0][0] == "menu:modifiers"
            assert calls[3][0][0] == "menu:modifier_groups"
            assert calls[4][0][0] == "menu:variants"
    
    @pytest.mark.asyncio
    async def test_cache_menu_data_fallback_to_memory(self):
        """Test fallback to memory cache when Redis fails."""
        menu_data = {"items": [{"id": "1", "name": "Item 1"}]}
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.side_effect = Exception("Redis error")
            
            with patch('app.redis_async.memory_cache_set') as mock_memory_set:
                mock_memory_set.return_value = True
                
                result = await cache_menu_data(menu_data)
                
                assert result is False  # Redis failed
                mock_memory_set.assert_called_with("menu:complete", menu_data)
    
    @pytest.mark.asyncio
    async def test_get_cached_menu_data_from_redis(self):
        """Test getting menu data from Redis cache."""
        menu_data = {"items": [{"id": "1", "name": "Item 1"}]}
        menu_json = json.dumps(menu_data).encode('utf-8')
        
        with patch('app.redis_async.redis_get') as mock_get:
            mock_get.return_value = menu_json
            
            result = await get_cached_menu_data()
            
            assert result == menu_data
            mock_get.assert_called_with("menu:complete")
    
    @pytest.mark.asyncio
    async def test_get_cached_menu_data_fallback(self):
        """Test fallback to memory cache when Redis fails."""
        menu_data = {"items": [{"id": "1", "name": "Item 1"}]}
        
        with patch('app.redis_async.redis_get') as mock_get:
            mock_get.return_value = None
            
            with patch('app.redis_async.memory_cache_get') as mock_memory_get:
                mock_memory_get.return_value = menu_data
                
                result = await get_cached_menu_data()
                
                assert result == menu_data
    
    @pytest.mark.asyncio
    async def test_cache_menu_item(self):
        """Test caching individual menu item."""
        item_data = {"id": "1", "name": "Test Item", "plu": "PLU123"}
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await cache_menu_item("PLU123", item_data)
            
            assert result is True
            mock_set.assert_called_with(
                "menu:item:PLU123",
                json.dumps(item_data),
                expire=3600
            )
    
    @pytest.mark.asyncio
    async def test_get_cached_menu_item(self):
        """Test getting cached menu item."""
        item_data = {"id": "1", "name": "Test Item", "plu": "PLU123"}
        item_json = json.dumps(item_data).encode('utf-8')
        
        with patch('app.redis_async.redis_get') as mock_get:
            mock_get.return_value = item_json
            
            result = await get_cached_menu_item("PLU123")
            
            assert result == item_data
            mock_get.assert_called_with("menu:item:PLU123")
    
    @pytest.mark.asyncio
    async def test_clear_menu_cache(self):
        """Test clearing all menu cache entries."""
        mock_client = AsyncMock()
        
        # Mock scan_iter to return menu keys
        async def mock_scan_iter(match=None):
            yield b"menu:complete"
            yield b"menu:items"
            yield b"menu:item:PLU123"
        
        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock()
        
        # Setup memory cache with menu items
        import app.redis_async
        app.redis_async._memory_cache["menu:test"] = "value"
        app.redis_async._memory_cache["other:test"] = "value"
        app.redis_async._memory_cache_timestamps["menu:test"] = time.time()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            result = await clear_menu_cache()
            
            assert result is True
            # Should delete all found keys
            mock_client.delete.assert_called_with(
                b"menu:complete",
                b"menu:items",
                b"menu:item:PLU123"
            )
            
            # Memory cache should be cleared too
            assert "menu:test" not in app.redis_async._memory_cache
            assert "other:test" in app.redis_async._memory_cache  # Non-menu key should remain


class TestCacheExpiration:
    """Test cache expiration and TTL functionality - Task 2.5.3."""
    
    @pytest.mark.asyncio
    async def test_redis_set_with_custom_ttl(self):
        """Test setting values with custom TTL."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            # Test with custom TTL
            await redis_set("test_key", "test_value", expire=120)
            
            mock_client.set.assert_called_with(
                "test_key",
                b"test_value",
                ex=120
            )
    
    @pytest.mark.asyncio
    async def test_menu_cache_with_custom_ttl(self):
        """Test menu caching with custom TTL."""
        menu_data = {"items": [{"id": "1"}]}
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            await cache_menu_data(menu_data, ttl=1800)
            
            # All calls should use the custom TTL
            for call in mock_set.call_args_list:
                assert call[1]["expire"] == 1800
    
    def test_memory_cache_expiration_check(self):
        """Test memory cache expiration checking."""
        import app.redis_async
        app.redis_async._memory_cache.clear()
        app.redis_async._memory_cache_timestamps.clear()
        
        # Add items with different timestamps
        current_time = time.time()
        app.redis_async._memory_cache["fresh"] = "fresh_value"
        app.redis_async._memory_cache_timestamps["fresh"] = current_time
        
        app.redis_async._memory_cache["stale"] = "stale_value"
        app.redis_async._memory_cache_timestamps["stale"] = current_time - DEFAULT_MEMORY_CACHE_DURATION - 1
        
        # Fresh item should be returned
        assert memory_cache_get("fresh") == "fresh_value"
        
        # Stale item should be None and cleaned up
        assert memory_cache_get("stale") is None
        assert "stale" not in app.redis_async._memory_cache


class TestConnectionRecovery:
    """Test connection pooling and error recovery - Task 2.5.4."""
    
    @pytest.mark.asyncio
    async def test_redis_reconnection_after_failure(self):
        """Test Redis reconnection after connection failure."""
        import app.redis_async
        
        # First, simulate a failed connection
        app.redis_async._redis_client = None
        
        with patch('app.redis_async.init_redis') as mock_init:
            # First call fails, second succeeds
            mock_client = AsyncMock()
            mock_init.side_effect = [None, mock_client]
            
            # First attempt should fail
            with pytest.raises(Exception, match="Redis client not available"):
                await get_redis()
            
            # Clear the failed state
            app.redis_async._redis_client = None
            
            # Second attempt should succeed
            result = await get_redis()
            assert result == mock_client
    
    @pytest.mark.asyncio
    async def test_operation_retry_on_connection_error(self):
        """Test operation retry logic on connection errors."""
        mock_client = AsyncMock()
        
        # Simulate connection error then success
        mock_client.get.side_effect = [ConnectionError("Connection lost"), b"test_value"]
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            # First call raises error, second returns client
            mock_get_redis.side_effect = [Exception("Connection error"), mock_client]
            
            # Should return None on error (no retry in current implementation)
            result = await redis_get("test_key")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_to_memory_cache(self):
        """Test graceful degradation to memory cache when Redis unavailable."""
        with patch('app.redis_async.redis_get') as mock_get:
            mock_get.return_value = None  # Redis unavailable
            
            with patch('app.redis_async.memory_cache_get') as mock_memory:
                mock_memory.return_value = {"items": []}
                
                # Should fall back to memory cache
                result = await get_cached_menu_data()
                assert result == {"items": []}
                assert mock_memory.called
    
    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self):
        """Test handling of connection timeouts."""
        with patch('app.redis_async.aioredis.Redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=TimeoutError("Connection timeout"))
            mock_redis.return_value = mock_client
            
            with patch('app.redis_async.settings') as mock_settings:
                mock_settings.REDIS_URL = "redis://localhost:6379/0"
                mock_settings.CELERY_BROKER_URL = None
                
                result = await init_redis()
                assert result is None  # Should handle timeout gracefully


class TestEdgeCasesAndConcurrency:
    """Test edge cases and concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_unicode_data_handling(self):
        """Test handling of Unicode data in cache."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.return_value = mock_client
            
            # Test with Unicode data
            unicode_value = "🍣 Sushi Menu 寿司"
            await redis_set("unicode_key", unicode_value)
            
            # Should encode properly
            mock_client.set.assert_called_with(
                "unicode_key",
                unicode_value.encode('utf-8'),
                ex=DEFAULT_REDIS_CACHE_DURATION
            )
    
    @pytest.mark.asyncio
    async def test_large_data_caching(self):
        """Test caching of large data structures."""
        # Create large menu data
        large_menu = {
            "items": [{"id": str(i), "name": f"Item {i}"} for i in range(1000)],
            "modifiers": [{"id": str(i), "name": f"Modifier {i}"} for i in range(500)]
        }
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await cache_menu_data(large_menu)
            assert result is True
            
            # Verify data was serialized
            complete_call = mock_set.call_args_list[0]
            assert "menu:complete" in complete_call[0]
            assert len(complete_call[0][1]) > 10000  # Should be large JSON string
    
    @pytest.mark.asyncio
    async def test_empty_data_handling(self):
        """Test handling of empty data structures."""
        empty_menu = {"items": [], "modifiers": [], "modifier_groups": [], "variants": []}
        
        with patch('app.redis_async.redis_set') as mock_set:
            mock_set.return_value = True
            
            result = await cache_menu_data(empty_menu)
            assert result is True
            
            # Should still cache empty lists
            assert mock_set.call_count == 5
    
    @pytest.mark.asyncio
    async def test_null_value_handling(self):
        """Test handling of null/None values."""
        with patch('app.redis_async.get_redis') as mock_get_redis:
            mock_get_redis.side_effect = Exception("No Redis")
            
            # Should handle None gracefully
            result = await redis_get("nonexistent")
            assert result is None
    
    def test_concurrent_memory_cache_access(self):
        """Test concurrent access to memory cache."""
        import threading
        import app.redis_async
        
        app.redis_async._memory_cache.clear()
        app.redis_async._memory_cache_timestamps.clear()
        
        results = []
        
        def cache_operation(i):
            memory_cache_set(f"concurrent_{i}", f"value_{i}")
            value = memory_cache_get(f"concurrent_{i}")
            results.append(value == f"value_{i}")
        
        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=cache_operation, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All operations should succeed
        assert all(results)
        assert len([k for k in app.redis_async._memory_cache.keys() if k.startswith("concurrent_")]) == 10


class TestBackwardCompatibility:
    """Test backward compatibility and aliases."""
    
    @pytest.mark.asyncio
    async def test_get_redis_client_alias(self):
        """Test get_redis_client alias for backward compatibility."""
        mock_client = AsyncMock()
        
        with patch('app.redis_async.get_redis') as mock_get:
            mock_get.return_value = mock_client
            
            # Test alias
            from app.redis_async import get_redis_client
            result = await get_redis_client()
            
            assert result == mock_client
            assert mock_get.called