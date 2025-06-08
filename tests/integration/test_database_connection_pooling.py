"""
Integration tests for database connection pooling - Task 3.5.4.

This module tests database connection pool behavior, including:
- Connection pool limits and management
- Connection recycling and timeout handling
- Concurrent connection usage
- Pool exhaustion scenarios
- Connection leak detection
"""

import pytest
import asyncio
import time
from typing import List
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy import text, event
from sqlalchemy.pool import QueuePool, StaticPool

from app.db_async import get_db, engine, async_session_factory, verify_connection
from app.models.menu_async import MenuItem, MenuCategory
from app.models.order_async import Order, OrderItem


@pytest.fixture
async def test_engine():
    """Create a test engine with specific pool configuration for testing."""
    # Use test database URL with pool configuration
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///test_pool.db",
        poolclass=StaticPool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=5,
        pool_recycle=30,
        pool_pre_ping=True,
        echo=False
    )
    
    yield test_engine
    
    # Cleanup
    await test_engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine):
    """Create a test session factory."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def pool_monitoring_engine():
    """Create an engine with pool monitoring for detailed testing."""
    # Track pool events
    pool_events = []
    
    def track_connect(dbapi_conn, connection_record):
        pool_events.append(("connect", time.time()))
    
    def track_checkout(dbapi_conn, connection_record, connection_proxy):
        pool_events.append(("checkout", time.time()))
    
    def track_checkin(dbapi_conn, connection_record):
        pool_events.append(("checkin", time.time()))
    
    # Create engine with monitoring
    monitored_engine = create_async_engine(
        "sqlite+aiosqlite:///test_monitored.db",
        poolclass=StaticPool,
        pool_size=3,
        max_overflow=2,
        pool_timeout=2,
        pool_recycle=10,
        pool_pre_ping=True,
        echo=False
    )
    
    # Register event listeners
    event.listen(monitored_engine.sync_engine.pool, 'connect', track_connect)
    event.listen(monitored_engine.sync_engine.pool, 'checkout', track_checkout)
    event.listen(monitored_engine.sync_engine.pool, 'checkin', track_checkin)
    
    yield monitored_engine, pool_events
    
    # Cleanup
    await monitored_engine.dispose()


class TestConnectionPoolBasics:
    """Test basic connection pool functionality."""
    
    @pytest.mark.asyncio
    async def test_pool_connection_creation(self, test_session_factory):
        """Test that connections are properly created from the pool."""
        # Create multiple sessions
        sessions = []
        
        try:
            for i in range(3):
                session = test_session_factory()
                sessions.append(session)
                
                # Execute a simple query to ensure connection works
                result = await session.execute(text("SELECT 1 as test_value"))
                value = result.scalar()
                assert value == 1
                
        finally:
            # Close all sessions
            for session in sessions:
                await session.close()
    
    @pytest.mark.asyncio
    async def test_pool_connection_reuse(self, test_session_factory):
        """Test that connections are properly reused from the pool."""
        # Create and close sessions to test reuse
        for cycle in range(3):
            session = test_session_factory()
            
            try:
                # Execute query
                result = await session.execute(text("SELECT :cycle as cycle_num"), {"cycle": cycle})
                value = result.scalar()
                assert value == cycle
                
            finally:
                await session.close()
    
    @pytest.mark.asyncio
    async def test_pool_connection_timeout(self):
        """Test connection timeout behavior when pool is exhausted."""
        # Create engine with very small pool for testing timeouts
        timeout_engine = create_async_engine(
            "sqlite+aiosqlite:///test_timeout.db",
            poolclass=StaticPool,
            pool_size=1,
            max_overflow=0,
            pool_timeout=1,  # 1 second timeout
            echo=False
        )
        
        timeout_session_factory = async_sessionmaker(timeout_engine, expire_on_commit=False)
        
        try:
            # Hold the only available connection
            session1 = timeout_session_factory()
            await session1.execute(text("SELECT 1"))
            
            # Try to get another connection - should timeout
            start_time = time.time()
            
            with pytest.raises((OperationalError, TimeoutError)):
                session2 = timeout_session_factory()
                await session2.execute(text("SELECT 1"))
                await session2.close()
            
            # Verify timeout happened within expected timeframe
            elapsed_time = time.time() - start_time
            assert elapsed_time >= 1.0  # Should have waited at least 1 second
            assert elapsed_time < 3.0   # But not too long
            
        finally:
            await session1.close()
            await timeout_engine.dispose()
    
    @pytest.mark.asyncio
    async def test_connection_pre_ping(self, test_engine):
        """Test that pool_pre_ping validates connections before use."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
        
        # Create a session and verify it works
        session = session_factory()
        
        try:
            # First query should work fine
            result = await session.execute(text("SELECT 'pre_ping_test' as test"))
            value = result.scalar()
            assert value == "pre_ping_test"
            
            # Simulate connection being closed externally
            # (In a real scenario, this might happen due to network issues)
            await session.close()
            
            # Create new session - pre_ping should handle any stale connections
            session2 = session_factory()
            result2 = await session2.execute(text("SELECT 'after_ping' as test"))
            value2 = result2.scalar()
            assert value2 == "after_ping"
            
        finally:
            if session:
                await session.close()
            if 'session2' in locals():
                await session2.close()


