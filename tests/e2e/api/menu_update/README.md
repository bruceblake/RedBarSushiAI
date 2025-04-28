# Menu Update E2E Tests

This directory contains end-to-end tests for the menu update functionality, which is critical for the Deliverect integration.

## Test Structure

The tests are organized as follows:

- **test_menu_update.py**: Basic tests for the menu update endpoint.
- **test_menu_update_formats.py**: Tests for different menu payload formats.
- **test_deliverect_integration.py**: Tests for the Deliverect webhook integration.
- **test_menu_cache.py**: Tests for menu caching and refreshing.
- **conftest.py**: Test fixtures and utilities.

## Running Tests

To run all menu update tests:

```bash
pytest tests/e2e/api/menu_update/ -v
```

To run a specific test file:

```bash
pytest tests/e2e/api/menu_update/test_deliverect_integration.py -v
```

## Covered Scenarios

These tests cover the following scenarios:

1. Basic menu update with different payload formats
2. Async Deliverect webhook handling with callbacks
3. PLU preservation and validation
4. Handling partial menu updates
5. Snooze/unsnooze functionality
6. Menu caching and refreshing
7. Handling of invalid or malformed data

## Menu Payload Formats

The tests handle several menu payload formats:

1. **Standard Deliverect**: As described in real_docs.md, with categories, products, modifierGroups, and modifiers.
2. **Async Deliverect**: Wrapped in a body object with menus array and callback URL.
3. **Direct Format**: Matching our internal data structure with items, modifiers, and modifierGroups arrays.
4. **Simple List**: Just an array of menu items.

## Fixtures

- **api_request**: Wrapper around the Playwright API context.
- **create_test_menu_payload**: Factory for creating test menu payloads in different formats.
- **deliverect_menu_payload**: Sample Deliverect menu payload from testing_data.
- **async_menu_payload**: Sample async Deliverect menu payload.

## Mocks

Some tests use mocking to verify behavior without making external API calls:

- **test_async_callback_functionality**: Mocks the requests.post function to verify callbacks.

## Best Practices

When adding new tests:

1. Use the existing fixtures to create payloads
2. Group related tests in the appropriate file
3. Follow the naming convention: test_*_functionality
4. Add assertions for both the API response and the resulting menu state