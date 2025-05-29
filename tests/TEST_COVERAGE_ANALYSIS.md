# RedBarSushiAI Test Coverage Analysis and Recommendations

## Current Test Suite Overview

### Unit Tests (`tests/unit/`)
✅ **Good Coverage:**
- Agent base functionality
- Individual agent logic (Frontline, Menu, Cart, Guardrail, Fulfillment, Escalation)
- FSM core functionality
- Intent detection
- Menu matching

❌ **Missing Coverage:**
- Database models (menu_async.py, order_async.py, location_async.py)
- Utility functions (text_normalization.py, json_utils.py, helpers_async.py)
- Redis operations (redis_async.py)
- Conversation store components
- Audio processing utilities
- Deliverect client utilities
- Configuration loading

### Integration Tests (`tests/integration/`)
✅ **Good Coverage:**
- Agent orchestration with FSM
- ConversationRelay webhook processing
- Database operations
- FSM orchestration

❌ **Missing Coverage:**
- Redis caching integration
- Menu syncing from Deliverect
- Order submission to Deliverect
- Celery task integration
- WebSocket connection management
- Multi-agent handoffs
- Error recovery scenarios

### E2E Tests (`tests/e2e/`)
✅ **Good Coverage:**
- Complete ordering flow
- ConversationRelay FSM integration
- Voice flow scenarios
- WebSocket resilience
- Menu system integration
- Agent SDK testing

❌ **Missing Coverage:**
- Real Twilio webhook testing (staging)
- Real OpenAI Realtime API testing (staging)
- Real Deliverect order submission (staging)
- Performance testing under load
- Concurrent call handling
- Long conversation handling
- Network interruption recovery

## Recommended Test Additions

### 1. Critical Unit Tests to Add

```python
# tests/unit/test_models.py
"""Unit tests for database models."""

import pytest
from app.models.menu_async import MenuItem, MenuModifier, MenuNameVariant
from app.models.order_async import Order, OrderItem

class TestMenuModels:
    def test_menu_item_plu_validation(self):
        """Test PLU is required and unique."""
        pass
    
    def test_price_in_cents_conversion(self):
        """Test price storage and retrieval."""
        pass
    
    def test_availability_with_snooze(self):
        """Test snooze functionality."""
        pass

class TestOrderModels:
    def test_order_total_calculation(self):
        """Test order total with modifiers."""
        pass
    
    def test_deliverect_id_generation(self):
        """Test unique order ID generation."""
        pass
```

```python
# tests/unit/test_redis_operations.py
"""Unit tests for Redis operations."""

import pytest
from unittest.mock import AsyncMock, patch
from app.redis_async import RedisClient

class TestRedisOperations:
    @pytest.mark.asyncio
    async def test_cart_storage_retrieval(self):
        """Test cart CRUD in Redis."""
        pass
    
    @pytest.mark.asyncio
    async def test_fsm_state_persistence(self):
        """Test FSM state storage."""
        pass
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test TTL on cached data."""
        pass
```

```python
# tests/unit/test_utils.py
"""Unit tests for utility functions."""

import pytest
from app.utils.text_normalization import normalize_menu_item_name
from app.utils.helpers_async import parse_quantity_from_text

class TestTextNormalization:
    def test_menu_name_normalization(self):
        """Test name normalization for matching."""
        test_cases = [
            ("California Roll", "california roll"),
            ("Spicy-Tuna", "spicy tuna"),
            ("Salmon (3pcs)", "salmon 3pcs")
        ]
        pass

class TestHelpers:
    def test_quantity_parsing(self):
        """Test parsing quantities from natural language."""
        test_cases = [
            ("three rolls", 3),
            ("a couple of items", 2),
            ("half dozen", 6)
        ]
        pass
```

### 2. Critical Integration Tests to Add

```python
# tests/integration/test_redis_caching.py
"""Integration tests for Redis caching with database."""

import pytest
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher

class TestRedisCaching:
    @pytest.mark.asyncio
    async def test_menu_cache_invalidation(self, db_session, redis_client):
        """Test cache invalidation on menu updates."""
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, redis_client):
        """Test multiple concurrent cache operations."""
        pass
```

```python
# tests/integration/test_deliverect_integration.py
"""Integration tests for Deliverect with mocked API."""

import pytest
from unittest.mock import patch, AsyncMock

class TestDeliverectIntegration:
    @pytest.mark.asyncio
    async def test_menu_webhook_processing(self, client):
        """Test processing Deliverect menu webhook."""
        pass
    
    @pytest.mark.asyncio
    async def test_order_submission_retry(self):
        """Test order submission with retries."""
        pass
```

```python
# tests/integration/test_websocket_audio.py
"""Integration tests for WebSocket audio processing."""

import pytest
import websockets
from app.api.voice.websocket import websocket_handler

class TestWebSocketAudio:
    @pytest.mark.asyncio
    async def test_audio_packet_processing(self):
        """Test processing Twilio audio packets."""
        pass
    
    @pytest.mark.asyncio
    async def test_openai_connection_handling(self):
        """Test OpenAI WebSocket connection."""
        pass
```

### 3. Critical E2E Tests for Staging