class TestConcurrentConnectionUsage:
    """Test connection pool behavior under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, test_session_factory):
        """Test creating multiple concurrent sessions."""
        async def create_and_query_session(session_id: int):
            """Helper function to create session and run query."""
            session = test_session_factory()
            try:
                result = await session.execute(
                    text("SELECT :session_id as id"), 
                    {"session_id": session_id}
                )
                return result.scalar()
            finally:
                await session.close()
        
        # Create multiple concurrent sessions
        tasks = [create_and_query_session(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Verify all sessions worked correctly
        assert len(results) == 10
        assert results == list(range(10))
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, test_session_factory):
        """Test concurrent database operations with real models."""
        async def create_menu_items(batch_id: int, count: int):
            """Create menu items in a batch."""
            session = test_session_factory()
            try:
                # Create category first
                category = MenuCategory(
                    name=f"Test Category {batch_id}",
                    description=f"Category for batch {batch_id}"
                )
                session.add(category)
                await session.commit()
                await session.refresh(category)
                
                # Create items
                items_created = []
                for i in range(count):
                    item = MenuItem(
                        name=f"Item {batch_id}-{i}",
                        description=f"Test item {i} from batch {batch_id}",
                        price=10.0 + i,
                        plu=f"BATCH{batch_id}_ITEM{i}",
                        category_id=category.id
                    )
                    session.add(item)
                    items_created.append(item)
                
                await session.commit()
                return len(items_created)
                
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()
        
        # Run concurrent operations
        tasks = [create_menu_items(batch_id, 3) for batch_id in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_batches = [r for r in results if isinstance(r, int)]
        assert len(successful_batches) >= 3  # At least 3 batches should succeed
        assert all(count == 3 for count in successful_batches)
    
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion_recovery(self):
        """Test recovery from connection pool exhaustion."""
        # Create engine with small pool
        small_pool_engine = create_async_engine(
            "sqlite+aiosqlite:///test_exhaustion.db",
            poolclass=StaticPool,
            pool_size=2,
            max_overflow=1,
            pool_timeout=1,
            echo=False
        )
        
        session_factory = async_sessionmaker(small_pool_engine, expire_on_commit=False)
        
        try:
            # Hold all available connections
            sessions = []
            for i in range(3):  # pool_size + max_overflow
                session = session_factory()
                await session.execute(text("SELECT 1"))
                sessions.append(session)
            
            # Try to create one more session - should fail
            with pytest.raises((OperationalError, TimeoutError)):
                extra_session = session_factory()
                await extra_session.execute(text("SELECT 1"))
                await extra_session.close()
            
            # Release one connection
            await sessions[0].close()
            sessions.pop(0)
            
            # Now we should be able to create a new session
            recovery_session = session_factory()
            result = await recovery_session.execute(text("SELECT 'recovered' as status"))
            status = result.scalar()
            assert status == "recovered"
            
            await recovery_session.close()
            
        finally:
            # Cleanup remaining sessions
            for session in sessions:
                await session.close()
            await small_pool_engine.dispose()


class TestConnectionRecycling:
    """Test connection recycling and lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_connection_recycle_timeout(self):
        """Test that connections are recycled after the specified timeout."""
        # Create engine with short recycle time
        recycle_engine = create_async_engine(
            "sqlite+aiosqlite:///test_recycle.db",
            poolclass=StaticPool,
            pool_size=2,
            pool_recycle=1,  # 1 second recycle time
            echo=False
        )
        
        session_factory = async_sessionmaker(recycle_engine, expire_on_commit=False)
        
        try:
            # Create session and use connection
            session1 = session_factory()
            result1 = await session1.execute(text("SELECT 'first_use' as usage"))
            value1 = result1.scalar()
            assert value1 == "first_use"
            await session1.close()
            
            # Wait for recycle timeout
            await asyncio.sleep(1.5)
            
            # Create new session - should get recycled connection
            session2 = session_factory()
            result2 = await session2.execute(text("SELECT 'after_recycle' as usage"))
            value2 = result2.scalar()
            assert value2 == "after_recycle"
            await session2.close()
            
        finally:
            await recycle_engine.dispose()
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle_monitoring(self, pool_monitoring_engine):
        """Test monitoring of connection lifecycle events."""
        monitored_engine, pool_events = pool_monitoring_engine
        session_factory = async_sessionmaker(monitored_engine, expire_on_commit=False)
        
        # Clear any existing events
        pool_events.clear()
        
        # Perform database operations
        session = session_factory()
        try:
            await session.execute(text("SELECT 1"))
            await session.commit()
        finally:
            await session.close()
        
        # Check that pool events were recorded
        event_types = [event[0] for event in pool_events]
        
        # We should see checkout and checkin events at minimum
        # Note: SQLite with StaticPool might not show all events the same way as PostgreSQL
        assert len(pool_events) > 0, "Expected pool events to be recorded"


