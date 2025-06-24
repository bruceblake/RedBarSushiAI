"""Tests for centralized circuit breaker service."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.circuit_breaker import (
    CircuitState, CircuitBreakerError, ServiceCircuitBreaker, 
    ServiceCircuitBreakers, circuit_breakers
)


class TestServiceCircuitBreaker:
    """Test individual circuit breaker functionality."""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization with default values."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        assert breaker.name == "TestService"
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
    
    def test_successful_call(self):
        """Test successful function call through circuit breaker."""
        breaker = ServiceCircuitBreaker("TestService")
        
        def test_func(x, y):
            return x + y
        
        result = breaker.call(test_func, 2, 3)
        assert result == 5
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
    
    def test_circuit_opens_after_failures(self):
        """Test circuit opens after reaching failure threshold."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=3
        )
        
        def failing_func():
            raise Exception("Test failure")
        
        # First 3 failures should be allowed
        for i in range(3):
            with pytest.raises(Exception, match="Test failure"):
                breaker.call(failing_func)
        
        # Circuit should now be open
        assert breaker.state == CircuitState.OPEN
        assert breaker._failure_count == 3
        
        # Next call should fail immediately with CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_async_call_success(self):
        """Test successful async function call through circuit breaker."""
        breaker = ServiceCircuitBreaker("TestService")
        
        async def async_func(x, y):
            await asyncio.sleep(0.01)
            return x * y
        
        result = await breaker.async_call(async_func, 4, 5)
        assert result == 20
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_async_call_failure(self):
        """Test async function failure handling."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=2
        )
        
        async def failing_async_func():
            raise Exception("Async failure")
        
        # Test failures
        for i in range(2):
            with pytest.raises(Exception, match="Async failure"):
                await breaker.async_call(failing_async_func)
        
        # Circuit should be open
        assert breaker.state == CircuitState.OPEN
        
        # Next call should fail with CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await breaker.async_call(failing_async_func)
    
    def test_circuit_recovery_timeout(self):
        """Test circuit transitions to half-open after recovery timeout."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=1,
            recovery_timeout=1  # 1 second for quick testing
        )
        
        def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        
        # Mock time passing
        with patch('app.services.circuit_breaker.datetime') as mock_datetime:
            # Set current time to past recovery timeout
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            
            # Circuit should transition to HALF_OPEN
            assert breaker.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_on_half_open_success(self):
        """Test circuit closes when call succeeds in half-open state."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=1,
            recovery_timeout=0  # Immediate recovery for testing
        )
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1/0)
        
        # Force to HALF_OPEN state
        breaker._state = CircuitState.HALF_OPEN
        
        # Successful call should close circuit
        def success_func():
            return "success"
        
        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
    
    def test_circuit_reopens_on_half_open_failure(self):
        """Test circuit reopens when call fails in half-open state."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=1
        )
        
        # Force to HALF_OPEN state
        breaker._state = CircuitState.HALF_OPEN
        
        # Failed call should reopen circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1/0)
        
        assert breaker.state == CircuitState.OPEN
    
    def test_event_listeners(self):
        """Test circuit breaker event listeners."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=1
        )
        
        # Track events
        events = []
        
        def on_open(cb, exception):
            events.append(("open", cb.name, str(exception)))
        
        def on_close(cb):
            events.append(("close", cb.name))
        
        breaker.add_listener(on_open=on_open, on_close=on_close)
        
        # Open circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1/0)
        
        assert len(events) == 1
        assert events[0][0] == "open"
        assert events[0][1] == "TestService"
        assert "division by zero" in events[0][2]
        
        # Force to HALF_OPEN and close
        breaker._state = CircuitState.HALF_OPEN
        breaker.call(lambda: "success")
        
        assert len(events) == 2
        assert events[1] == ("close", "TestService")
    
    def test_get_stats(self):
        """Test circuit breaker statistics."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=3
        )
        
        # Initial stats
        stats = breaker.get_stats()
        assert stats["name"] == "TestService"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        
        # After success
        breaker.call(lambda: "ok")
        stats = breaker.get_stats()
        assert stats["success_count"] == 1
        
        # After failure
        try:
            breaker.call(lambda: 1/0)
        except:
            pass
        
        stats = breaker.get_stats()
        assert stats["failure_count"] == 1
        assert stats["last_failure"] is not None
    
    def test_manual_reset(self):
        """Test manual circuit reset."""
        breaker = ServiceCircuitBreaker(
            name="TestService",
            failure_threshold=1
        )
        
        # Open circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1/0)
        
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0


