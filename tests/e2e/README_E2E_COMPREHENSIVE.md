# Comprehensive E2E Testing Framework for RedBarSushiAI

This document describes the comprehensive end-to-end testing framework designed to validate the complete RedBarSushiAI system from user input through to order creation in Deliverect.

## Overview

The E2E testing framework follows a **multi-layered validation approach** that tests AI responses while ensuring deterministic system outcomes:

1. **Assertion Layer 1**: AI Response Validation (flexible keyword matching)
2. **Assertion Layer 2**: System State Validation (Redis cart/FSM state)  
3. **Assertion Layer 3**: External Integration Validation (Deliverect orders)

This approach allows AI creativity in responses while strictly verifying that actions, state changes, and final outputs are correct.

## Test Architecture

### Core Components

- **`conftest_e2e.py`**: Test fixtures, helper functions, and environment setup
- **`deliverect_test_helper.py`**: Deliverect API integration for order verification
- **`test_comprehensive_e2e.py`**: Complete test suite with all scenarios
- **`run-e2e-tests-docker.sh`**: Execution script for running tests in Docker

### Testing Methodology

The framework validates **deterministic outcomes** while flexibly asserting **non-deterministic responses**:

```python
# ✅ Flexible AI Response Validation
assert_contains_keywords(response.get("text", ""), ["edamame", "added"])

# ✅ Strict System State Validation  
cart = await get_cart_state(redis_client, call_sid)
assert len(cart.get("items", [])) == 1
assert cart["items"][0]["name"].lower() == "edamame"

# ✅ Ultimate Truth Validation
order_verified = await deliverect_helper.verify_order_exists(expected_items)
assert order_verified, "Order not found in Deliverect"
```

## Test Categories

### Category 1: Core Ordering Flow (Happy Paths)

**Test 1.1: Single Simple Item Order**
- Basic end-to-end flow: greeting → name → order → confirmation
- Validates fundamental system operation
- Verifies order appears correctly in Deliverect

**Test 1.2: Multi-Item Order with Quantity**  
- Tests handling of multiple items with specific quantities
- Validates cart management and order aggregation
- Ensures quantities are preserved through the entire flow

### Category 2: Item Customization & Modification

**Test 2.1: Order with Required Customization**
- Tests items that require mandatory modifiers (e.g., Steak Frites cooking temperature)
- Validates FSM state transitions to `ORDERING_ITEM_CUSTOMIZATION`
- Ensures items aren't added to cart until customization is complete

**Test 2.2: Order with Optional Modifier**
- Tests optional modifiers that users can accept or decline
- Validates graceful handling of modifier choices
- Verifies modifiers are correctly applied in final order

**Test 2.3: Modify Item Already in Cart**
- Tests `ORDERING_ITEM_MODIFICATION` state
- Validates ability to change quantities or modifiers of existing cart items
- Ensures cart updates are properly persisted

### Category 3: State Management & Edge Cases

**Test 3.1: Out of Stock and Recovery**
- Tests `ORDERING_OUT_OF_STOCK` state handling
- Validates graceful fallback when items are unavailable
- Ensures users can pivot to alternative items

**Test 3.2: Upsell Flow (if implemented)**
- Tests `ORDERING_UPSELL_SUGGESTION` state
- Validates optional upselling suggestions
- Ensures upsells are handled naturally in conversation

**Test 3.3: Ambiguous Item Disambiguation**
- Tests handling of ambiguous menu item requests
- Validates AI's ability to ask clarifying questions
- Ensures correct item selection after disambiguation

### Category 4: Validation and Error Recovery

**Test 4.1: Validation Catches Missing Modifier**
- Tests ValidationAgent as final safety net
- Validates detection of incomplete orders before submission
- Ensures proper remediation flow for missing required modifiers

**Test 4.2: User Cancels Order Midway**
- Tests order cancellation intent detection
- Validates proper cart clearing and session cleanup
- Ensures no orders are created in Deliverect after cancellation

