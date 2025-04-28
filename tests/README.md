# Testing Strategy for RedBarSushiAI

This document outlines the testing strategy for the RedBarSushiAI application, describing the different types of tests and their purpose.

## Testing Layers

The application uses three primary testing layers, following industry best practices:

### 1. Unit Tests

Unit tests focus on testing individual components in isolation. They verify that specific functions and methods work correctly on their own.

**Characteristics:**
- Fast execution
- No external dependencies (all dependencies are mocked)
- Test single units of functionality
- Located in `/tests/unit/`

**When to use unit tests:**
- Testing utility functions and helpers
- Testing data transformations
- Testing business logic
- Testing edge cases and error handling

### 2. Integration Tests

Integration tests verify that multiple components work correctly together. They test the interactions between components within the application.

**Characteristics:**
- Components are tested together
- External dependencies may be mocked
- Focus on component boundaries and interactions
- Located in `/tests/integration/`

**When to use integration tests:**
- Testing API endpoints with their handlers
- Testing database operations
- Testing interactions between services
- Testing how components combine to implement features

### 3. End-to-End (E2E) Tests

E2E tests verify complete user workflows and business processes. They test the entire application stack through its external interfaces.

**Characteristics:**
- Test complete user flows
- Minimal or no mocking
- Test from the user's perspective
- Located in `/tests/e2e/`

**When to use E2E tests:**
- Testing complete user journeys
- Testing business processes from start to finish
- Testing integrations with external systems
- Testing critical paths in production-like environments

## Test Organization

### Unit Tests

- `/tests/unit/test_menu_utils.py` - Tests for menu utility functions
- `/tests/unit/test_menu_matcher.py` - Tests for menu matching functionality

### Integration Tests

- `/tests/integration/test_menu_integration.py` - Tests for menu component interactions
- `/tests/integration/test_deliverect_price_handling.py` - Tests for price handling with Deliverect
- `/tests/integration/test_deliverect_categories.py` - Tests for category handling with Deliverect
- `/tests/integration/test_deliverect_modifiers.py` - Tests for modifier handling with Deliverect
- `/tests/integration/test_snooze_functionality.py` - Tests for snooze/unsnooze functionality

### E2E Tests

- `/tests/e2e/test_complete_order_flow.py` - Tests for complete order workflows

## Fixtures

Fixtures are organized by test layer:

- `/tests/unit/conftest.py` - Unit test fixtures
- `/tests/integration/conftest.py` - Integration test fixtures
- `/tests/e2e/conftest.py` - E2E test fixtures

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only E2E tests
pytest tests/e2e/

# Run tests with specific markers
pytest -m unit
pytest -m integration
pytest -m e2e
```

## Testing Best Practices

1. **Test Pyramid**: Follow the test pyramid with more unit tests than integration tests, and more integration tests than E2E tests.

2. **Isolation**: Unit tests should be isolated and not depend on external services or state.

3. **Fixtures**: Use fixtures to set up test data and environments.

4. **Clear Assertions**: Make clear assertions about what you're testing.

5. **Test Coverage**: Aim for high test coverage, especially for critical business logic.

6. **Test First**: Consider writing tests before implementing features (TDD).

7. **Test Readability**: Write clear, readable tests that serve as documentation.

8. **Fast Feedback**: Tests should run quickly to provide fast feedback.

9. **Continuous Integration**: Run tests automatically in CI/CD pipelines.

10. **Meaningful Names**: Use meaningful names for test files and test methods.

## Common Testing Scenarios

### Menu Updates

- **Unit Tests**: Test menu validation, price conversion, etc.
- **Integration Tests**: Test API endpoints with menu validation and storage.
- **E2E Tests**: Test updating a menu and then using it to place an order.

### Order Processing

- **Unit Tests**: Test order validation, pricing calculations, etc.
- **Integration Tests**: Test order API with order processor.
- **E2E Tests**: Test complete order flow from menu update to order completion.

### Snooze/Unsnooze Functionality

- **Unit Tests**: Test snooze data validation.
- **Integration Tests**: Test snooze API with menu storage.
- **E2E Tests**: Test snoozing an item and verifying it's not available for ordering.

## Test Data Management

1. **Fixtures**: Use pytest fixtures to create and manage test data.
2. **Factory Methods**: Use factory methods to create test objects.
3. **Temporary Files**: Use temporary files for testing file operations.
4. **Mock Responses**: Use mock responses for external API calls.

## Continuous Improvement

The testing strategy should evolve with the application. Regularly review:

1. Test coverage
2. Test execution time
3. Test failures and flakiness
4. Test effectiveness at catching bugs