class TestServiceCircuitBreakers:
    """Test centralized circuit breaker management."""
    
    def test_initialization(self):
        """Test ServiceCircuitBreakers initialization."""
        breakers = ServiceCircuitBreakers()
        
        assert hasattr(breakers, 'openai')
        assert hasattr(breakers, 'twilio')
        assert hasattr(breakers, 'deliverect')
        
        assert breakers.openai.name == "OpenAI"
        assert breakers.twilio.name == "Twilio"
        assert breakers.deliverect.name == "Deliverect"
    
    @pytest.mark.asyncio
    async def test_openai_circuit_breaker(self):
        """Test OpenAI circuit breaker integration."""
        breakers = ServiceCircuitBreakers()
        
        # Mock OpenAI call
        async def mock_openai_call():
            return {"choices": [{"message": {"content": "Test response"}}]}
        
        result = await breakers.openai.async_call(mock_openai_call)
        assert result["choices"][0]["message"]["content"] == "Test response"
    
    def test_get_all_stats(self):
        """Test getting statistics for all circuit breakers."""
        breakers = ServiceCircuitBreakers()
        
        stats = breakers.get_all_stats()
        
        assert "openai" in stats
        assert "twilio" in stats
        assert "deliverect" in stats
        assert "summary" in stats
        
        # Initially all should be healthy
        assert stats["summary"]["healthy_services"] == 3
        assert stats["summary"]["degraded_services"] == 0
        assert stats["summary"]["failed_services"] == 0
    
    @patch('app.tasks.notifications.send_circuit_breaker_alert')
    def test_circuit_open_alert(self, mock_alert):
        """Test alert is sent when circuit opens."""
        breakers = ServiceCircuitBreakers()
        mock_alert.delay = MagicMock()
        
        # Force circuit to open
        breakers.openai._failure_count = 4
        breakers.openai._state = CircuitState.CLOSED
        
        # Trigger failure to open circuit
        try:
            breakers.openai.call(lambda: 1/0)
        except:
            pass
        
        # Alert should be sent
        mock_alert.delay.assert_called_once()
        call_args = mock_alert.delay.call_args[1]
        assert call_args["service_name"] == "OpenAI"
        assert "division by zero" in call_args["error"]
    
    def test_global_instance(self):
        """Test global circuit_breakers instance."""
        from app.services.circuit_breaker import circuit_breakers
        
        assert isinstance(circuit_breakers, ServiceCircuitBreakers)
        assert hasattr(circuit_breakers, 'openai')
        assert hasattr(circuit_breakers, 'twilio')
        assert hasattr(circuit_breakers, 'deliverect')


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with services."""
    
    @pytest.mark.asyncio
    async def test_ai_mixin_with_circuit_breaker(self):
        """Test AI mixin using circuit breaker for OpenAI calls."""
        from app.agents.ai_mixin import AIIntelligenceMixin
        
        class TestAgent(AIIntelligenceMixin):
            def __init__(self):
                super().__init__()
                self.name = "TestAgent"
        
        agent = TestAgent()
        
        # Mock OpenAI client
        mock_client = AsyncMock()
        agent._ai_client = mock_client
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test AI response"
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test successful call
        result = await agent.process_with_ai(
            "Test input",
            {"conversation_state": "TEST"}
        )
        
        assert result["text"] == "Test AI response"
        assert result["agent"] == "TestAgent"
    
    @pytest.mark.asyncio
    async def test_deliverect_service_with_circuit_breaker(self):
        """Test Deliverect service using circuit breaker."""
        from app.services.deliverect_service import DeliverectService
        from app.models.order_async import Order
        
        service = DeliverectService()
        
        # Create mock order
        order = MagicMock(spec=Order)
        order.id = "123"
        order.order_type = "pickup"
        order.customer_name = "Test Customer"
        order.customer_phone = "+1234567890"
        order.items = []
        
        # Mock database session
        mock_db = AsyncMock()
        
        # Mock successful API call
        with patch.object(service, '_make_api_call') as mock_api_call:
            mock_api_call.return_value = (True, {"id": "DLVR-123"}, 201)
            
            result = await service.submit_order(order, mock_db)
            
            assert result["success"] is True
            assert result["deliverect_order_id"] == "DLVR-123"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascading_failures(self):
        """Test circuit breaker prevents cascading failures."""
        from app.services.circuit_breaker import circuit_breakers
        
        # Reset circuit breakers
        circuit_breakers.openai.reset()
        
        # Simulate multiple failures
        async def failing_openai_call():
            raise Exception("OpenAI API error")
        
        # First few failures go through
        for i in range(5):  # Assuming threshold is 5
            with pytest.raises(Exception, match="OpenAI API error"):
                await circuit_breakers.openai.async_call(failing_openai_call)
        
        # Circuit should be open, preventing further calls
        with pytest.raises(CircuitBreakerError):
            await circuit_breakers.openai.async_call(failing_openai_call)
        
        # Verify circuit is open
        stats = circuit_breakers.openai.get_stats()
        assert stats["state"] == "open"
        assert stats["failure_count"] == 5