## Configuration for Docker Environment

The tests are specifically configured to run against the Docker container setup:

### Network Configuration
- **App Container**: `http://redbarsushi-app-1:8000`
- **Redis Container**: `redis://redbarsushi-redis-1:6379/1` (using database 1 for testing)

### Environment Variables
```bash
export E2E_BASE_URL="http://redbarsushi-app-1:8000"
export E2E_REDIS_URL="redis://redbarsushi-redis-1:6379/1"
export DELIVERECT_API_KEY="your-staging-api-key"
export DELIVERECT_TEST_LOCATION_ID="test-location-redbarsushi"
```

## Test Menu Requirements

The tests require a specific Deliverect test menu with these items:

- **Edamame**: Simple product, no modifiers
- **Spicy Tuna Roll**: Simple product for upselling tests
- **Steak Frites**: Product with required modifier group ("Cooking Temperature")
- **Red Dragon Roll**: Product with optional modifier group ("Add-ons")
- **Seasonal Soup**: Product that is snoozed (out of stock)
- **California Roll & Cali-Crunch Roll**: Similarly named items for disambiguation
- **House Salad**: Another simple item for multi-item tests

## Running the Tests

### Quick Start
```bash
# Run all comprehensive E2E tests
./run-e2e-tests-docker.sh

# Run specific test category
./run-e2e-tests-docker.sh run core
./run-e2e-tests-docker.sh run customization
./run-e2e-tests-docker.sh run state
./run-e2e-tests-docker.sh run validation
```

### Manual Execution
```bash
# Setup environment
./run-e2e-tests-docker.sh setup

# Run specific test file inside container
docker exec -i redbarsushi-app-1 python -m pytest tests/e2e/test_comprehensive_e2e.py::TestCategory1CoreOrderingFlow -v

# Cleanup
./run-e2e-tests-docker.sh cleanup
```

## Expected Test Results

### Success Criteria
- All AI responses contain contextually appropriate keywords
- Cart state in Redis matches expected item configurations
- Orders appear in Deliverect with correct items, quantities, and modifiers
- FSM state transitions occur as expected for complex flows

### Example Success Output
```
✅ Test 1.1 passed: Single simple item order
✅ Test 1.2 passed: Multi-item order with quantity
✅ Test 2.1 passed: Order with required customization
...
🎉 ALL E2E TESTS PASSED! System is ready for production.
```

## Troubleshooting

### Common Issues

**Tests fail with connection errors**
- Ensure Docker containers are running: `docker-compose up -d`
- Check container network connectivity

**Deliverect verification fails**
- Verify API key and test location ID are correct
- Check that test menu items exist in Deliverect staging
- Ensure Seasonal Soup is snoozed for out-of-stock tests

**Redis state validation fails**
- Confirm Redis is using database 1 for tests
- Check that session management is working correctly

**AI responses don't contain expected keywords**
- Review AI prompts and system instructions
- Consider updating keyword assertions to be more flexible

### Debug Mode

Run tests with additional debugging:
```bash
docker exec -i redbarsushi-app-1 python -m pytest tests/e2e/test_comprehensive_e2e.py -v -s --tb=long
```

## Integration with CI/CD

This E2E test suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run E2E Tests
  run: |
    docker-compose up -d
    ./run-e2e-tests-docker.sh
    docker-compose down
```

## Test Data Management

- Each test uses a unique `call_sid` to avoid conflicts
- Redis test database (db 1) is flushed before/after test runs
- Deliverect orders are left for manual cleanup (typical POS behavior)

## Future Enhancements

- **Performance testing**: Add timing assertions for response times
- **Concurrent testing**: Test multiple simultaneous conversations
- **Voice integration**: Test actual audio input/output flows
- **Stress testing**: High-volume order processing validation
- **Integration depth**: Test more complex POS integration scenarios

This comprehensive E2E testing framework ensures that the RedBarSushiAI system works end-to-end in real conditions, providing confidence for production deployment.