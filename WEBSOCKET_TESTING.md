# WebSocket Testing Suite for RedBarSushiAI

This comprehensive testing suite verifies the reliability and stability of WebSocket connections in the RedBarSushiAI system, with a focus on preventing the disconnection issues that were occurring after the greeting.

## Available Tests

The suite includes several testing tools:

1. **WebSocket Stability Test** (`websocket_stability_client.py`) - Tests the stability of a single WebSocket connection over time, particularly after the greeting phase.

2. **WebSocket Failure Mode Tests** (`test_failure_modes.py`) - Tests the system's resilience against various failure scenarios:
   - Network latency (200ms, 500ms)
   - Packet loss (10%, 30%)
   - Long communication pauses (5s, 10s)  
   - High concurrent load (multiple connections)
   - Connection reconnection

3. **Fix Verification** (`verify_websocket_fixes.py`) - Verifies that all of the necessary fixes have been properly implemented in the codebase.

4. **WebSocket Test Server** (`websocket_test_server.py`) - A simple server that simulates the RedBarSushiAI WebSocket implementation for local testing.

5. **Complete Test Runner** (`run_websocket_tests.py`) - Runs all tests and generates a comprehensive HTML and JSON report.

## Setup and Requirements

Before running the tests, make sure you have the required dependencies installed:

```bash
# Activate your virtual environment
source ~/websocket_test_env/bin/activate  # or your preferred environment

# Install required packages
pip install websockets flask flask-sock gunicorn gevent gevent-websocket
```

## Running the Tests

### Complete Test Suite

To run the complete test suite with the local test server:

```bash
python run_websocket_tests.py
```

This will:
1. Start a local WebSocket test server
2. Run the fix verification
3. Run the stability test 
4. Run all failure mode tests
5. Generate a comprehensive report

To test against a remote server:

```bash
python run_websocket_tests.py --url wss://redbarsushiai-staging.onrender.com/ws/voice/media
```

### Individual Tests

You can also run individual tests:

#### 1. WebSocket Stability Test

```bash
# Test against local server
python websocket_stability_client.py

# Test against remote server
python websocket_stability_client.py --url wss://redbarsushiai-staging.onrender.com/ws/voice/media --duration 120
```

#### 2. Failure Mode Tests

```bash
# Test against local server
python test_failure_modes.py

# Test against remote server
python test_failure_modes.py --url wss://redbarsushiai-staging.onrender.com/ws/voice/media
```

#### 3. Fix Verification

```bash
python verify_websocket_fixes.py
```

#### 4. Start Test Server

```bash
python websocket_test_server.py
```

Then visit http://localhost:5000 in your browser to test interactively.

## Interpreting Results

After running the complete test suite, you'll find two report files:

- **websocket_test_report.html** - A human-readable HTML report with test results and metrics
- **websocket_test_report.json** - A machine-readable JSON report with detailed test data

The report includes:

- Fix verification results
- Stability test metrics
- Failure mode test results
- Overall reliability assessment

## Test Coverage

The tests verify the following aspects:

1. **Fix Implementation**:
   - Route registration conflict resolution
   - Graceful worker shutdown configuration
   - Multiple keep-alive message implementation
   - TwiML pause configuration
   - Task garbage collection prevention

2. **Stability**:
   - Connection stays open after greeting
   - Multiple keep-alive messages are received
   - System responds to user messages after silence periods

3. **Resilience**:
   - System handles network latency
   - System handles packet loss
   - System maintains connection during long pauses
   - System handles multiple concurrent connections
   - System handles reconnection attempts

## Potential Failure Modes

Even with all fixes implemented, WebSocket connections can still fail due to:

1. **Network Issues**:
   - Intermittent connectivity
   - Excessive latency (>1000ms)
   - Severe packet loss (>50%)
   - Network provider middleboxes terminating idle connections

2. **Server Issues**:
   - Memory exhaustion under heavy load
   - CPU saturation affecting response times
   - Resource leaks in long-running connections
   - Worker processes being recycled

3. **Client Issues**:
   - Client-side timeout settings
   - Browser or WebSocket client implementation differences
   - Mobile network connection switching

4. **Infrastructure Issues**:
   - Load balancer timeout settings
   - Reverse proxy configuration
   - Firewall rules affecting WebSocket traffic

## Monitoring Recommendations

To ensure WebSocket stability in production, consider monitoring:

1. WebSocket connection duration metrics
2. Rate of connections that drop after greeting
3. Server-side resource usage during calls
4. Worker process lifecycle events

## Acknowledgements

This test suite was created to address WebSocket disconnection issues in the RedBarSushiAI voice ordering system. It leverages best practices for testing real-time communication systems with a focus on stability and reliability under various conditions.