# RedBarSushiAI Tests

This directory contains tests for the RedBarSushiAI voice ordering system.

## Test Structure

- `conftest.py`: Contains common fixtures and configurations for all tests
- `e2e/`: End-to-end tests that test the system as a whole
- `integration/`: Integration tests that test how components work together

## Test Categories

The tests are organized into the following categories:

- **Voice Processing**: Tests for the voice and WebSocket handling
- **Menu Handling**: Tests for menu querying and display
- **Order Processing**: Tests for cart, order creation, and submission
- **Guardrails and Validation**: Tests for business rules and constraints

## Running Tests

### Running All Tests

```bash
pytest
```

### Running Specific Test Categories

```bash
# Run all end-to-end tests
pytest -m e2e

# Run voice processing tests
pytest -m voice

# Run menu handling tests
pytest -m menu

# Run order processing tests
pytest -m order

# Run WebSocket tests
pytest -m websocket
```

### Running Specific Test Files

```bash
# Run a specific test file
pytest tests/e2e/test_ai_voice_ordering.py

# Run tests with verbose output
pytest -v tests/e2e/test_order_processing.py
```

## Test Features

### Mock WebSockets

The tests use mock WebSockets to simulate real-time audio interactions without requiring actual audio hardware or network connections.

### Mock Agents

The agent system is mocked to isolate tests from external dependencies like OpenAI.

### In-Memory Database

Tests use an in-memory SQLite database with test data to avoid affecting the real database.

### Mock External APIs

External APIs (Twilio, Deliverect, OpenAI) are mocked to prevent actual network calls during testing.

## Adding New Tests

When adding new tests, follow these guidelines:

1. Add appropriate pytest markers (`@pytest.mark.e2e`, `@pytest.mark.voice`, etc.)
2. Use fixtures from `conftest.py` where appropriate
3. Mock external dependencies
4. Keep tests isolated and idempotent
5. Use descriptive test names that explain what is being tested

## Test Data

The test data includes:

- Sample menu items (California Roll, Spicy Tuna Roll)
- Modifiers (Extra Avocado, Spicy Mayo)
- Variant mappings for natural language understanding
- Test location information