"""
Integration tests for AI-powered voice flow
Tests the complete system with real AI calls
"""
import pytest
import asyncio
from typing import Dict, Any
import json

from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.cart_async import AsyncCartAgent


@pytest.fixture
async def orchestrator():
    """Initialize orchestrator for tests"""
    await async_agent_orchestrator.initialize()
    return async_agent_orchestrator


@pytest.fixture
def call_sid():
    """Generate unique call SID for each test"""
    import time
    return f"TEST_{int(time.time())}"


class TestAIVoiceFlow:
    """Test complete AI voice flow"""
    
    @pytest.mark.asyncio
    async def test_initial_greeting_is_fast(self, orchestrator, call_sid):
        """Test that initial greeting returns instantly without AI"""
        import time
        
        start = time.time()
        response = await orchestrator.process_voice_input(
            call_sid, 
            "", 
            {"first_interaction": True}
        )
        duration = time.time() - start
        
        assert duration < 0.1, f"Initial greeting too slow: {duration:.2f}s"
        assert "Welcome to Red Bar Sushi" in response["text"]
        assert response["agent"] == "FrontlineVoiceAI"
        assert not response.get("ai_generated", True)  # Should not use AI
    
    @pytest.mark.asyncio
    async def test_name_recognition_with_ai(self, orchestrator, call_sid):
        """Test that name recognition uses AI and updates context"""
        # First interaction
        await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        )
        
        # Provide name
        response = await orchestrator.process_voice_input(call_sid, "Bruce")
        
        assert response["handled"]
        assert "Bruce" in response["text"] or "nice to meet you" in response["text"].lower()
        
        # Check if name was set in context
        fsm = await orchestrator._get_fsm(call_sid)
        context = fsm.get_context()
        
        # Name should be detected
        assert context.get("customer_name") == "Bruce" or any(
            action.get("type") == "set_customer_name" and action.get("name") == "Bruce"
            for action in response.get("actions", [])
        )
    
    @pytest.mark.asyncio
    async def test_cart_agent_uses_ai(self, orchestrator, call_sid):
        """Test that cart agent uses AI for processing orders"""
        # Setup: greeting and name
        await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        )
        await orchestrator.process_voice_input(call_sid, "John")
        await orchestrator.process_voice_input(call_sid, "I want to order")
        
        # Order an item
        response = await orchestrator.process_voice_input(
            call_sid, "Two california rolls"
        )
        
        assert response["agent"] == "Cart"
        assert response["handled"]
        # Should not be the fallback pattern
        assert not response["text"].startswith("[Cart] Processed:")
        assert response.get("ai_generated") or response.get("from_cache")
    
    @pytest.mark.asyncio
    async def test_complete_order_flow(self, orchestrator, call_sid):
        """Test complete order flow from greeting to confirmation"""
        responses = []
        
        # 1. Greeting
        resp = await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        )
        responses.append(("greeting", resp))
        assert resp["handled"]
        
        # 2. Name
        resp = await orchestrator.process_voice_input(call_sid, "Sarah")
        responses.append(("name", resp))
        assert resp["handled"]
        
        # 3. Start order
        resp = await orchestrator.process_voice_input(call_sid, "I'd like to order")
        responses.append(("start_order", resp))
        assert resp["handled"]
        
        # 4. Add items
        resp = await orchestrator.process_voice_input(call_sid, "Two spicy tuna rolls")
        responses.append(("add_item1", resp))
        assert resp["handled"]
        
        resp = await orchestrator.process_voice_input(call_sid, "Add one california roll")
        responses.append(("add_item2", resp))
        assert resp["handled"]
        
        # 5. Complete order
        resp = await orchestrator.process_voice_input(call_sid, "That's all")
        responses.append(("complete", resp))
        assert resp["handled"]
        
        # Verify flow completed properly
        fsm = await orchestrator._get_fsm(call_sid)
        final_state = fsm.current_state.value
        
        # Should have progressed beyond ORDERING
        assert final_state in ["VALIDATION", "CONFIRMATION", "FULFILLMENT"]
        
        # Log all responses for debugging
        for step, resp in responses:
            print(f"\n{step}: {resp['text'][:100]}...")
    
    @pytest.mark.asyncio
    async def test_ai_caching_works(self, orchestrator):
        """Test that AI responses are cached and reused"""
        # First call - should use AI
        call_sid1 = "TEST_CACHE_1"
        await orchestrator.process_voice_input(
            call_sid1, "", {"first_interaction": True}
        )
        
        response1 = await orchestrator.process_voice_input(call_sid1, "Mike")
        
        # Second call with same input - should use cache
        call_sid2 = "TEST_CACHE_2"
        await orchestrator.process_voice_input(
            call_sid2, "", {"first_interaction": True}
        )
        
        import time
        start = time.time()
        response2 = await orchestrator.process_voice_input(call_sid2, "Mike")
        duration = time.time() - start
        
        # Cached response should be very fast
        assert duration < 0.5, f"Cached response too slow: {duration:.2f}s"
        
        # Both should handle the name properly
        assert response1["handled"] and response2["handled"]
    
    @pytest.mark.asyncio
    async def test_no_fallback_patterns(self, orchestrator, call_sid):
        """Ensure no hardcoded fallback patterns are used"""
        # Test various inputs that might trigger fallbacks
        test_cases = [
            ("", {"first_interaction": True}),
            ("Jennifer"),
            ("I want to order food"),
            ("Add three dragon rolls"),
            ("That's everything"),
        ]
        
        for input_text, context in test_cases:
            if isinstance(context, dict):
                response = await orchestrator.process_voice_input(
                    call_sid, input_text, context
                )
            else:
                response = await orchestrator.process_voice_input(
                    call_sid, input_text
                )
            
            # Check for fallback patterns
            text = response["text"]
            
            # Should not contain fallback patterns
            assert not text.startswith("[")  # No [Agent] prefixes
            assert "Processed:" not in text
            assert "technical difficulties" not in text or input_text == ""  # Only for actual errors
            
            # Should be handled
            assert response["handled"]


