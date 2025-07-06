# Comprehensive E2E Testing Suite for RedBarSushiAI

This directory contains a complete end-to-end testing suite that validates the entire RedBarSushiAI system without any mocking. These tests simulate real customer interactions from voice input to final order processing in Deliverect.

## Philosophy

The E2E tests follow a **zero-mocking** philosophy, meaning they test the complete, integrated system:

- ✅ Real OpenAI API calls for AI processing
- ✅ Real Redis cache operations
- ✅ Real PostgreSQL database interactions  
- ✅ Real Deliverect API integration (when configured)
- ✅ Complete HSM state management
- ✅ Full agent orchestration pipeline

## Test Environment Requirements

### Required Services
- **PostgreSQL**: Database with complete schema
- **Redis**: Cache for sessions and menu data
- **OpenAI API**: Real AI processing (requires valid API key)
- **Deliverect API**: Order verification (optional, will mock if not configured)

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://user:pass@localhost:5432/redbarsushi
REDIS_URL=redis://localhost:6379

# Optional (for real Deliverect integration)
DELIVERECT_API_KEY=your_deliverect_api_key
DELIVERECT_TEST_LOCATION_ID=test-location-redbarsushi
```

### Test Menu Setup

The tests require specific menu items in Deliverect for comprehensive testing:

1. **Edamame** (`TEST-EDAMAME`)
   - Simple item with no required modifiers
   - Used for basic ordering tests

2. **Steak Frites** (`TEST-STEAK-FRITES`)
   - Requires cooking temperature modifier (min: 1, max: 1)
   - Options: Rare, Medium Rare, Medium, Medium Well, Well Done
   - Used for required modifier testing

3. **Seasonal Soup** (`TEST-SEASONAL-SOUP`)
   - Must be "snoozed" (out of stock) in Deliverect
   - Used for out-of-stock handling tests

4. **Red Dragon Roll** (`TEST-RED-DRAGON-ROLL`)
   - Optional sauce modifiers (min: 0, max: 3)
   - Options: Spicy Mayo, Extra Wasabi, Soy Sauce, Pickled Ginger
   - Used for item modification tests

5. **California Roll** (`TEST-CALIFORNIA-ROLL`)
   - Standard sushi item with no modifiers
   - Used for multi-item order tests

## Test Cases

### Test Case 1: Happy Path with Required Customization
**File**: `test_happy_path_order_with_customization()`

**Validates**:
- Complete conversation flow from greeting to order completion
- Required modifier detection and handling
- State transitions: GREETING → MAIN_MENU → ORDERING → ITEM_CUSTOMIZATION → CONFIRMATION → FULFILLMENT
- Order creation in Deliverect with correct modifiers

**Expected Flow**:
```
User: "Hi, I'd like to place an order."
AI: (Greets and asks for name)
User: "My name is Bruce."
AI: (Acknowledges name and offers help)
User: "I'll have the Steak Frites."
AI: "For the Steak Frites, how would you like that cooked?" (CRITICAL: Must detect required modifier)
User: "Medium rare."
AI: "I've added one medium rare Steak Frites to your order."
User: "That's all for me."
AI: (Provides order summary and asks for confirmation)
User: "Yes, that's correct."
AI: (Confirms order placement)
```

### Test Case 2: Out-of-Stock Item Handling
**File**: `test_out_of_stock_item_handling()`

**Validates**:
- Detection of snoozed/unavailable items
- Graceful error handling and alternative suggestions
- State transition to ORDERING_OUT_OF_STOCK
- Recovery to normal ordering flow

**Expected Flow**:
```
User: "I would like the Seasonal Soup."
AI: "I'm sorry, the Seasonal Soup is currently unavailable. [suggests alternatives]" 
    (CRITICAL: Must detect snoozed item)
User: "Okay, then I'll just have the Edamame."
AI: "I've added Edamame to your order."
```

### Test Case 3: Validation Error Recovery
**File**: `test_validation_missing_required_modifier()`

**Validates**:
- ValidationAgent catches missing required modifiers
- Automatic state transition to fix validation issues
- Complete order processing after validation fixes
- Phase 3 validation integration working correctly

**Expected Flow**:
```
User: "Let me get the Edamame and the Steak Frites." (No cooking temp)
AI: "Edamame added. For the Steak Frites, how would you like that cooked?"
    (CRITICAL: Must immediately catch missing modifier)
