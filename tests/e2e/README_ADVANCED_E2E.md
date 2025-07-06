# Advanced E2E Testing Suite for RedBarSushiAI

This comprehensive E2E testing suite elevates your RedBarSushiAI system from basic functionality validation to production-ready quality assurance. The advanced test categories push the boundaries of conversational complexity, system stress, and failure recovery.

## Overview

The advanced E2E tests are designed to validate that your AI-powered voice ordering system can handle the messy, unpredictable nature of real-world usage, including edge cases, failures, and malicious inputs.

## Test Categories

### Category 5: Complex Conversational Fluidity Tests
**File**: `test_advanced_conversational_fluidity.py`

Tests the AI's ability to handle sophisticated conversational scenarios:

- **Test 5.1**: Mid-conversation correction and ambiguity resolution
- **Test 5.2**: Multi-intent parsing and out-of-order information handling  
- **Test 5.3**: Contextual memory and reference resolution
- **Test 5.4**: Conversation flow recovery and repair

**Key Validations**:
- AI correctly discards previous choices and locks onto final decisions
- Pronouns are resolved correctly in context
- Multiple intents in single utterances are handled properly
- Conversation coherence is maintained after interruptions

### Category 6: Stress, Load, and Concurrency Testing
**File**: `test_stress_load_concurrency.py`

Validates system performance and stability under pressure:

- **Test 6.1**: Concurrent session isolation and data integrity
- **Test 6.2**: Load performance degradation analysis
- **Test 6.3**: Session state consistency under load
- **Test 6.4**: Resource exhaustion and recovery

**Key Validations**:
- No data crossover between concurrent sessions
- Performance degrades gracefully under increasing load
- Cart operations maintain integrity under stress
- System recovers after resource exhaustion

### Category 7: Integration Failure and Resiliency Testing
**File**: `test_integration_failure_resiliency.py`

Tests system resilience to external service failures:

- **Test 7.1**: OpenAI API failure handling
- **Test 7.2**: Deliverect API failure handling
- **Test 7.3**: Redis connection failure handling
- **Test 7.4**: Database connection failure handling
- **Test 7.5**: Network timeout and retry logic

**Key Validations**:
- Graceful fallback when core LLM is unavailable
- Appropriate error messages for service failures
- System state remains stable during API failures
- Recovery mechanisms work when services are restored

### Category 8: Security and Robustness Testing
**File**: `test_security_robustness.py`

Validates system security and robustness:

- **Test 8.1**: Prompt injection attack prevention
- **Test 8.2**: Input sanitization and validation
- **Test 8.3**: Rate limiting and abuse prevention
- **Test 8.4**: Data privacy and isolation
- **Test 8.5**: System robustness under attack

**Key Validations**:
- AI maintains restaurant role despite injection attempts
- Malicious input is sanitized safely
- User data remains isolated between sessions
- System remains stable under various attack vectors

## Running the Advanced Tests

### Prerequisites

1. **Docker Environment**: Tests run against the Dockerized application
2. **Environment Variables**: Ensure all required environment variables are set
3. **Test Dependencies**: Install additional dependencies for advanced testing

```bash
# Install additional test dependencies
pip install sentence-transformers pytest-xdist toxiproxy-python

# Ensure Docker containers are running
docker-compose up -d
```

### Running Individual Test Categories

```bash
# Run conversational fluidity tests
pytest tests/e2e/test_advanced_conversational_fluidity.py -v

# Run stress and load tests (may take longer)
pytest tests/e2e/test_stress_load_concurrency.py -v -m slow

# Run integration failure tests
pytest tests/e2e/test_integration_failure_resiliency.py -v

# Run security tests
pytest tests/e2e/test_security_robustness.py -v
```

### Running All Advanced Tests

```bash
# Run all advanced E2E tests
pytest tests/e2e/test_advanced_*.py tests/e2e/test_stress_*.py tests/e2e/test_integration_*.py tests/e2e/test_security_*.py -v

# Run with parallel execution (faster)
pytest tests/e2e/test_advanced_*.py -n auto

# Run only quick tests (skip slow tests)
pytest tests/e2e/test_advanced_*.py -m "not slow"
```

### Docker-based Test Execution

```bash
# Run tests inside Docker container for consistency
./run-docker-tests.sh advanced

# Run specific advanced test category
docker exec -it redbarsushi-app-1 pytest tests/e2e/test_advanced_conversational_fluidity.py -v
```

## Test Configuration

### Environment Variables

```bash
# Base URL for E2E tests (default: container network)
E2E_BASE_URL=http://redbarsushi-app:8000

# Redis URL for E2E tests (default: container network)
E2E_REDIS_URL=redis://redbarsushi-redis:6379/1

# Test timeout settings
E2E_TIMEOUT=30

# Enable performance monitoring
E2E_PERFORMANCE_MONITORING=true
```

### Pytest Markers

The advanced tests use custom pytest markers:

- `@pytest.mark.e2e`: Marks tests as end-to-end tests
- `@pytest.mark.slow`: Marks tests that take longer to run
- `@pytest.mark.deliverect`: Tests requiring Deliverect API access