class TestAgentAICapabilities:
    """Test individual agent AI capabilities"""
    
    @pytest.mark.asyncio
    async def test_frontline_agent_has_ai(self):
        """Test that frontline agent has AI capabilities"""
        agent = AsyncFrontlineVoiceAgentAI()
        
        # Check AI mixin
        assert hasattr(agent, 'process_with_ai')
        assert hasattr(agent, '_ai_enabled')
        assert agent._ai_enabled
        
        # Test AI processing
        response = await agent.process_with_ai(
            "Hello, my name is David",
            {"conversation_state": "GREETING"}
        )
        
        assert response["handled"]
        assert response.get("ai_generated") or response.get("from_cache")
    
    @pytest.mark.asyncio
    async def test_cart_agent_has_ai(self):
        """Test that cart agent has AI capabilities"""
        agent = AsyncCartAgent()
        
        # Check AI mixin
        assert hasattr(agent, 'process_with_ai')
        assert hasattr(agent, '_ai_enabled')
        assert agent._ai_enabled
        
        # Set call context
        agent.set_current_call("TEST_CART_AI")
        
        # Test AI processing
        response = await agent.process_input(
            "I want two california rolls",
            {"call_sid": "TEST_CART_AI"}
        )
        
        assert response["handled"]
        assert not response["text"].startswith("[Cart] Processed:")


@pytest.mark.asyncio
async def test_performance_targets():
    """Test that response times meet performance targets"""
    await async_agent_orchestrator.initialize()
    
    # Allow warmup
    await asyncio.sleep(1)
    
    import time
    call_sid = f"PERF_{int(time.time())}"
    
    # Test each interaction type
    tests = [
        ("greeting", "", {"first_interaction": True}, 0.1),
        ("name", "Robert", None, 2.0),
        ("order_start", "I want to order", None, 2.0),
        ("add_item", "One rainbow roll", None, 2.0),
    ]
    
    for test_name, input_text, context, target in tests:
        start = time.time()
        response = await async_agent_orchestrator.process_voice_input(
            call_sid, input_text, context
        )
        duration = time.time() - start
        
        print(f"{test_name}: {duration:.2f}s (target: {target}s)")
        
        # Allow some tolerance
        assert duration < target * 2, f"{test_name} too slow: {duration:.2f}s > {target * 2}s"