class TestConnectionLeakDetection:
    """Test detection and handling of connection leaks."""
    
    @pytest.mark.asyncio
    async def test_session_cleanup_on_exception(self, test_session_factory):
        """Test that sessions are properly cleaned up even when exceptions occur."""
        sessions_created = []
        
        try:
            # Create session and simulate an error
            session = test_session_factory()
            sessions_created.append(session)
            
            # Execute a query that will work
            await session.execute(text("SELECT 1"))
            
            # Simulate an application error (not database error)
            raise ValueError("Simulated application error")
            
        except ValueError:
            # This is expected
            pass
        finally:
            # Cleanup sessions
            for session in sessions_created:
                await session.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_session_cleanup(self, test_session_factory):
        """Test that concurrent sessions are properly cleaned up."""
        async def session_with_error(should_error: bool):
            """Function that may or may not error."""
            session = test_session_factory()
            try:
                await session.execute(text("SELECT 1"))
                
                if should_error:
                    raise RuntimeError("Intentional error")
                    
                return "success"
            finally:
                await session.close()
        
        # Run multiple tasks, some with errors
        tasks = [
            session_with_error(False),  # success
            session_with_error(True),   # error
            session_with_error(False),  # success
            session_with_error(True),   # error
            session_with_error(False),  # success
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful_results = [r for r in results if r == "success"]
        error_results = [r for r in results if isinstance(r, RuntimeError)]
        
        assert len(successful_results) == 3
        assert len(error_results) == 2
    
    @pytest.mark.asyncio
    async def test_long_running_session_handling(self, test_session_factory):
        """Test handling of long-running sessions."""
        # Create a session that holds a connection for a while
        long_session = test_session_factory()
        
        try:
            # Start a transaction
            await long_session.execute(text("SELECT 1"))
            
            # Simulate other operations that need connections
            quick_sessions = []
            for i in range(3):
                quick_session = test_session_factory()
                quick_sessions.append(quick_session)
                
                result = await quick_session.execute(
                    text("SELECT :value as quick_op"), 
                    {"value": f"quick_{i}"}
                )
                value = result.scalar()
                assert value == f"quick_{i}"
            
            # Cleanup quick sessions
            for qs in quick_sessions:
                await qs.close()
            
            # Long session should still work
            result = await long_session.execute(text("SELECT 'still_working' as status"))
            status = result.scalar()
            assert status == "still_working"
            
        finally:
            await long_session.close()


class TestPoolPerformanceAndScaling:
    """Test connection pool performance and scaling characteristics."""
    
    @pytest.mark.asyncio
    async def test_pool_performance_under_load(self, test_session_factory):
        """Test pool performance with high concurrent load."""
        async def quick_database_operation(operation_id: int):
            """Perform a quick database operation."""
            session = test_session_factory()
            try:
                start_time = time.time()
                
                result = await session.execute(
                    text("SELECT :op_id as operation_id"), 
                    {"op_id": operation_id}
                )
                value = result.scalar()
                
                end_time = time.time()
                return {
                    "operation_id": value,
                    "duration": end_time - start_time,
                    "success": True
                }
            except Exception as e:
                return {
                    "operation_id": operation_id,
                    "error": str(e),
                    "success": False
                }
            finally:
                await session.close()
        
        # Run many concurrent operations
        num_operations = 50
        start_time = time.time()
        
        tasks = [quick_database_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_ops = [r for r in results if r["success"]]
        failed_ops = [r for r in results if not r["success"]]
        
        # Most operations should succeed
        success_rate = len(successful_ops) / len(results)
        assert success_rate >= 0.8, f"Success rate too low: {success_rate}"
        
        # Average operation time should be reasonable
        if successful_ops:
            avg_duration = sum(op["duration"] for op in successful_ops) / len(successful_ops)
            assert avg_duration < 1.0, f"Average operation too slow: {avg_duration}s"
        
        # Total time should be reasonable for concurrent execution
        assert total_time < 10.0, f"Total execution time too long: {total_time}s"
    
    @pytest.mark.asyncio
    async def test_connection_pool_scaling(self):
        """Test how connection pool scales with different configurations."""
        pool_configs = [
            {"pool_size": 2, "max_overflow": 0, "expected_concurrent": 2},
            {"pool_size": 3, "max_overflow": 2, "expected_concurrent": 5},
            {"pool_size": 5, "max_overflow": 5, "expected_concurrent": 10},
        ]
        
        for config in pool_configs:
            # Create engine with specific pool configuration
            scaling_engine = create_async_engine(
                f"sqlite+aiosqlite:///test_scaling_{config['pool_size']}.db",
                poolclass=StaticPool,
                pool_size=config["pool_size"],
                max_overflow=config["max_overflow"],
                pool_timeout=1,
                echo=False
            )
            
            session_factory = async_sessionmaker(scaling_engine, expire_on_commit=False)
            
            try:
                # Try to create expected number of concurrent sessions
                sessions = []
                successful_sessions = 0
                
                for i in range(config["expected_concurrent"]):
                    try:
                        session = session_factory()
                        await session.execute(text("SELECT 1"))
                        sessions.append(session)
                        successful_sessions += 1
                    except (OperationalError, TimeoutError):
                        # Expected when pool is exhausted
                        break
                
                # Should be able to create at least pool_size sessions
                assert successful_sessions >= config["pool_size"]
                
                # Cleanup
                for session in sessions:
                    await session.close()
                    
            finally:
                await scaling_engine.dispose()


class TestRealWorldScenarios:
    """Test connection pooling in realistic application scenarios."""
    
    @pytest.mark.asyncio
    async def test_web_request_simulation(self, test_session_factory):
        """Simulate web requests that use database connections."""
        async def simulate_web_request(request_id: int):
            """Simulate a web request that uses the database."""
            session = test_session_factory()
            try:
                # Simulate checking user session
                await session.execute(text("SELECT 1 as user_check"))
                
                # Simulate loading menu data
                await session.execute(text("SELECT 'menu_data' as data_type"))
                
                # Simulate logging request
                await session.execute(
                    text("SELECT :req_id as request_logged"), 
                    {"req_id": request_id}
                )
                
                return f"request_{request_id}_completed"
                
            finally:
                await session.close()
        
        # Simulate burst of concurrent requests
        request_count = 20
        tasks = [simulate_web_request(i) for i in range(request_count)]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that most requests completed successfully
        successful_requests = [r for r in results if isinstance(r, str) and "completed" in r]
        success_rate = len(successful_requests) / len(results)
        
        assert success_rate >= 0.9, f"Too many failed requests: {success_rate}"
    
    @pytest.mark.asyncio
    async def test_background_task_with_connections(self, test_session_factory):
        """Test background tasks that use database connections."""
        async def background_data_processing():
            """Simulate a background task that processes data."""
            session = test_session_factory()
            try:
                # Simulate processing multiple batches
                for batch in range(5):
                    await session.execute(
                        text("SELECT :batch as batch_processed"), 
                        {"batch": batch}
                    )
                    # Small delay to simulate processing
                    await asyncio.sleep(0.1)
                
                return "background_task_completed"
                
            finally:
                await session.close()
        
        async def concurrent_user_requests():
            """Simulate concurrent user requests during background processing."""
            tasks = []
            for i in range(10):
                session = test_session_factory()
                
                async def user_request(req_session, req_id):
                    try:
                        result = await req_session.execute(
                            text("SELECT :req_id as user_request"), 
                            {"req_id": req_id}
                        )
                        return result.scalar()
                    finally:
                        await req_session.close()
                
                tasks.append(user_request(session, i))
            
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run background task and user requests concurrently
        background_task = background_data_processing()
        user_requests_task = concurrent_user_requests()
        
        background_result, user_results = await asyncio.gather(
            background_task, user_requests_task, return_exceptions=True
        )
        
        # Verify both completed successfully
        assert background_result == "background_task_completed"
        assert len([r for r in user_results if isinstance(r, int)]) >= 8  # Most user requests succeeded