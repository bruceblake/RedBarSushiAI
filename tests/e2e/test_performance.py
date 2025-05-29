"""
Performance and load tests for the voice ordering system.
Tests system behavior under various load conditions.
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import httpx
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher


@pytest.mark.slow
class TestPerformanceBaseline:
    """Test baseline performance metrics."""
    
    @pytest.mark.asyncio
    async def test_agent_response_time(self, orchestrator):
        """Test individual agent response times."""
        call_sid = "PERF_AGENT_TEST"
        
        # Warm up
        await orchestrator.process_voice_input(call_sid, "Hello", {})
        
        # Measure response times
        response_times = []
        
        test_inputs = [
            "My name is John",
            "What's on your menu?",
            "I want two California rolls",
            "That's all",
            "Yes, confirm the order"
        ]
        
        for input_text in test_inputs:
            start = time.time()
            response = await orchestrator.process_voice_input(
                call_sid, input_text, {}
            )
            duration = time.time() - start
            response_times.append(duration)
            
            assert response["handled"] is True
        
        # Performance assertions
        avg_time = statistics.mean(response_times)
        max_time = max(response_times)
        
        assert avg_time < 0.5  # Average under 500ms
        assert max_time < 1.0  # Max under 1 second
    
    @pytest.mark.asyncio
    async def test_menu_matching_performance(self, db_session):
        """Test menu matching speed with cache."""
        matcher = AsyncCachedMenuMatcher(db_session)
        
        # Test items
        test_queries = [
            "California roll",
            "cali roll",
            "california",
            "spicy tuna",
            "spicy tuna roll",
            "edamame",
            "green soybeans",
            "dragon roll",
            "rainbow roll",
            "salmon sashimi"
        ]
        
        # Warm up cache
        for query in test_queries[:3]:
            await matcher.match_menu_item(query)
        
        # Measure performance
        match_times = []
        
        for query in test_queries:
            start = time.time()
            result = await matcher.match_menu_item(query)
            duration = time.time() - start
            match_times.append(duration)
        
        # Performance assertions
        avg_match_time = statistics.mean(match_times)
        cached_times = match_times[0:3]  # Should be cached
        uncached_times = match_times[3:]
        
        assert avg_match_time < 0.1  # Average under 100ms
        assert statistics.mean(cached_times) < 0.01  # Cached under 10ms
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self, db_session):
        """Test database query performance."""
        from app.models.menu_async import MenuItem
        from sqlalchemy import select
        
        queries = [
            # Simple queries
            select(MenuItem).limit(10),
            select(MenuItem).where(MenuItem.is_available == True),
            select(MenuItem).where(MenuItem.plu == "PLU_CALI_001"),
            
            # Complex queries with joins
            select(MenuItem).join(MenuItem.modifier_groups).distinct(),
        ]
        
        query_times = []
        
        for query in queries:
            start = time.time()
            result = await db_session.execute(query)
            _ = result.scalars().all()
            duration = time.time() - start
            query_times.append(duration)
        
        # All queries should be fast
        assert all(t < 0.05 for t in query_times)  # Under 50ms


@pytest.mark.slow
class TestConcurrentLoad:
    """Test system under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_conversations(self, orchestrator):
        """Test handling multiple concurrent conversations."""
        num_conversations = 10
        call_sids = [f"CONCURRENT_{i}" for i in range(num_conversations)]
        
        async def process_conversation(call_sid):
            """Simulate a conversation."""
            responses = []
            start = time.time()
            
            # Greeting
            r1 = await orchestrator.process_voice_input(
                call_sid, "Hello, my name is User", {}
            )
            responses.append(r1)
            
            # Order
            r2 = await orchestrator.process_voice_input(
                call_sid, "I want a California roll", {}
            )
            responses.append(r2)
            
            # Complete
            r3 = await orchestrator.process_voice_input(
                call_sid, "That's all", {}
            )
            responses.append(r3)
            
            duration = time.time() - start
            return duration, all(r["handled"] for r in responses)
        
        # Run conversations concurrently
        start_time = time.time()
        tasks = [process_conversation(sid) for sid in call_sids]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        durations = [r[0] for r in results]
        successes = [r[1] for r in results]
        
        assert all(successes)  # All conversations succeeded
        assert total_time < 5.0  # All complete within 5 seconds
        assert statistics.mean(durations) < 2.0  # Average conversation under 2s
    
    @pytest.mark.asyncio
    async def test_concurrent_menu_queries(self, db_session):
        """Test concurrent menu database queries."""
        from app.models.menu_async import MenuItem
        from sqlalchemy import select
        
        async def query_menu_items():
            """Perform multiple menu queries."""
            queries = [
                select(MenuItem).where(MenuItem.is_available == True),
                select(MenuItem).where(MenuItem.category_id == 1),
                select(MenuItem).order_by(MenuItem.price)
            ]
            
            start = time.time()
            for query in queries:
                result = await db_session.execute(query)
                _ = result.scalars().all()
            return time.time() - start
        
        # Run concurrent query sessions
        tasks = [query_menu_items() for _ in range(20)]
        durations = await asyncio.gather(*tasks)
        
        # Performance assertions
        assert statistics.mean(durations) < 0.2  # Average under 200ms
        assert max(durations) < 0.5  # Max under 500ms
    
    @pytest.mark.asyncio
    async def test_redis_concurrent_operations(self, redis_client):
        """Test Redis under concurrent load."""
        num_operations = 100
        
        async def redis_operations(index):
            """Perform various Redis operations."""
            key_prefix = f"perf_test_{index}"
            
            # Set operations
            await redis_client.set(f"{key_prefix}_data", "test_value")
            
            # Get operations
            await redis_client.get(f"{key_prefix}_data")
            
            # Hash operations
            await redis_client.hset(f"{key_prefix}_hash", "field1", "value1")
            await redis_client.hget(f"{key_prefix}_hash", "field1")
            
            # Cleanup
            await redis_client.delete(f"{key_prefix}_data", f"{key_prefix}_hash")
        
        start = time.time()
        tasks = [redis_operations(i) for i in range(num_operations)]
        await asyncio.gather(*tasks)
        duration = time.time() - start
        
        # Should handle 100 operations quickly
        assert duration < 2.0  # Under 2 seconds
        ops_per_second = num_operations / duration
        assert ops_per_second > 50  # At least 50 ops/second


