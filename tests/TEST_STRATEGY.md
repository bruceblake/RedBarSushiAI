# RedBarSushiAI Testing Strategy

## Overview

This document outlines the testing strategy for RedBarSushiAI, following the testing pyramid approach with appropriate use of mocks and real services based on the environment.

## Test Categories

### 1. Unit Tests (Development Environment)
- **Location**: `tests/unit/`
- **Mocking**: Heavy mocking of all external dependencies
- **Run**: Every commit, pre-push
- **Purpose**: Test individual functions, classes, and methods in isolation

Examples:
- FSM state transition logic
- Agent decision-making logic
- Utility functions (menu parsing, order formatting)
- Individual webhook handlers

### 2. Integration Tests (Development/CI Environment)
- **Location**: `tests/integration/`
- **Mocking**: Strategic mocking of external services, use sandboxes when available
- **Run**: CI pipeline, development
- **Purpose**: Test component interactions

Examples:
- FSM + Agent orchestration (with mocked OpenAI/Deliverect)
- ConversationRelay webhook processing (with sample Twilio payloads)
- Database operations with test database
- Redis caching with test Redis instance

### 3. End-to-End Tests (Staging Environment Only)
- **Location**: `tests/e2e/`
- **Mocking**: Minimal - use real services wherever possible
- **Run**: Staging environment, nightly builds
- **Purpose**: Validate complete user flows with real integrations

Examples:
- Complete voice order flow (Twilio → OpenAI → Deliverect)
- Menu inquiry conversations
- Error recovery scenarios
- Order modification flows

## Environment-Based Testing

### Development Environment
```bash
# Run unit and integration tests only
pytest tests/unit tests/integration -v

# Skip e2e tests automatically
pytest -v  # e2e tests marked with @pytest.mark.e2e will be skipped
```

### CI Environment
```bash
# Run unit and integration tests with coverage
pytest tests/unit tests/integration --cov=app --cov-report=xml

# Run selective e2e tests with mocks
pytest tests/e2e -m "not requires_staging" -v
```

### Staging Environment
```bash
# Set environment
export FASTAPI_ENV=staging

# Run all tests including e2e
pytest -v

# Run only e2e tests
pytest tests/e2e -v
```

## Service-Specific Testing Approach

### Twilio
- **Unit/Integration**: Use sample webhook payloads, test TwiML generation
- **E2E (Staging)**: Use Twilio test credentials and test phone numbers

### OpenAI
- **Unit/Integration**: Mock all OpenAI API calls
- **E2E (Staging)**: Use real API with cheaper models (gpt-3.5-turbo) or test assistants

### Deliverect
- **Unit/Integration**: Mock API responses or use sandbox if available
- **E2E (Staging)**: Use Deliverect sandbox environment

### Database
- **Unit**: Use in-memory SQLite or mock repositories
- **Integration**: Use test PostgreSQL database
- **E2E**: Use staging PostgreSQL database with test data

### Redis
- **Unit**: Mock Redis operations
- **Integration/E2E**: Use test Redis instance

## Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit  # Unit test
@pytest.mark.integration  # Integration test
@pytest.mark.e2e  # End-to-end test
@pytest.mark.slow  # Slow test (>1 second)
@pytest.mark.requires_openai  # Requires OpenAI API
@pytest.mark.requires_twilio  # Requires Twilio credentials
@pytest.mark.requires_deliverect  # Requires Deliverect access
```

## Best Practices

1. **No Mocks in E2E Tests** (with exceptions):
   - E2E tests should use real services in staging
   - Exception: Mock specific error scenarios that are hard to reproduce
   - Exception: Mock services that are temporarily unavailable

2. **Test Data Management**:
   - Use fixtures for consistent test data
   - Clean up test data after each test
   - Use unique identifiers to prevent conflicts

3. **Async Testing**:
   - Use `pytest.mark.asyncio` for async tests
   - Properly await all async operations
   - Use `AsyncMock` for mocking async functions

4. **Error Testing**:
   - Test both success and failure paths
   - Test timeout scenarios
   - Test network interruptions
   - Test invalid inputs

## Running Tests

### Quick Development Testing
```bash
# Run fast unit tests
pytest tests/unit -v --tb=short

# Run specific test file
pytest tests/unit/test_fsm.py -v

# Run with pattern matching
pytest -k "test_menu" -v
```

### Comprehensive Testing
```bash
# Run all non-e2e tests with coverage
pytest -m "not e2e" --cov=app --cov-report=html

# Run integration tests only
pytest -m integration -v
```

### Staging Testing
```bash
# Set staging environment
export FASTAPI_ENV=staging

# Run e2e tests
pytest tests/e2e -v

# Run specific e2e scenario
pytest tests/e2e/test_full_order_flow.py::test_complete_voice_order_flow -v
```

## Continuous Improvement

1. Monitor test execution times
2. Refactor slow tests
3. Add tests for bug fixes
4. Maintain test coverage above 80%
5. Review and update mocks when APIs change