User: "Well-done. That's everything."
AI: (Provides complete order summary with both items)
```

### Test Case 4: Item Modification Flow
**File**: `test_item_modification_flow()`

**Validates**:
- Customer can modify items already in cart
- State transition to ORDERING_ITEM_MODIFICATION
- Modifier application to existing items
- Phase 2 enhancement features working

**Expected Flow**:
```
User: "I'll get a Red Dragon Roll."
AI: "Added Red Dragon Roll to your order."
User: "Actually, can you add spicy mayo to that?"
AI: "I've added spicy mayo to your Red Dragon Roll."
    (CRITICAL: Must understand modification intent)
```

### Test Case 5: Complex Multi-Item Order
**File**: `test_complex_multi_item_order_with_validation()`

**Validates**:
- Complex order processing with multiple item types
- Comprehensive validation pipeline
- Cart management across multiple items
- Performance under realistic order complexity

## Running the Tests

### Quick Start
```bash
# Run all E2E tests
./run-e2e-tests.sh

# Run specific test
docker-compose exec app python -m pytest tests/e2e/test_comprehensive_e2e.py::test_happy_path_order_with_customization -v -s

# Run with detailed logging
DEBUG=1 ./run-e2e-tests.sh
```

### Test Runner Features

The `run-e2e-tests.sh` script provides:

- ✅ **Environment Validation**: Checks all required services and environment variables
- ✅ **Service Health Checks**: Ensures Docker services are healthy before testing
- ✅ **Test Data Setup**: Prepares Deliverect test menu automatically
- ✅ **Comprehensive Reporting**: Generates JUnit XML reports for CI/CD
- ✅ **Cleanup Options**: Clears test data after completion
- ✅ **Parallel Execution**: Optional parallel test execution for speed

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Run E2E Tests
  run: |
    export OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}
    export DELIVERECT_API_KEY=${{ secrets.DELIVERECT_API_KEY }}
    ./run-e2e-tests.sh
  timeout-minutes: 10

- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: e2e-test-results
    path: e2e-test-results.xml
```

## Validation Checklist

After running the E2E tests, verify:

- [ ] **All test cases pass** without any mocking
- [ ] **Response times** are under 3 seconds per interaction
- [ ] **State transitions** follow the HSM correctly
- [ ] **Menu matching** works for all item variations
- [ ] **Validation pipeline** catches and fixes order issues
- [ ] **Deliverect integration** creates real orders with correct modifiers
- [ ] **Error handling** gracefully manages edge cases
- [ ] **Agent orchestration** routes requests to appropriate specialists

## Performance Expectations

- **Response Time**: < 3 seconds per turn (95th percentile)
- **Memory Usage**: < 512MB per conversation session
- **API Calls**: Optimized OpenAI usage with appropriate caching
- **Database Queries**: < 10 queries per conversation turn
- **Redis Operations**: < 100ms cache access time

## Troubleshooting

### Common Issues

1. **OpenAI API Timeouts**
   - Check API key validity
   - Verify network connectivity
   - Monitor rate limits

2. **Deliverect Integration Failures**
   - Verify API key and location ID
   - Check test menu setup
   - Ensure items are properly configured

3. **Database Connection Issues**
   - Verify PostgreSQL service is running
   - Check connection string format
   - Ensure schema is properly migrated

4. **Redis Cache Problems**
   - Verify Redis service is accessible
   - Check memory usage and eviction policies
   - Clear cache if corrupted

### Debug Mode

Run with debug logging:
```bash
DEBUG=1 VERBOSE=1 ./run-e2e-tests.sh
```

This provides:
- Detailed conversation logs
- API request/response timing
- State transition tracking  
- Validation step-by-step analysis

## Success Criteria

The E2E test suite validates that RedBarSushiAI is production-ready when:

✅ **All 5 test cases pass** without mocking any services  
✅ **Real orders are created** in Deliverect with correct items and modifiers  
✅ **State management** follows the HSM specification exactly  
✅ **Validation pipeline** catches and resolves all order issues  
✅ **Performance meets requirements** (< 3s response time)  
✅ **Error handling** gracefully manages all edge cases  

When all criteria are met, the system is **validated for production deployment**.