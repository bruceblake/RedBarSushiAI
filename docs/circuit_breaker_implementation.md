# Circuit Breaker Implementation

## Overview

This document describes the centralized circuit breaker implementation for RedBarSushiAI, designed to improve system resilience when dealing with external service failures.

## Architecture

### Core Components

1. **ServiceCircuitBreaker** (`app/services/circuit_breaker.py`)
   - Individual circuit breaker for a single service
   - Tracks failures and manages state transitions
   - Supports both sync and async function calls

2. **ServiceCircuitBreakers** (Centralized Management)
   - Manages circuit breakers for all external services
   - Provides global access through `circuit_breakers` instance
   - Handles event notifications and alerts

3. **Circuit States**
   - **CLOSED**: Normal operation, requests pass through
   - **OPEN**: Service failing, requests rejected immediately
   - **HALF_OPEN**: Testing recovery, limited requests allowed

### Protected Services

1. **OpenAI API**
   - Failure threshold: 5
   - Recovery timeout: 60 seconds
   - Used by all AI agents

2. **Twilio API**
   - Failure threshold: 3
   - Recovery timeout: 30 seconds
   - Used for voice communication

3. **Deliverect API**
   - Failure threshold: 5
   - Recovery timeout: 300 seconds (5 minutes)
   - Used for POS integration

## Usage

### Basic Usage

```python
from app.services.circuit_breaker import circuit_breakers, CircuitBreakerError

# Sync call
try:
    result = circuit_breakers.openai.call(
        some_function,
        arg1, arg2
    )
except CircuitBreakerError:
    # Handle circuit open scenario
    return fallback_response()

# Async call
try:
    result = await circuit_breakers.openai.async_call(
        some_async_function,
        arg1, arg2
    )
except CircuitBreakerError:
    # Handle circuit open scenario
    return await async_fallback_response()
```

### Integration Examples

#### AI Mixin Integration

```python
# In app/agents/ai_mixin.py
try:
    response = await circuit_breakers.openai.async_call(
        client.chat.completions.create,
        **params
    )
except CircuitBreakerError:
    logger.warning("OpenAI circuit breaker open")
    return self._get_circuit_breaker_fallback(input_text, context)
```

#### Deliverect Service Integration

```python
# In app/services/deliverect_service.py
try:
    success, response_data, status_code = await circuit_breakers.deliverect.async_call(
        self._make_api_call,
        deliverect_payload,
        db
    )
except CircuitBreakerError:
    return {
        "success": False,
        "error": "POS system temporarily unavailable",
        "needs_manual_intervention": True
    }
```

## Configuration

Circuit breaker parameters can be configured through environment variables:

```bash
# OpenAI Circuit Breaker
CIRCUIT_BREAKER_OPENAI_FAIL_MAX=5
CIRCUIT_BREAKER_OPENAI_RESET_TIMEOUT=60

# Twilio Circuit Breaker
CIRCUIT_BREAKER_TWILIO_FAIL_MAX=3
CIRCUIT_BREAKER_TWILIO_RESET_TIMEOUT=30

# Deliverect Circuit Breaker
CIRCUIT_BREAKER_DELIVERECT_FAIL_MAX=5
CIRCUIT_BREAKER_DELIVERECT_RESET_TIMEOUT=300
```

## Monitoring

### Getting Statistics

```python
# Individual service stats
stats = circuit_breakers.openai.get_stats()
# Returns: {
#     "name": "OpenAI",
#     "state": "closed",
#     "failure_count": 0,
#     "success_count": 150,
#     "failure_threshold": 5,
#     "recovery_timeout": 60,
#     "last_failure": None,
#     "last_success": "2024-01-15T10:30:00"
# }

# All services summary
all_stats = circuit_breakers.get_all_stats()
# Returns stats for all services plus summary
```

### Event Notifications

Circuit breaker state changes trigger notifications:

1. **Circuit Opens**: Sends alert via Celery task
2. **Circuit Closes**: Logs recovery

## Fallback Strategies

### AI Agent Fallbacks

Each AI agent implements contextual fallbacks:

```python
def _get_circuit_breaker_fallback(self, input_text: str, context: Dict[str, Any]) -> str:
    agent_name = self.name.lower()
    
    if 'menu' in agent_name:
        return "I can help you with our menu. We have sushi rolls, nigiri, sashimi, and appetizers."
    elif 'cart' in agent_name:
        return "I'll help you add that to your order. What would you like?"
    # ... more agent-specific fallbacks
```

### Service-Specific Fallbacks

1. **OpenAI Failures**
   - Return contextual responses based on agent type
   - Maintain conversation flow without AI
   - Log for manual review

2. **Deliverect Failures**
   - Queue orders locally for later submission
   - Send notifications to staff
   - Provide order confirmation with manual processing note

3. **Twilio Failures**
   - Fall back to text-based interaction if possible
   - Log call details for recovery
   - Alert operations team

## Best Practices

1. **Always Handle CircuitBreakerError**
   - Provide meaningful fallback responses
   - Don't expose technical errors to users
   - Log context for debugging

2. **Monitor Circuit States**
   - Set up alerts for circuit opens
   - Track failure patterns
   - Review recovery success rates

3. **Test Fallback Behavior**
   - Include circuit breaker scenarios in tests
   - Verify graceful degradation
   - Test recovery mechanisms

4. **Configure Appropriately**
   - Set thresholds based on service SLAs
   - Adjust recovery timeouts for service characteristics
   - Consider business impact when setting parameters

## Testing

### Unit Tests

See `tests/unit/test_circuit_breaker.py` for comprehensive tests covering:
- State transitions
- Failure tracking
- Recovery mechanisms
- Event notifications
- Integration scenarios

### Manual Testing

```python
# Force circuit open for testing
circuit_breakers.openai._state = CircuitState.OPEN

# Test fallback behavior
# ... make requests ...

# Reset circuit
circuit_breakers.openai.reset()
```

## Future Enhancements

1. **Metrics Integration**
   - Export to Prometheus/Grafana
   - Real-time dashboards
   - Historical analysis

2. **Advanced Patterns**
   - Adaptive thresholds
   - Request prioritization
   - Bulkhead isolation

3. **Configuration Management**
   - Dynamic threshold adjustment
   - Service-specific timeout strategies
   - A/B testing for parameters