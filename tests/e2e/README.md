# E2E Conversation Flow Tests

This module provides comprehensive end-to-end testing for RedBarSushiAI, simulating complete user conversations from initial greeting to order completion.

## Overview

The E2E testing framework validates the entire system by:
- Simulating real user conversations through WebSocket connections
- Testing all conversation paths (happy path, error recovery, edge cases)
- Verifying state transitions and agent handoffs
- Validating conversation outcomes and business logic
- Measuring system performance and response times

## Components

### 1. Conversation Scenarios (`conversation_scenarios.py`)

Defines structured test scenarios across multiple categories:

- **Happy Path**: Simple successful orders
- **Error Recovery**: Handling unavailable items, connection issues
- **Complex Orders**: Large orders, modifications, cancellations
- **Edge Cases**: Rapid context switches, ambiguous requests
- **Stress Tests**: Long conversations, maximum complexity

Each scenario includes:
- Conversation turns with expected states
- Validation functions for responses
- Expected outcomes for verification

### 2. E2E Test Runner (`e2e_test_runner.py`)

Executes scenarios against the live system:
- WebSocket connection management
- Turn-by-turn conversation execution
- State and context validation
- Response time measurement
- Comprehensive result tracking

### 3. CLI Interface (`run_e2e_tests.py`)

Command-line tool for running tests:
- Filter by scenario type or tags
- Run individual scenarios
- Mock server support for isolated testing
- Detailed reporting and summaries

### 4. Mock Server (`websocket_mock_server.py`)

Simulates the RedBarSushiAI system for testing:
- Predefined responses for common inputs
- State machine simulation
- Context management
- Useful for development and CI/CD

## Usage

### Running All Tests

```bash
# Run all E2E tests against local system
python tests/e2e/run_e2e_tests.py

# Run against specific environment
python tests/e2e/run_e2e_tests.py --base-url http://staging.example.com --ws-url ws://staging.example.com/ws
```

### Running Filtered Tests

```bash
# Run only happy path scenarios
python tests/e2e/run_e2e_tests.py --type happy_path

# Run scenarios with specific tags
python tests/e2e/run_e2e_tests.py --tags pickup simple

# Run a single scenario
python tests/e2e/run_e2e_tests.py --scenario happy_path_001
```

### Using Mock Server

```bash
# Run tests against mock server (no real system needed)
python tests/e2e/run_e2e_tests.py --mock

# Start mock server standalone
python tests/e2e/websocket_mock_server.py
```

### Listing Scenarios

```bash
# List all available test scenarios
python tests/e2e/run_e2e_tests.py --list
```

## Scenario Structure

Each scenario consists of:

```python
ConversationScenario(
    id="unique_id",
    name="Descriptive Name",
    description="What this tests",
    scenario_type=ScenarioType.HAPPY_PATH,
    turns=[
        ConversationTurn(
            speaker="user",
            message="What the user says",
            expected_state="EXPECTED_FSM_STATE",
            expected_agent="expected_agent_name",
            expected_context={"key": "value"},  # Or validation function
            validation_function=lambda response: "keyword" in response
        ),
        # More turns...
    ],
    expected_outcome={
        "order_placed": True,
        "items_count": 2
    }
)
```

## Test Categories

### Happy Path Tests
- Simple pickup order
- Order with menu questions
- Delivery order with address

### Error Recovery Tests
- Item not available
- Connection/audio issues
- Invalid input handling

### Complex Order Tests
- Large group orders
- Multiple modifications
- Partial cancellations

### Edge Case Tests
- Rapid context switches
- Ambiguous requests
- Minimal input

### Stress Tests
- Maximum length conversations
- High complexity orders
- Performance limits

## Validation Types

### State Validation
Verifies FSM transitions:
```python
expected_state="ORDERING"
```

### Agent Validation
Verifies correct agent selection:
```python
expected_agent="cart"
```

### Context Validation
Verifies context updates:
```python
# Exact match
expected_context={"customer_name": "John"}

# Function validation
expected_context=lambda ctx: len(ctx.get("cart", [])) > 0
```

### Response Validation
Verifies response content:
```python
validation_function=lambda resp: "california roll" in resp.lower()
```

### Outcome Validation
Verifies final results:
```python
expected_outcome={
    "order_placed": True,
    "order_type": "pickup"
}
```

## Output and Reports

### Console Output
- Real-time test progress
- Pass/fail status for each scenario
- Summary statistics

### JSON Reports
Detailed results saved to `test_results/`:
- `e2e_results_TIMESTAMP.json`: Full test data
- `e2e_report_TIMESTAMP.json`: Summary report

### Markdown Summary
Human-readable summary:
- `e2e_summary_TIMESTAMP.md`

## Integration with CI/CD

### Basic Integration
```bash
# Exit with error code on failure
python tests/e2e/run_e2e_tests.py --quiet

# Check exit code
if [ $? -ne 0 ]; then
    echo "E2E tests failed"
    exit 1
fi
```

### GitHub Actions Example
```yaml
- name: Run E2E Tests
  run: |
    python tests/e2e/run_e2e_tests.py --type happy_path --quiet
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Performance Thresholds
Check response times in the report:
```python
import json

with open('test_results/e2e_report_latest.json') as f:
    report = json.load(f)

avg_response_time = report['performance']['avg_response_time']
if avg_response_time > 2.0:  # 2 second threshold
    print(f"Performance degradation: {avg_response_time}s average")
    exit(1)
```

## Debugging Failed Tests

### Verbose Mode
```bash
python tests/e2e/run_e2e_tests.py --scenario failing_scenario_id --verbose
```

### Analyzing Results
1. Check the scenario result for the failed turn
2. Review expected vs actual values
3. Check conversation history in the full results
4. Verify system logs for the time period

### Common Issues
- **State Mismatch**: FSM didn't transition as expected
- **Agent Mismatch**: Wrong agent handled the request
- **Context Missing**: Expected data not in context
- **Timeout**: Response took too long
- **Validation Failed**: Response didn't match expectations

## Extending the Tests

### Adding New Scenarios

1. Create a new method in the appropriate class:
```python
@staticmethod
def new_test_scenario() -> ConversationScenario:
    return ConversationScenario(
        id="category_###",
        name="New Test",
        # ... scenario definition
    )
```

2. Add to `get_all_scenarios()` function

### Custom Validation Functions

```python
def validate_complex_cart(context):
    cart = context.get("cart", [])
    return (
        len(cart) >= 2 and
        sum(item.get("quantity", 0) for item in cart) > 5
    )

# Use in turn
ConversationTurn(
    expected_context=validate_complex_cart
)
```

## Best Practices

1. **Comprehensive Coverage**: Test all major conversation paths
2. **Realistic Scenarios**: Use actual user patterns
3. **Performance Monitoring**: Track response times
4. **Regular Execution**: Run in CI/CD pipeline
5. **Failure Analysis**: Investigate all failures promptly
6. **Scenario Maintenance**: Update as system evolves

## Performance Considerations

- Default timeout: 30 seconds per turn
- Scenario timeout: 5 minutes (configurable)
- Concurrent execution: Not recommended (state conflicts)
- Mock server: Use for rapid development testing

## Troubleshooting

### WebSocket Connection Failed
- Verify system is running
- Check WebSocket URL configuration
- Ensure no firewall blocking

### State Validation Failures
- Check FSM configuration matches tests
- Verify intent detection prompts
- Review recent FSM changes

### Response Timeouts
- Check system load
- Verify external service availability
- Consider increasing timeout values