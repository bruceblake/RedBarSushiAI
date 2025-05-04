# RedBarSushiAI Integration Tests

This document provides an overview of all integration tests available in the RedBarSushiAI system, including how to run them through the MCP (Model Context Protocol) interface.

## Test Categories

The system includes the following test categories:

| Category | Description | Files |
|----------|-------------|-------|
| **health** | Basic health check tests | `tests/e2e/test_health_check.py` |
| **voice_basic** | Basic voice endpoint tests | `tests/e2e/test_voice_endpoints.py` |
| **voice_flow** | Voice conversation flow tests | `tests/e2e/test_voice_flow.py`, `tests/e2e/test_voice_menu_handling.py` |
| **orders** | Basic order tests | `tests/e2e/test_basic_order.py`, `tests/e2e/test_complete_order_flow.py` |
| **deliverect** | Deliverect API integration tests | `tests/integration/test_deliverect_api_integration.py` |
| **menu_sync** | Deliverect menu synchronization tests | `tests/integration/test_deliverect_menu_synchronization.py` |
| **mcp_integration** | MCP integration tests | `tests/integration/test_mcp_test_integration.py` |
| **complete_order_e2e** | Complete order flow E2E tests | `tests/e2e/test_complete_order_flow_e2e.py` |
| **all_integration** | All integration tests | `tests/integration/` |
| **all_e2e** | All E2E tests | `tests/e2e/` |
| **all** | All tests | `tests/e2e/`, `tests/integration/` |

## Running Tests via MCP

Tests can be run through the MCP interface using Claude Code or through the command-line script.

### Using Claude Code:

```
/mcp run_test test_type="basic"
/mcp run_test test_type="voice"
/mcp run_test test_type="menu"
/mcp run_test test_type="order"
/mcp run_test test_type="deliverect"
/mcp run_test test_type="menu-sync"
/mcp run_test test_type="mcp"
/mcp run_test test_type="complete-order-e2e"
/mcp run_test test_type="integration"
/mcp run_test test_type="all"
```

### Using Command Line:

```bash
# Start the MCP server if not already running
./run_fixed_simple_mcp.sh

# Run tests directly
./test_staging_e2e.sh basic
./test_staging_e2e.sh voice
./test_staging_e2e.sh menu
./test_staging_e2e.sh order
./test_staging_e2e.sh deliverect
./test_staging_e2e.sh menu-sync
./test_staging_e2e.sh mcp
./test_staging_e2e.sh complete-order-e2e
./test_staging_e2e.sh integration
./test_staging_e2e.sh all
```

## Test Descriptions

### Deliverect API Integration Tests

`tests/integration/test_deliverect_api_integration.py`

This test suite verifies the integration with the Deliverect API for order submission and handling:

- **test_prepare_order_for_deliverect**: Tests that order items are properly prepared for Deliverect (reference handlers, prices, modifiers).
- **test_build_deliverect_order**: Verifies the structure of the Deliverect order payload (format, prices, customer details).
- **test_submit_order_to_deliverect**: Tests the process of submitting an order to the Deliverect API.
- **test_track_order_status**: Verifies tracking an order's status through the Deliverect API.
- **test_handle_deliverect_error_responses**: Tests handling of various error responses from the Deliverect API.
- **test_retry_mechanism_for_deliverect_api**: Tests the retry mechanism for temporary Deliverect API failures.

### Deliverect Menu Synchronization Tests

`tests/integration/test_deliverect_menu_synchronization.py`

This test suite verifies the synchronization of menu data from Deliverect:

- **test_process_deliverect_menu**: Tests the Deliverect menu processing function that converts the Deliverect format to the internal menu format.
- **test_store_deliverect_menu**: Verifies that menu data is correctly stored in the database.
- **test_process_webhook_format**: Tests that webhook formatted data is correctly processed.
- **test_menu_update_price_changes**: Verifies handling of menu updates with price changes.
- **test_variant_price_calculation**: Tests that variant prices are correctly calculated.
- **test_modifier_groups_assignment**: Verifies that modifier groups are correctly assigned to items.
- **test_modify_item_availability**: Tests updating item availability (snoozed status).
- **test_sync_rollback_on_failure**: Verifies that menu synchronization rolls back changes if there's a failure mid-update.

### Complete Order Flow E2E Tests

`tests/e2e/test_complete_order_flow_e2e.py`

This test suite verifies the end-to-end order flow:

- **test_end_to_end_order_flow**: Tests the complete order flow from conversation to Deliverect submission and tracking.
- **test_order_flow_with_error_recovery**: Tests the order flow with error handling and recovery.
- **test_order_flow_with_timeouts**: Tests the order flow with timeouts and recovery.

### MCP Integration Tests

`tests/integration/test_mcp_test_integration.py`

This test suite verifies the MCP integration:

- **test_mcp_run_test_command**: Tests that the MCP server can execute a test command and return results.
- **test_mcp_handle_test_failure**: Tests that the MCP server correctly handles test failures.
- **test_mcp_echo_tool**: Tests the MCP echo tool.
- **test_mcp_initialize**: Tests the MCP initialize method to verify protocol compatibility.
- **test_mcp_tools_list**: Verifies the MCP tools_list method returns the correct tools.
- **test_mcp_run_all_tests_cmd**: Tests the MCP can execute the 'all' test command.
- **test_mcp_protocol_compatibility**: Comprehensive test of MCP protocol compatibility.

## Adding New Tests

When adding new tests:

1. Create the test file in the appropriate directory:
   - E2E tests in `tests/e2e/`
   - Integration tests in `tests/integration/`
   - Unit tests in `tests/unit/`

2. Update the test configuration in `mcp/test_config.py` to include the new test.

3. Update the test script `test_staging_e2e.sh` to run the new test.

4. Update this document (`INTEGRATION_TESTS.md`) with the new test information.

## Best Practices

- Always include appropriate fixtures for test setup.
- Use mock objects for external dependencies (Deliverect API, Twilio, etc.).
- Include both positive and negative test cases.
- Test boundary conditions and error handling.
- Make tests independent of each other.
- Include clear assertions and error messages.
- Add appropriate pytest marks (e.g., `@pytest.mark.integration`).