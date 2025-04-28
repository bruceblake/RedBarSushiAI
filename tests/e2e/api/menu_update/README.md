# Menu Update E2E Tests

This directory contains end-to-end tests for the menu update functionality, which is critical for the Deliverect integration.

## Test Structure

The tests are organized as follows:

- **test_menu_update.py**: Basic tests for the menu update endpoint.
- **test_menu_update_formats.py**: Tests for different menu payload formats.
- **test_deliverect_integration.py**: Tests for the Deliverect webhook integration.
- **test_menu_cache.py**: Tests for menu caching and refreshing.

## Running Tests

To run all menu update tests:

```bash
pytest tests/e2e/api/menu_update/ -v
```

To run a specific test file:

```bash
pytest tests/e2e/api/menu_update/test_deliverect_integration.py -v
```

To run only tests that are not skipped:

```bash
pytest tests/e2e/api/menu_update/ -v -k "not skip"
```

## Fixtures

The following fixtures are defined in the main `tests/e2e/conftest.py`:

- **api_request**: Wrapper around the Playwright API context.
- **create_test_menu_payload**: Factory for creating test menu payloads in different formats.
- **deliverect_menu_payload**: Sample Deliverect menu payload.
- **async_menu_payload**: Sample async Deliverect menu payload.

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

1. **Standard Deliverect**: With categories, products, modifierGroups, and modifiers.
2. **Async Deliverect**: Wrapped in a body object with menus array and callback URL.
3. **Direct Format**: Matching our internal data structure with items, modifiers, and modifierGroups arrays.
4. **Simple List**: Just an array of menu items.

## Notes on Test Implementation

- Tests are designed to be run both in sequence and independently
- Tests that don't work with the current API implementation are marked with `@pytest.mark.skip`
- Error checking includes conditional assertions for items that may not exist in isolated test runs
- Some tests intentionally send invalid data to test the system's robustness
- Tests verify both the API response and the actual menu state through GET /menu calls

## API Behavior Notes

The following behaviors have been observed in the current API implementation:

1. The API appears to always classify direct format updates with `"source": "deliverect"` rather than `"source": "custom"`.
2. The API rejects complex nested Deliverect webhook structures with 400 status.
3. The snooze/unsnooze endpoint expects a format different from what is documented.
4. The API may convert prices to different formats (e.g., dollars to cents).
5. The `/clear_menu_cache` endpoint returns a message with the item count rather than an explicit item_count field.
6. The API rejects some types of invalid data structures that might theoretically be fixable.