@pytest.mark.slow
class TestMemoryUsage:
    """Test memory usage under load."""
    
    @pytest.mark.asyncio
    async def test_long_running_conversation(self, orchestrator):
        """Test memory usage during long conversation."""
        call_sid = "LONG_CONV_MEM_TEST"
        
        # Simulate 100 conversation turns
        for i in range(100):
            response = await orchestrator.process_voice_input(
                call_sid,
                f"Test message number {i}",
                {}
            )
            assert response["handled"] is True
            
            # Check if context is growing unbounded
            fsm = await orchestrator.get_fsm(call_sid)
            context_size = len(str(fsm.context))
            
            # Context should not grow indefinitely
            assert context_size < 10000  # Under 10KB
    
    @pytest.mark.asyncio
    async def test_cache_memory_limits(self, redis_client):
        """Test cache doesn't grow unbounded."""
        # Add many cache entries
        for i in range(1000):
            key = f"cache_test_{i}"
            value = f"value_{i}" * 100  # ~500 bytes each
            await redis_client.set(key, value, ex=60)  # 1 minute TTL
        
        # Check memory usage (would need Redis INFO command)
        # This is a placeholder - real implementation would check Redis memory
        
        # Cleanup
        keys = [f"cache_test_{i}" for i in range(1000)]
        if keys:
            await redis_client.delete(*keys)


@pytest.mark.slow
@pytest.mark.staging
class TestRealWorldScenarios:
    """Test realistic usage patterns."""
    
    @pytest.mark.asyncio
    async def test_lunch_rush_simulation(self, orchestrator):
        """Simulate lunch rush with many orders."""
        # Simulate 20 orders in rapid succession
        order_times = []
        
        async def place_order(index):
            call_sid = f"LUNCH_RUSH_{index}"
            start = time.time()
            
            # Quick order flow
            await orchestrator.process_voice_input(
                call_sid, f"Hi, I'm Customer {index}", {}
            )
            
            await orchestrator.process_voice_input(
                call_sid, "Two California rolls and one spicy tuna", {}
            )
            
            await orchestrator.process_voice_input(
                call_sid, "That's it", {}
            )
            
            await orchestrator.process_voice_input(
                call_sid, "Pickup please", {}
            )
            
            return time.time() - start
        
        # Process orders with some concurrency
        start_time = time.time()
        
        # Batch in groups of 5
        for batch in range(4):
            batch_tasks = [
                place_order(batch * 5 + i) 
                for i in range(5)
            ]
            batch_times = await asyncio.gather(*batch_tasks)
            order_times.extend(batch_times)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # Performance metrics
        avg_order_time = statistics.mean(order_times)
        orders_per_minute = (20 / total_time) * 60
        
        assert avg_order_time < 3.0  # Each order under 3 seconds
        assert orders_per_minute > 20  # Can handle 20+ orders/minute
    
    @pytest.mark.asyncio
    async def test_network_latency_impact(self, staging_url):
        """Test impact of network latency on performance."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            latencies = []
            
            for _ in range(10):
                start = time.time()
                response = await client.get(f"{staging_url}/health")
                latency = time.time() - start
                latencies.append(latency)
                
                assert response.status_code == 200
            
            avg_latency = statistics.mean(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            
            # Reasonable latency expectations
            assert avg_latency < 0.5  # Average under 500ms
            assert p95_latency < 1.0  # 95th percentile under 1s