# Testing Framework for RedBarSushiAI

This directory contains tests and tools for testing the restaurant AI agent systematically before it goes to production.

## Test Types

1. **Unit Tests**: Test individual functions and components in isolation
   - Located in this directory with the `test_` prefix
   - Example: `test_ai_agent.py` for AI agent functionality

2. **Integration Tests**: Test interactions between components
   - Located in the `integration/` directory 
   - Example: `integration/test_menu_endpoint.py` for menu API endpoints

3. **Simulation Tests**: Test full customer conversations
   - Located in the `simulation/` directory
   - Example: `simulation/test_customer_interaction.py` for testing conversation flows

4. **Load Tests**: Test system performance under load
   - Located in the `load/` directory
   - Example: `load/test_concurrent_users.py` for simulating multiple users

## Setting Up a Test Environment

We've created tooling to help set up a proper test environment for both local development and Render staging environments.

### Local Test Environment

1. Create a local test environment:
   ```bash
   python tests/setup_test_env.py --with-sample-data
   ```

2. Run the tests:
   ```bash
   pytest
   ```

### Render-Compatible Test Environment

1. Create a Render-compatible test environment:
   ```bash
   python tests/setup_test_env.py --render-compatible --with-sample-data --setup-postgres
   ```

2. Run the tests:
   ```bash
   pytest
   ```

## Test Data

The tests use a combination of:
- Mock data defined in `conftest.py`
- Sample data created by `setup_test_env.py`
- Real API calls (for integration tests only when explicitly enabled)

## Testing the AI Agent

The AI agent is tested at multiple levels:

### 1. Core Functions (Unit Tests)

Tests for individual functions like `find_menu_item_by_name()`, `process_user_input()`, etc.

Example:
```python
# Test finding menu items
def test_find_menu_item_by_name():
    item = find_menu_item_by_name("California Roll")
    assert item is not None
    assert item["name"] == "California Roll"
```

### 2. Conversation Handling (Simulation Tests)

Tests for back-and-forth conversations with the AI agent.

Example:
```python
# Test a conversation scenario
def test_ordering_scenario():
    response1 = process_user_input("I'd like to order a California Roll")
    assert response1["intent"] == "order_food"
    
    response2 = process_user_input("Can I add a Spicy Tuna Roll?", session_id="123")
    assert len(response2["menu_items"]) == 2
```

### 3. Load Testing

Tests for system performance under multiple concurrent users.

## Best Practices

1. **Mock External Dependencies**: Always mock OpenAI, Twilio, and Deliverect APIs
2. **Use Fixtures**: Use pytest fixtures for common test data and setup
3. **Clean Up**: Ensure tests clean up after themselves (database, files)
4. **Environment Variables**: Use temporary environment variables for testing

## Running Specific Tests

You can run specific test files or directories:

```bash
# Run all unit tests (excluding integration and load tests)
python -m pytest -m "not integration and not load"

# Run integration tests only 
python -m pytest -m "integration"

# Run load tests only
python -m pytest -m "load"

# Run all tests
python -m pytest

# Run a specific test file
pytest tests/test_ai_agent.py

# Run tests with a specific name pattern
pytest -k "menu"

# Run tests with verbose output
pytest -v

# Run tests with coverage report
pytest --cov=app
```

## Continuous Integration

We use GitHub Actions to automatically run tests on every push and pull request.
See the workflow configuration in `.github/workflows/test.yml`.

## Staging Environment

For a full staging environment on Render, follow these steps:

1. Create a new Web Service on Render
2. Configure environment variables in Render dashboard
3. Use a separate database for staging
4. Run the load tests against the staging environment

## Adding New Tests

1. Add unit tests to the main test directory
2. Add integration tests to the `integration/` directory
3. Add simulation tests to the `simulation/` directory
4. Add load tests to the `load/` directory