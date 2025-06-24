"""
Unit tests for AI components
Tests AI mixin, caching, and optimization features
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import time

from app.agents.ai_mixin import AIIntelligenceMixin
from app.utils.ai_cache import AIResponseCache, ai_cache
from app.utils.openai_pool import OpenAIConnectionPool, openai_pool
from app.utils.response_cache import ResponseCache


class TestAIMixin:
    """Test the AI intelligence mixin"""
    
    @pytest.fixture
    def ai_agent(self):
        """Create a test agent with AI mixin"""
        class TestAgent(AIIntelligenceMixin):
            def __init__(self):
                super().__init__()
                self.name = "TestAgent"
                self.tools = []
        
        return TestAgent()
    
    @pytest.mark.asyncio
    async def test_ai_mixin_initialization(self, ai_agent):
        """Test AI mixin initializes correctly"""
        assert ai_agent._ai_enabled
        assert ai_agent._model == "gpt-4o-mini"
        assert ai_agent._ai_client is None  # Not initialized until first use
    
    @pytest.mark.asyncio
    async def test_ai_disabled_returns_simple_response(self, ai_agent):
        """Test that disabled AI returns simple response without fallback"""
        ai_agent._ai_enabled = False
        
        response = await ai_agent.process_with_ai(
            "test input",
            {"test": "context"}
        )
        
        assert response["text"] == "AI is not enabled."
        assert response["handled"]
        assert response["agent"] == "TestAgent"
        assert response["actions"] == []
    
    @pytest.mark.asyncio
    async def test_build_messages_optimization(self, ai_agent):
        """Test message building is optimized"""
        context = {
            "customer_name": "John",
            "cart_items": [
                {"name": "California Roll", "quantity": 2},
                {"name": "Spicy Tuna", "quantity": 1}
            ],
            "conversation_history": [
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Response 1"},
                {"role": "user", "content": "Message 2"},
                {"role": "assistant", "content": "Response 2"},
                {"role": "user", "content": "Message 3"},
            ]
        }
        
        messages = ai_agent._build_messages("Current input", context)
        
        # Should have limited messages
        assert len(messages) <= 4  # System + last 2 history + current
        
        # Check system message is consolidated
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1
        
        # Check customer name is included
        assert "John" in system_messages[0]["content"]
    
    @pytest.mark.asyncio
    async def test_fast_response_generation(self, ai_agent):
        """Test fast response generation for common patterns"""
        test_cases = [
            ("GREETING", "Bruce", "Nice to meet you!"),
            ("MAIN_MENU", "I want to order", "Perfect!"),
            ("ORDERING", "that's all", "confirm your order"),
        ]
        
        for state, input_text, expected_phrase in test_cases:
            response = await ai_agent.get_fast_response(
                input_text,
                {"conversation_state": state}
            )
            
            assert expected_phrase.lower() in response.lower()


class TestAICache:
    """Test the AI response caching system"""
    
    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance"""
        return AIResponseCache(ttl=60)
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache):
        """Test cache key generation includes relevant context"""
        key1 = cache._generate_cache_key(
            "Hello", "GREETING", {"customer_name": "John"}
        )
        key2 = cache._generate_cache_key(
            "Hello", "GREETING", {"customer_name": "Jane"}
        )
        key3 = cache._generate_cache_key(
            "hello", "GREETING", {"customer_name": "John"}
        )
        
        # Different names should have different keys
        assert key1 != key2
        
        # Case insensitive input should have same key
        assert key1 == key3
    
    @pytest.mark.asyncio
    async def test_cache_hit_and_miss(self, cache):
        """Test cache hits and misses"""
        response = {
            "text": "Test response",
            "actions": []
        }
        
        # Cache miss
        result = await cache.get("test input", "TEST_STATE", {})
        assert result is None
        
        # Store in cache
        await cache.set("test input", "TEST_STATE", {}, response)
        
        # Cache hit
        result = await cache.get("test input", "TEST_STATE", {})
        assert result is not None
        assert result["text"] == "Test response"
    
    def test_fast_response_patterns(self, cache):
        """Test fast response pattern matching"""
        # Test name patterns in greeting
        response = cache.get_fast_response("Bruce", "GREETING")
        assert response is not None
        assert "Bruce" in response
        assert "Nice to meet you" in response
        
        # Test order patterns
        response = cache.get_fast_response("I want to order", "MAIN_MENU")
        assert response is not None
        assert "order" in response.lower()
        
        # Test completion patterns
        response = cache.get_fast_response("That's all", "ORDERING")
        assert response is not None
        assert "confirm" in response.lower()
    
    @pytest.mark.asyncio
    async def test_cache_size_limit(self, cache):
        """Test cache size limiting"""
        # Fill cache beyond limit
        for i in range(1100):
            await cache.set(
                f"input_{i}",
                "STATE",
                {},
                {"text": f"response_{i}"}
            )
        
        # Cache should be limited
        assert len(cache._cache) <= 1000


