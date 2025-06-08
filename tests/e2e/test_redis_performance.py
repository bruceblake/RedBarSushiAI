"""
Redis performance and caching tests for the Red Bar Sushi AI system.
Tests Redis operations and caching mechanisms.
"""
import asyncio
import time
import pytest
import redis.asyncio as redis
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import json

# Redis connection for testing
redis_client = None

@pytest.fixture(scope="module")
async def setup_redis():
    """Setup Redis connection for testing."""
    global redis_client
    redis_client = redis.from_url("redis://localhost:6380/0", decode_responses=True)
    
    # Test connection
    try:
        await redis_client.ping()
        print("Redis connection successful")
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    
    yield redis_client
    
    # Cleanup
    await redis_client.close()

class TestRedisPerformance:
    """Performance tests for Redis operations."""
    
    @pytest.mark.asyncio
    async def test_redis_basic_operations(self, setup_redis):
        """Test basic Redis operations performance."""
        redis_conn = setup_redis
        
        # Test SET operations
        start_time = time.time()
        for i in range(100):
            await redis_conn.set(f"test_key_{i}", f"test_value_{i}")
        set_time = time.time() - start_time
        
        # Test GET operations
        start_time = time.time()
        for i in range(100):
            value = await redis_conn.get(f"test_key_{i}")
            assert value == f"test_value_{i}"
        get_time = time.time() - start_time
        
        # Test DELETE operations
        start_time = time.time()
        for i in range(100):
            await redis_conn.delete(f"test_key_{i}")
        delete_time = time.time() - start_time
        
        print(f"Redis SET 100 keys: {set_time:.3f}s ({100/set_time:.1f} ops/sec)")
        print(f"Redis GET 100 keys: {get_time:.3f}s ({100/get_time:.1f} ops/sec)")
        print(f"Redis DELETE 100 keys: {delete_time:.3f}s ({100/delete_time:.1f} ops/sec)")
        
        # Performance assertions
        assert set_time < 1.0, f"SET operations too slow: {set_time:.3f}s"
        assert get_time < 0.5, f"GET operations too slow: {get_time:.3f}s"
        assert delete_time < 0.5, f"DELETE operations too slow: {delete_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_redis_json_operations(self, setup_redis):
        """Test Redis JSON storage and retrieval performance."""
        redis_conn = setup_redis
        
        # Create test data
        test_data = {
            "menu_item": {
                "id": 123,
                "name": "California Roll",
                "price": 12.99,
                "category": "Rolls",
                "modifiers": [
                    {"name": "Extra Avocado", "price": 2.00},
                    {"name": "No Cucumber", "price": 0.00}
                ],
                "properties": {
                    "allergens": ["shellfish", "sesame"],
                    "spice_level": "mild"
                }
            }
        }
        
        # Test JSON SET operations
        start_time = time.time()
        for i in range(50):
            test_data["menu_item"]["id"] = i
            await redis_conn.set(f"menu_item_{i}", json.dumps(test_data))
        json_set_time = time.time() - start_time
        
        # Test JSON GET operations
        start_time = time.time()
        for i in range(50):
            data_str = await redis_conn.get(f"menu_item_{i}")
            data = json.loads(data_str)
            assert data["menu_item"]["id"] == i
        json_get_time = time.time() - start_time
        
        print(f"Redis JSON SET 50 objects: {json_set_time:.3f}s ({50/json_set_time:.1f} ops/sec)")
        print(f"Redis JSON GET 50 objects: {json_get_time:.3f}s ({50/json_get_time:.1f} ops/sec)")
        
        # Performance assertions
        assert json_set_time < 2.0, f"JSON SET operations too slow: {json_set_time:.3f}s"
        assert json_get_time < 1.0, f"JSON GET operations too slow: {json_get_time:.3f}s"
        
        # Cleanup
        for i in range(50):
            await redis_conn.delete(f"menu_item_{i}")
    
    @pytest.mark.asyncio
    async def test_redis_hash_operations(self, setup_redis):
        """Test Redis hash operations performance."""
        redis_conn = setup_redis
        
        # Test HSET operations
        start_time = time.time()
        for i in range(25):
            hash_data = {
                "name": f"Item_{i}",
                "price": str(10.99 + i),
                "category": "Test Category",
                "description": f"Test item number {i}"
            }
            await redis_conn.hset(f"hash_item_{i}", mapping=hash_data)
        hash_set_time = time.time() - start_time
        
        # Test HGETALL operations
        start_time = time.time()
        for i in range(25):
            data = await redis_conn.hgetall(f"hash_item_{i}")
            assert data["name"] == f"Item_{i}"
        hash_get_time = time.time() - start_time
        
        print(f"Redis HSET 25 hashes: {hash_set_time:.3f}s ({25/hash_set_time:.1f} ops/sec)")
        print(f"Redis HGETALL 25 hashes: {hash_get_time:.3f}s ({25/hash_get_time:.1f} ops/sec)")
        
        # Performance assertions
        assert hash_set_time < 1.0, f"HSET operations too slow: {hash_set_time:.3f}s"
        assert hash_get_time < 0.5, f"HGETALL operations too slow: {hash_get_time:.3f}s"
        
        # Cleanup
        for i in range(25):
            await redis_conn.delete(f"hash_item_{i}")
    
    @pytest.mark.asyncio
    async def test_redis_expiration_performance(self, setup_redis):
        """Test Redis key expiration performance."""
        redis_conn = setup_redis
        
        # Set keys with expiration
        start_time = time.time()
        for i in range(20):
            await redis_conn.setex(f"expiring_key_{i}", 60, f"value_{i}")
        setex_time = time.time() - start_time
        
        # Check TTL
        start_time = time.time()
        for i in range(20):
            ttl = await redis_conn.ttl(f"expiring_key_{i}")
            assert ttl > 0, f"Key {i} should have TTL > 0, got {ttl}"
        ttl_time = time.time() - start_time
        
        print(f"Redis SETEX 20 keys: {setex_time:.3f}s ({20/setex_time:.1f} ops/sec)")
        print(f"Redis TTL 20 keys: {ttl_time:.3f}s ({20/ttl_time:.1f} ops/sec)")
        
        # Performance assertions
        assert setex_time < 1.0, f"SETEX operations too slow: {setex_time:.3f}s"
        assert ttl_time < 0.5, f"TTL operations too slow: {ttl_time:.3f}s"
        
        # Cleanup
        for i in range(20):
            await redis_conn.delete(f"expiring_key_{i}")
    
    @pytest.mark.asyncio
    async def test_redis_pipeline_performance(self, setup_redis):
        """Test Redis pipeline performance for batch operations."""
        redis_conn = setup_redis
        
        # Individual operations
        start_time = time.time()
        for i in range(100):
            await redis_conn.set(f"individual_{i}", f"value_{i}")
        individual_time = time.time() - start_time
        
        # Pipeline operations
        start_time = time.time()
        pipe = redis_conn.pipeline()
        for i in range(100):
            pipe.set(f"pipeline_{i}", f"value_{i}")
        await pipe.execute()
        pipeline_time = time.time() - start_time
        
        print(f"Redis individual SET 100 keys: {individual_time:.3f}s ({100/individual_time:.1f} ops/sec)")
        print(f"Redis pipeline SET 100 keys: {pipeline_time:.3f}s ({100/pipeline_time:.1f} ops/sec)")
        print(f"Pipeline speedup: {individual_time/pipeline_time:.1f}x faster")
        
        # Pipeline should be significantly faster
        assert pipeline_time < individual_time, f"Pipeline should be faster than individual operations"
        assert pipeline_time < 0.5, f"Pipeline operations too slow: {pipeline_time:.3f}s"
        
        # Cleanup
        pipe = redis_conn.pipeline()
        for i in range(100):
            pipe.delete(f"individual_{i}")
            pipe.delete(f"pipeline_{i}")
        await pipe.execute()
    
    @pytest.mark.asyncio
    async def test_redis_memory_usage(self, setup_redis):
        """Test Redis memory usage with different data types."""
        redis_conn = setup_redis
        
        # Get initial memory usage
        initial_info = await redis_conn.info("memory")
        initial_memory = initial_info["used_memory"]
        
        # Store different types of data
        large_string = "x" * 1000  # 1KB string
        large_json = json.dumps({"data": ["item"] * 100})  # Complex JSON
        
        # Add data
        for i in range(100):
            await redis_conn.set(f"string_{i}", large_string)
            await redis_conn.set(f"json_{i}", large_json)
        
        # Get memory usage after adding data
        after_info = await redis_conn.info("memory")
        after_memory = after_info["used_memory"]
        
        memory_increase = after_memory - initial_memory
        memory_per_key = memory_increase / 200  # 100 string + 100 json keys
        
        print(f"Initial memory: {initial_memory:,} bytes")
        print(f"After adding 200 keys: {after_memory:,} bytes")
        print(f"Memory increase: {memory_increase:,} bytes")
        print(f"Memory per key: {memory_per_key:.1f} bytes")
        
        # Cleanup and verify memory is released
        pipe = redis_conn.pipeline()
        for i in range(100):
            pipe.delete(f"string_{i}")
            pipe.delete(f"json_{i}")
        await pipe.execute()
        
        # Check memory after cleanup
        cleanup_info = await redis_conn.info("memory")
        cleanup_memory = cleanup_info["used_memory"]
        
        print(f"After cleanup: {cleanup_memory:,} bytes")
        
        # Memory should be reasonably efficient
        assert memory_per_key < 2000, f"Memory usage too high: {memory_per_key:.1f} bytes per key"