```python
# tests/e2e/test_staging_integrations.py
"""E2E tests that require staging environment."""

import pytest
import os

@pytest.mark.skipif(os.getenv("FASTAPI_ENV") != "staging", reason="Staging only")
class TestStagingIntegrations:
    
    @pytest.mark.asyncio
    async def test_real_twilio_webhook(self, staging_phone_number):
        """Test with real Twilio test credentials."""
        # Use Twilio test phone numbers
        # Verify TwiML generation
        # Test media stream connection
        pass
    
    @pytest.mark.asyncio
    async def test_real_openai_conversation(self, openai_staging_key):
        """Test with real OpenAI API."""
        # Use cheaper model (gpt-3.5-turbo)
        # Test intent detection
        # Test conversation flow
        pass
    
    @pytest.mark.asyncio
    async def test_real_deliverect_order(self, deliverect_sandbox):
        """Test with Deliverect sandbox."""
        # Submit test order
        # Verify order status
        # Check webhook callbacks
        pass
```

```python
# tests/e2e/test_performance.py
"""Performance and load tests for staging."""

import pytest
import asyncio
import time

@pytest.mark.slow
@pytest.mark.staging
class TestPerformance:
    
    @pytest.mark.asyncio
    async def test_concurrent_calls(self, orchestrator):
        """Test handling multiple concurrent calls."""
        call_sids = [f"PERF_TEST_{i}" for i in range(10)]
        
        # Create concurrent conversations
        tasks = []
        for call_sid in call_sids:
            task = orchestrator.process_voice_input(
                call_sid, "I want to order", {}
            )
            tasks.append(task)
        
        start = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start
        
        assert all(r["handled"] for r in results)
        assert duration < 5.0  # Should handle 10 calls in under 5 seconds
    
    @pytest.mark.asyncio
    async def test_long_conversation(self, orchestrator):
        """Test conversation with many interactions."""
        call_sid = "LONG_CONV_TEST"
        
        # Simulate 50+ turns
        for i in range(50):
            response = await orchestrator.process_voice_input(
                call_sid,
                f"Test message {i}",
                {}
            )
            assert response["handled"] is True
```

```python
# tests/e2e/test_error_recovery.py
"""E2E tests for error recovery scenarios."""

import pytest
from unittest.mock import patch

class TestErrorRecovery:
    
    @pytest.mark.asyncio
    async def test_openai_api_timeout_recovery(self, orchestrator):
        """Test recovery from OpenAI API timeouts."""
        pass
    
    @pytest.mark.asyncio
    async def test_database_connection_loss(self, orchestrator):
        """Test recovery from database disconnection."""
        pass
    
    @pytest.mark.asyncio
    async def test_redis_connection_loss(self, orchestrator):
        """Test recovery from Redis disconnection."""
        pass
    
    @pytest.mark.asyncio
    async def test_deliverect_api_failure(self, orchestrator):
        """Test graceful handling of Deliverect failures."""
        pass
```

### 4. Staging-Specific Test Configuration

```python
# tests/e2e/conftest.py
"""E2E test configuration for staging environment."""

import pytest
import os

@pytest.fixture
def staging_config():
    """Get staging-specific configuration."""
    if os.getenv("FASTAPI_ENV") != "staging":
        pytest.skip("Staging environment required")
    
    return {
        "twilio_test_number": os.getenv("TWILIO_TEST_PHONE_NUMBER"),
        "openai_test_model": "gpt-3.5-turbo",
        "deliverect_sandbox_url": os.getenv("DELIVERECT_SANDBOX_URL"),
        "test_timeout": 30  # Longer timeouts for real services
    }

@pytest.fixture
async def real_twilio_client(staging_config):
    """Create real Twilio client for staging."""
    from twilio.rest import Client
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )

@pytest.fixture
async def real_openai_client(staging_config):
    """Create real OpenAI client for staging."""
    import openai
    return openai.AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
```

## Test Execution Strategy

### Development Environment
```bash
# Run all unit and integration tests
pytest tests/unit tests/integration -v

# Run with coverage
pytest tests/unit tests/integration --cov=app --cov-report=html

# Run specific test categories
pytest -m "not e2e" -v
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Run Unit Tests
  run: pytest tests/unit -v --tb=short

- name: Run Integration Tests
  run: pytest tests/integration -v

- name: Check Coverage
  run: pytest tests/unit tests/integration --cov=app --cov-fail-under=80
```

### Staging Environment
```bash
# Set environment
export FASTAPI_ENV=staging

# Run all tests including E2E
pytest -v

# Run only E2E tests
pytest tests/e2e -v -s

# Run performance tests
pytest tests/e2e/test_performance.py -v --durations=10

# Run with real services
pytest tests/e2e/test_staging_integrations.py -v
```

## Coverage Goals

### Target Coverage by Category:
- **Unit Tests**: 85% coverage of business logic
- **Integration Tests**: 70% coverage of component interactions
- **E2E Tests**: Cover all critical user paths

### Priority Areas for Testing:
1. **Order Processing Pipeline**: End-to-end validation
2. **Menu Matching Logic**: Edge cases and variants
3. **FSM State Transitions**: All possible paths
4. **Error Recovery**: Network, API, and database failures
5. **Concurrent Operations**: Multiple simultaneous calls
6. **Audio Processing**: Streaming and buffering

## Monitoring Test Health

### Key Metrics to Track:
1. Test execution time trends
2. Flaky test identification
3. Coverage regression alerts
4. Staging vs production parity
5. API mock accuracy

### Test Maintenance:
1. Weekly review of failing tests
2. Monthly update of test data
3. Quarterly review of test strategy
4. Continuous addition of regression tests