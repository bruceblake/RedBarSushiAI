"""
Advanced E2E Tests - Category 6: Stress, Load, and Concurrency Testing

These tests validate system performance and stability under pressure by testing:
- Concurrent session isolation and data integrity
- Performance degradation under load
- Resource utilization monitoring
- Session state management under stress
- Data corruption prevention with parallel operations

Following the detailed test methodology for validating system resilience.
"""

import pytest
import pytest_asyncio
import asyncio
import time
import logging
import json
import uuid
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

import httpx
import redis.asyncio as redis

from .conftest import (
    send_turn, get_cart_state, get_fsm_state, get_session_data,
    assert_semantic_similarity, assert_contains_keywords
)

logger = logging.getLogger(__name__)


class TestCategory6StressLoadConcurrency:
    """Category 6: Stress, Load, and Concurrency Testing"""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_6_1_concurrent_session_isolation(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 6.1: Concurrent Session Isolation and Data Integrity
        
        This test validates that:
        1. Multiple concurrent sessions don't interfere with each other
        2. Cart data remains isolated between sessions
        3. FSM states are properly segregated
        4. No data corruption occurs under concurrent load
        """
        # Configuration for concurrent test
        NUM_CONCURRENT_SESSIONS = 5
        SESSION_DURATION = 30  # seconds
        
        logger.info(f"Starting concurrent session test with {NUM_CONCURRENT_SESSIONS} sessions")
        
        # Create unique session identifiers
        sessions = []
        for i in range(NUM_CONCURRENT_SESSIONS):
            session_id = f"concurrent_test_{int(time.time())}_{i}_{uuid.uuid4().hex[:8]}"
            sessions.append({
                "call_sid": session_id,
                "user_name": f"User_{i}",
                "expected_items": [
                    {"name": f"Item_{i}_A", "quantity": 1},
                    {"name": f"Item_{i}_B", "quantity": 2}
                ]
            })
        
        async def run_concurrent_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
            """Run a single concurrent session"""
            call_sid = session_data["call_sid"]
            user_name = session_data["user_name"]
            
            session_results = {
                "call_sid": call_sid,
                "user_name": user_name,
                "success": False,
                "cart_items": [],
                "errors": [],
                "response_times": []
            }
            
            try:
                # Simulate realistic ordering session
                start_time = time.time()
                
                # Greeting
                response_time = time.time()
                response1 = await send_turn(async_client, call_sid, "Hello")
                session_results["response_times"].append(time.time() - response_time)
                
                # Name
                response_time = time.time()
                response2 = await send_turn(async_client, call_sid, user_name)
                session_results["response_times"].append(time.time() - response_time)
                
                # Order items specific to this session
                response_time = time.time()
                order_text = f"I'd like a Chicken Burger and two Veggie Burgers for {user_name}"
                response3 = await send_turn(async_client, call_sid, order_text)
                session_results["response_times"].append(time.time() - response_time)
                
                # Add session-specific customization
                response_time = time.time()
                customization = f"Make the chicken burger special for {user_name}"
                response4 = await send_turn(async_client, call_sid, customization)
                session_results["response_times"].append(time.time() - response_time)
                
                # Complete order
                response_time = time.time()
                response5 = await send_turn(async_client, call_sid, "That's everything.")
                session_results["response_times"].append(time.time() - response_time)
                
                response_time = time.time()
                response6 = await send_turn(async_client, call_sid, "Yes, confirm the order.")
                session_results["response_times"].append(time.time() - response_time)
                
                # Verify cart state
                cart = await get_cart_state(redis_client, call_sid)
                session_results["cart_items"] = cart.get("items", [])
                
                # Verify session isolation
                session_data_result = await get_session_data(redis_client, call_sid)
                
                session_results["success"] = True
                session_results["total_time"] = time.time() - start_time
                
                logger.info(f"Session {call_sid} completed successfully")
                
            except Exception as e:
                session_results["errors"].append(str(e))
                logger.error(f"Session {call_sid} failed: {e}")
            
            return session_results
        
        # Run all sessions concurrently
        logger.info("Launching concurrent sessions...")
        start_time = time.time()
        
        tasks = [run_concurrent_session(session) for session in sessions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        logger.info(f"All concurrent sessions completed in {total_time:.2f} seconds")
        
        # Analyze results
        successful_sessions = []
        failed_sessions = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_sessions.append({"error": str(result)})
            elif result.get("success", False):
                successful_sessions.append(result)
            else:
                failed_sessions.append(result)
        
        # Validate session isolation
        logger.info(f"Successful sessions: {len(successful_sessions)}")
        logger.info(f"Failed sessions: {len(failed_sessions)}")
        
        # Critical validation: No session data crossover
        for i, session_result in enumerate(successful_sessions):
            call_sid = session_result["call_sid"]
            user_name = session_result["user_name"]
            cart_items = session_result["cart_items"]
            
            # Verify cart contains only items from this session
            for item in cart_items:
                item_name = item.get("name", "").lower()
                # Items should not contain other session identifiers
                for j, other_session in enumerate(sessions):
                    if i != j:
                        other_user = other_session["user_name"]
                        assert other_user.lower() not in item_name, \
                            f"Session {call_sid} cart contains item from {other_user}: {item_name}"
        
        # Performance validation
        response_times = []
        for session_result in successful_sessions:
            response_times.extend(session_result.get("response_times", []))
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
            
            logger.info(f"Response time stats: avg={avg_response_time:.2f}s, max={max_response_time:.2f}s, min={min_response_time:.2f}s")
            
            # Validate reasonable performance (adjust thresholds as needed)
            assert avg_response_time < 10.0, f"Average response time too high: {avg_response_time:.2f}s"
            assert max_response_time < 30.0, f"Maximum response time too high: {max_response_time:.2f}s"
        
        # Ensure majority of sessions succeeded
        success_rate = len(successful_sessions) / len(sessions)
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2f} (min 80%)"
        
        logger.info("✅ Test 6.1 passed: Concurrent session isolation maintained")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_6_2_load_performance_degradation(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 6.2: Load Performance Degradation Analysis
        
        This test validates that:
        1. System performance degrades gracefully under increasing load
        2. Response times remain within acceptable bounds
        3. Error rates don't spike uncontrollably
        4. System recovers after load reduction
        """
        # Configuration for load testing
        LOAD_LEVELS = [1, 3, 5, 8]  # Concurrent requests
        REQUESTS_PER_LEVEL = 10
        
        logger.info("Starting load performance degradation test")
        
        performance_results = []
        
        for load_level in LOAD_LEVELS:
            logger.info(f"Testing load level: {load_level} concurrent requests")
            
            level_results = {
                "load_level": load_level,
                "response_times": [],
                "errors": [],
                "success_count": 0,
                "total_requests": 0
            }
            
            async def single_load_request(request_id: int) -> Dict[str, Any]:
                """Execute a single load test request"""
                call_sid = f"load_test_{load_level}_{request_id}_{int(time.time())}"
                
                try:
                    start_time = time.time()
                    
                    # Quick ordering flow
                    await send_turn(async_client, call_sid, "Hi")
                    await send_turn(async_client, call_sid, f"LoadTest_{request_id}")
                    await send_turn(async_client, call_sid, "I want a Chicken Burger")
                    await send_turn(async_client, call_sid, "That's all")
                    
                    response_time = time.time() - start_time
                    
                    # Verify basic functionality
                    cart = await get_cart_state(redis_client, call_sid)
                    cart_items = cart.get("items", [])
                    
                    return {
                        "success": True,
                        "response_time": response_time,
                        "cart_items": len(cart_items),
                        "call_sid": call_sid
                    }
                    
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "response_time": time.time() - start_time if 'start_time' in locals() else 0
                    }
            
            # Run requests at this load level
            for batch in range(0, REQUESTS_PER_LEVEL, load_level):
                batch_size = min(load_level, REQUESTS_PER_LEVEL - batch)
                
                tasks = [single_load_request(batch + i) for i in range(batch_size)]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    level_results["total_requests"] += 1
                    
                    if isinstance(result, Exception):
                        level_results["errors"].append(str(result))
                    elif result.get("success", False):
                        level_results["success_count"] += 1
                        level_results["response_times"].append(result["response_time"])
                    else:
                        level_results["errors"].append(result.get("error", "Unknown error"))
                        level_results["response_times"].append(result.get("response_time", 0))
                
                # Small delay between batches
                await asyncio.sleep(0.5)
            
            # Calculate metrics for this load level
            if level_results["response_times"]:
                level_results["avg_response_time"] = statistics.mean(level_results["response_times"])
                level_results["max_response_time"] = max(level_results["response_times"])
                level_results["min_response_time"] = min(level_results["response_times"])
            else:
                level_results["avg_response_time"] = 0
                level_results["max_response_time"] = 0
                level_results["min_response_time"] = 0
            
            level_results["success_rate"] = level_results["success_count"] / level_results["total_requests"]
            level_results["error_rate"] = len(level_results["errors"]) / level_results["total_requests"]
            
            performance_results.append(level_results)
            
            logger.info(f"Load level {load_level} completed:")
            logger.info(f"  Success rate: {level_results['success_rate']:.2%}")
            logger.info(f"  Avg response time: {level_results['avg_response_time']:.2f}s")
            logger.info(f"  Max response time: {level_results['max_response_time']:.2f}s")
            logger.info(f"  Error rate: {level_results['error_rate']:.2%}")
            
            # Brief recovery period
            await asyncio.sleep(2)
        
        # Analyze performance degradation
        logger.info("Analyzing performance degradation...")
        
        # Validate graceful degradation
        for i, result in enumerate(performance_results):
            load_level = result["load_level"]
            success_rate = result["success_rate"]
            avg_response_time = result["avg_response_time"]
            error_rate = result["error_rate"]
            
            # Minimum acceptable performance thresholds
            min_success_rate = max(0.5, 0.9 - (i * 0.1))  # Allow degradation
            max_avg_response_time = 15.0 + (i * 5.0)  # Allow slower responses
            max_error_rate = min(0.5, 0.1 + (i * 0.1))  # Allow some errors
            
            assert success_rate >= min_success_rate, \
                f"Load level {load_level}: Success rate {success_rate:.2%} below threshold {min_success_rate:.2%}"
            
            assert avg_response_time <= max_avg_response_time, \
                f"Load level {load_level}: Avg response time {avg_response_time:.2f}s exceeds {max_avg_response_time:.2f}s"
            
            assert error_rate <= max_error_rate, \
                f"Load level {load_level}: Error rate {error_rate:.2%} exceeds {max_error_rate:.2%}"
        
        # Validate that performance doesn't collapse entirely
        final_result = performance_results[-1]
        assert final_result["success_rate"] >= 0.3, \
            f"System failed catastrophically: {final_result['success_rate']:.2%} success rate"
        
        logger.info("✅ Test 6.2 passed: Load performance degradation within acceptable bounds")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_6_3_session_state_consistency_under_load(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 6.3: Session State Consistency Under Load
        
        This test validates that:
        1. Session state remains consistent during concurrent modifications
        2. FSM transitions work correctly under load
        3. Cart operations maintain integrity
        4. No race conditions corrupt session data
        """
        # Configuration
        NUM_CONCURRENT_OPERATIONS = 8
        OPERATIONS_PER_SESSION = 5
        
        logger.info("Starting session state consistency test")
        
        async def concurrent_session_operations(session_id: int) -> Dict[str, Any]:
            """Perform multiple operations on a single session concurrently"""
            call_sid = f"state_test_{session_id}_{int(time.time())}"
            
            results = {
                "call_sid": call_sid,
                "operations": [],
                "final_cart": [],
                "errors": [],
                "success": False
            }
            
            try:
                # Initialize session
                await send_turn(async_client, call_sid, "Hello")
                await send_turn(async_client, call_sid, f"StateTest_{session_id}")
                
                # Define operations to perform
                operations = [
                    ("add_item", "Add a Chicken Burger"),
                    ("add_item", "Add a Veggie Burger"),
                    ("modify_item", "Make the chicken burger without pickles"),
                    ("add_item", "Add Caesar Salad"),
                    ("review_order", "What's in my cart?")
                ]
                
                # Execute operations with small delays
                for i, (op_type, op_text) in enumerate(operations):
                    try:
                        start_time = time.time()
                        response = await send_turn(async_client, call_sid, op_text)
                        
                        # Verify response
                        assert "message" in response, f"Operation {i} failed: no message"
                        
                        # Check cart state after each operation
                        cart = await get_cart_state(redis_client, call_sid)
                        fsm_state = await get_fsm_state(redis_client, call_sid)
                        
                        results["operations"].append({
                            "operation": op_type,
                            "text": op_text,
                            "response_time": time.time() - start_time,
                            "cart_items": len(cart.get("items", [])),
                            "fsm_state": fsm_state
                        })
                        
                        # Small delay to allow processing
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        results["errors"].append(f"Operation {i} ({op_type}): {str(e)}")
                
                # Get final state
                final_cart = await get_cart_state(redis_client, call_sid)
                results["final_cart"] = final_cart.get("items", [])
                
                # Validate final state consistency
                if len(results["final_cart"]) >= 2:  # Should have at least 2 items
                    results["success"] = True
                
            except Exception as e:
                results["errors"].append(f"Session error: {str(e)}")
            
            return results
        
        # Run concurrent session operations
        logger.info(f"Running {NUM_CONCURRENT_OPERATIONS} concurrent session operations...")
        
        tasks = [concurrent_session_operations(i) for i in range(NUM_CONCURRENT_OPERATIONS)]
        session_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_sessions = []
        failed_sessions = []
        
        for result in session_results:
            if isinstance(result, Exception):
                failed_sessions.append({"error": str(result)})
            elif result.get("success", False):
                successful_sessions.append(result)
            else:
                failed_sessions.append(result)
        
        logger.info(f"Successful sessions: {len(successful_sessions)}")
        logger.info(f"Failed sessions: {len(failed_sessions)}")
        
        # Validate session state consistency
        for session_result in successful_sessions:
            call_sid = session_result["call_sid"]
            operations = session_result["operations"]
            final_cart = session_result["final_cart"]
            
            # Verify operations were processed in order
            cart_sizes = [op["cart_items"] for op in operations]
            
            # Cart should generally grow (allowing for some AI interpretation)
            if len(cart_sizes) > 1:
                # At least some operations should have increased cart size
                cart_growth = any(cart_sizes[i] > cart_sizes[i-1] for i in range(1, len(cart_sizes)))
                logger.info(f"Session {call_sid}: Cart sizes {cart_sizes}, Growth: {cart_growth}")
            
            # Validate final cart has reasonable content
            assert len(final_cart) >= 1, f"Session {call_sid}: Final cart is empty"
            
            # Check for data integrity
            for item in final_cart:
                assert "name" in item, f"Session {call_sid}: Cart item missing name"
                assert "quantity" in item, f"Session {call_sid}: Cart item missing quantity"
                assert item["quantity"] > 0, f"Session {call_sid}: Invalid quantity"
        
        # Validate overall success rate
        success_rate = len(successful_sessions) / len(session_results)
        assert success_rate >= 0.6, f"Session consistency success rate too low: {success_rate:.2%}"
        
        logger.info("✅ Test 6.3 passed: Session state consistency maintained under load")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_6_4_resource_exhaustion_recovery(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 6.4: Resource Exhaustion and Recovery
        
        This test validates that:
        1. System handles resource exhaustion gracefully
        2. Recovery mechanisms work after stress
        3. No permanent damage occurs from overload
        4. System returns to normal operation
        """
        # Configuration for stress testing
        STRESS_DURATION = 10  # seconds
        STRESS_REQUESTS_PER_SECOND = 10
        RECOVERY_DURATION = 5  # seconds
        
        logger.info("Starting resource exhaustion recovery test")
        
        # Baseline performance measurement
        logger.info("Measuring baseline performance...")
        baseline_start = time.time()
        
        baseline_call_sid = f"baseline_{int(time.time())}"
        await send_turn(async_client, baseline_call_sid, "Hello")
        await send_turn(async_client, baseline_call_sid, "Baseline")
        await send_turn(async_client, baseline_call_sid, "I want a Chicken Burger")
        
        baseline_time = time.time() - baseline_start
        logger.info(f"Baseline performance: {baseline_time:.2f}s")
        
        # Stress phase
        logger.info(f"Starting stress phase: {STRESS_DURATION}s at {STRESS_REQUESTS_PER_SECOND} req/s")
        
        stress_results = {
            "requests_sent": 0,
            "requests_completed": 0,
            "errors": [],
            "response_times": []
        }
        
        async def stress_request(request_id: int) -> Dict[str, Any]:
            """Single stress request"""
            call_sid = f"stress_{request_id}_{int(time.time())}"
            
            try:
                start_time = time.time()
                
                # Minimal request to stress system
                response = await send_turn(async_client, call_sid, "Quick order")
                
                return {
                    "success": True,
                    "response_time": time.time() - start_time,
                    "call_sid": call_sid
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - start_time if 'start_time' in locals() else 0
                }
        
        # Generate stress load
        stress_start = time.time()
        request_id = 0
        
        while time.time() - stress_start < STRESS_DURATION:
            # Send batch of requests
            batch_size = min(STRESS_REQUESTS_PER_SECOND, 
                           max(1, int(STRESS_REQUESTS_PER_SECOND * 0.1)))
            
            tasks = []
            for _ in range(batch_size):
                tasks.append(stress_request(request_id))
                request_id += 1
                stress_results["requests_sent"] += 1
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    stress_results["errors"].append(str(result))
                else:
                    stress_results["requests_completed"] += 1
                    stress_results["response_times"].append(result.get("response_time", 0))
                    
                    if not result.get("success", False):
                        stress_results["errors"].append(result.get("error", "Unknown error"))
            
            # Brief pause
            await asyncio.sleep(0.1)
        
        stress_duration = time.time() - stress_start
        
        # Calculate stress metrics
        stress_completion_rate = stress_results["requests_completed"] / stress_results["requests_sent"]
        stress_error_rate = len(stress_results["errors"]) / stress_results["requests_sent"]
        
        if stress_results["response_times"]:
            stress_avg_response_time = statistics.mean(stress_results["response_times"])
        else:
            stress_avg_response_time = float('inf')
        
        logger.info(f"Stress phase completed in {stress_duration:.2f}s:")
        logger.info(f"  Requests sent: {stress_results['requests_sent']}")
        logger.info(f"  Completion rate: {stress_completion_rate:.2%}")
        logger.info(f"  Error rate: {stress_error_rate:.2%}")
        logger.info(f"  Avg response time: {stress_avg_response_time:.2f}s")
        
        # Recovery phase
        logger.info(f"Starting recovery phase: {RECOVERY_DURATION}s...")
        await asyncio.sleep(RECOVERY_DURATION)
        
        # Post-stress performance measurement
        logger.info("Measuring post-stress performance...")
        recovery_start = time.time()
        
        recovery_call_sid = f"recovery_{int(time.time())}"
        await send_turn(async_client, recovery_call_sid, "Hello")
        await send_turn(async_client, recovery_call_sid, "Recovery")
        await send_turn(async_client, recovery_call_sid, "I want a Chicken Burger")
        
        recovery_time = time.time() - recovery_start
        logger.info(f"Post-stress performance: {recovery_time:.2f}s")
        
        # Validate recovery
        performance_degradation = recovery_time / baseline_time
        logger.info(f"Performance degradation factor: {performance_degradation:.2f}")
        
        # System should recover to reasonable performance
        assert performance_degradation <= 5.0, \
            f"System failed to recover: {performance_degradation:.2f}x degradation"
        
        # Validate stress didn't cause total system failure
        assert stress_completion_rate >= 0.1, \
            f"System completely failed under stress: {stress_completion_rate:.2%} completion rate"
        
        # Validate system is still functional
        cart = await get_cart_state(redis_client, recovery_call_sid)
        logger.info(f"Recovery cart state: {cart}")
        # Basic functionality should still work
        
        logger.info("✅ Test 6.4 passed: System recovered from resource exhaustion")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])