### Test Data Configuration

Advanced tests use dynamic test data generation to avoid conflicts:

```python
# Unique call SIDs with timestamps
call_sid = f"e2e_test_{test_name}_{int(time.time())}"

# Session isolation with unique identifiers
session_id = f"session_{uuid.uuid4().hex[:8]}"
```

## Performance Monitoring

The advanced test suite includes comprehensive performance monitoring:

### Metrics Tracked

- **Response Times**: Average, max, min, 95th percentile
- **Request Rates**: Requests per second under load
- **Error Rates**: Failure rates under stress
- **Resource Utilization**: Memory and CPU usage patterns
- **Concurrency Metrics**: Session isolation and data integrity

### Performance Thresholds

```python
# Response time thresholds
ACCEPTABLE_AVG_RESPONSE_TIME = 5.0  # seconds
ACCEPTABLE_MAX_RESPONSE_TIME = 15.0  # seconds

# Success rate thresholds
MINIMUM_SUCCESS_RATE = 0.8  # 80%
CONCURRENT_SESSION_SUCCESS_RATE = 0.6  # 60% under load

# Performance degradation limits
MAX_PERFORMANCE_DEGRADATION = 5.0  # 5x baseline under stress
```

## Security Test Methodology

### Prompt Injection Testing

The security tests validate resistance to various prompt injection techniques:

- Role override attempts
- System instruction bypassing
- Context confusion attacks
- Authority claim attempts
- Code injection attempts

### Input Sanitization Testing

Comprehensive validation of input handling:

- SQL injection prevention
- XSS attack neutralization
- Command injection blocking
- Unicode bypass prevention
- Special character handling

### Privacy and Data Isolation

Rigorous validation of data privacy:

- Session isolation verification
- Cross-user data leak prevention
- Personal information protection
- Cart data privacy maintenance

## Failure Simulation

### Network Failure Simulation

Advanced tests simulate various network conditions:

```python
# Timeout simulation
await NetworkFailureSimulator.simulate_timeout(
    client, call_sid, user_input, timeout_duration=5.0
)

# Intermittent failure simulation
await NetworkFailureSimulator.simulate_intermittent_failure(
    client, call_sid, user_input, failure_rate=0.3
)
```

### Service Failure Simulation

Tests simulate external service failures:

- OpenAI API unavailability
- Deliverect API timeouts
- Redis connection loss
- Database connectivity issues

## Load Testing Methodology

### Concurrent User Simulation

```python
# Test concurrent sessions
NUM_CONCURRENT_SESSIONS = 10
SESSION_DURATION = 30  # seconds

# Load level testing
LOAD_LEVELS = [1, 3, 5, 8, 12]  # Concurrent requests
REQUESTS_PER_LEVEL = 20
```

### Performance Analysis

Comprehensive analysis of load test results:

- Throughput metrics
- Latency distribution
- Error rate analysis
- Resource utilization
- Scalability limits

## Best Practices

### Test Isolation

- Each test uses unique identifiers to prevent interference
- Redis test database is cleaned after each test
- Session data is properly isolated

### Error Handling

- Tests validate graceful error handling, not just success cases
- Fallback mechanisms are thoroughly tested
- Recovery scenarios are validated

### Real-world Scenarios

- Tests simulate actual user behavior patterns
- Edge cases reflect real production issues
- Failure scenarios mirror actual operational challenges

### Continuous Improvement

- Performance baselines are established and tracked
- Security test payloads are regularly updated
- Load test scenarios evolve with system changes

## Troubleshooting

### Common Issues

1. **Test Timeouts**: Increase timeout values in slow environments
2. **Resource Constraints**: Reduce concurrency levels for limited hardware
3. **Network Issues**: Verify Docker network connectivity
4. **Redis Connection**: Ensure Redis is accessible from test containers

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Run with debug logging
pytest tests/e2e/test_advanced_*.py -v -s --log-level=DEBUG

# Capture stdout for analysis
pytest tests/e2e/test_advanced_*.py -v -s --capture=no
```

### Performance Profiling

Monitor system resources during testing:

```bash
# Monitor Docker container resources
docker stats

# Profile test execution
pytest tests/e2e/test_stress_load_concurrency.py --profile

# Generate performance reports
pytest tests/e2e/test_stress_load_concurrency.py --benchmark-save=results
```

## Integration with CI/CD

### GitHub Actions Integration

```yaml
# .github/workflows/advanced-e2e.yml
name: Advanced E2E Tests

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  advanced-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Advanced E2E Tests
        run: |
          docker-compose up -d
          ./run-docker-tests.sh advanced
          
      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        with:
          name: advanced-e2e-results
          path: test-results/
```

### Test Result Analysis

Automated analysis of test results:

- Performance trend analysis
- Security vulnerability detection
- Reliability metrics tracking
- Capacity planning insights

This advanced E2E testing suite ensures your RedBarSushiAI system is truly production-ready, capable of handling real-world complexity, failures, and security challenges.