class TestOpenAIPool:
    """Test the OpenAI connection pool"""
    
    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test pool initializes with multiple clients"""
        pool = OpenAIConnectionPool()
        await pool.initialize()
        
        assert pool._initialized
        assert len(pool._clients) == 3  # Should have 3 clients
        assert len(pool._warm_tasks) == 3
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_round_robin_client_selection(self):
        """Test clients are selected in round-robin fashion"""
        pool = OpenAIConnectionPool()
        await pool.initialize()
        
        # Get clients multiple times
        clients = []
        for _ in range(6):
            client = await pool.get_client()
            clients.append(client)
        
        # Should cycle through all 3 clients twice
        assert clients[0] is clients[3]
        assert clients[1] is clients[4]
        assert clients[2] is clients[5]
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_pool_warmup_timeout(self):
        """Test pool doesn't wait too long for warmup"""
        pool = OpenAIConnectionPool()
        
        # Mock slow warmup
        async def slow_warmup(*args):
            await asyncio.sleep(10)
        
        with patch.object(pool, '_warm_connection', side_effect=slow_warmup):
            start = time.time()
            await pool.initialize()
            
            # Should not wait for warmup
            client = await pool.get_client()
            duration = time.time() - start
            
            assert duration < 1.0  # Should return immediately
            assert client is not None
        
        await pool.close()


class TestResponseCache:
    """Test the simple response cache"""
    
    def test_response_cache_initialization(self):
        """Test response cache initializes with common responses"""
        cache = ResponseCache()
        
        # Check pre-populated responses
        greeting = cache.get("greeting_initial")
        assert greeting is not None
        assert "Welcome to Red Bar Sushi" in greeting["text"]
        
        order_start = cache.get("acknowledge_order_start")
        assert order_start is not None
        assert "order" in order_start["text"].lower()
    
    def test_pattern_matching(self):
        """Test pattern-based cache retrieval"""
        cache = ResponseCache()
        
        # Test order pattern in main menu
        response = cache.get_for_pattern("I want to order", "MAIN_MENU")
        assert response is not None
        assert "order" in response["text"].lower()
        
        # Test completion pattern in ordering
        response = cache.get_for_pattern("That's all", "ORDERING")
        assert response is not None
        
        # Test no match
        response = cache.get_for_pattern("random text", "UNKNOWN_STATE")
        assert response is None


@pytest.mark.asyncio
async def test_ai_integration():
    """Test AI components work together"""
    # Create agent with AI
    class TestAgent(AIIntelligenceMixin):
        def __init__(self):
            super().__init__()
            self.name = "TestIntegration"
            self.tools = []
            self.instructions = "You are a test agent."
    
    agent = TestAgent()
    
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test AI response"
    mock_response.choices[0].message.tool_calls = None
    
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_client.return_value = mock_instance
        
        # First call - should hit AI
        start = time.time()
        response1 = await agent.process_with_ai(
            "test input",
            {"conversation_state": "TEST"}
        )
        duration1 = time.time() - start
        
        assert response1["text"] == "Test AI response"
        assert response1["ai_generated"]
        
        # Second call - might hit cache
        start = time.time()
        response2 = await agent.process_with_ai(
            "test input",
            {"conversation_state": "TEST"}
        )
        duration2 = time.time() - start
        
        # Cache should make it faster
        assert duration2 <= duration1