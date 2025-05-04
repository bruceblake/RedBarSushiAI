# Docker End-to-End (E2E) Tests for RedBarSushiAI

This document outlines how to run and develop end-to-end (E2E) tests using Docker for the RedBarSushiAI system. E2E tests verify complete user workflows and business processes through the entire application stack.

## Docker E2E Testing Environment

E2E tests use a more comprehensive Docker setup than integration tests. The environment includes:

1. **Application Container**
   - Flask application with all dependencies
   - Configured for testing mode
   - Connected to test database and services

2. **PostgreSQL Container**
   - Test database with schema matching production
   - Preloaded with test data for consistent testing

3. **Redis Container**
   - Used for session management and caching
   - Simulates production Redis configuration

4. **Mock API Containers**
   - Mock Twilio service for voice simulation
   - Mock OpenAI service for NLP simulation
   - Mock Deliverect service for order processing simulation

## Setting Up the E2E Environment

### Docker Compose Configuration

The full E2E test environment is defined in `tests/docker-compose-e2e.yml`:

```yaml
version: '3.8'

services:
  app:
    build:
      context: ..
      dockerfile: Dockerfile
    environment:
      - FLASK_APP=run.py
      - FLASK_ENV=testing
      - TESTING=true
      - DATABASE_URL=postgresql://test_user:test_password@postgres/test_redbarsushi
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - TWILIO_BASE_URL=http://mock-twilio:3000
      - OPENAI_BASE_URL=http://mock-openai:3000
      - DELIVERECT_BASE_URL=http://mock-deliverect:3000
    ports:
      - "5000:5000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      mock-twilio:
        condition: service_started
      mock-openai:
        condition: service_started
      mock-deliverect:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/healthcheck"]
      interval: 5s
      timeout: 10s
      retries: 3
      start_period: 5s

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: test_redbarsushi
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./scripts/init_test_db.sql:/docker-entrypoint-initdb.d/init_test_db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_redbarsushi"]
      interval: 1s
      timeout: 3s
      retries: 10

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 1s
      timeout: 3s
      retries: 10

  mock-twilio:
    build:
      context: ./mocks/twilio
      dockerfile: Dockerfile
    ports:
      - "3001:3000"
    volumes:
      - ./mocks/twilio/responses:/app/responses

  mock-openai:
    build:
      context: ./mocks/openai
      dockerfile: Dockerfile
    ports:
      - "3002:3000"
    volumes:
      - ./mocks/openai/responses:/app/responses

  mock-deliverect:
    build:
      context: ./mocks/deliverect
      dockerfile: Dockerfile
    ports:
      - "3003:3000"
    volumes:
      - ./mocks/deliverect/responses:/app/responses
```

### Starting the E2E Environment

Start the E2E testing environment with:

```bash
docker-compose -f tests/docker-compose-e2e.yml up -d
```

Verify all services are running:

```bash
docker-compose -f tests/docker-compose-e2e.yml ps
```

## Running E2E Tests

### Using the E2E Test Runner

The E2E test runner script automates the process:

```bash
./run_e2e_tests.sh
```

This script:
1. Starts the Docker environment if not running
2. Runs database migrations
3. Seeds test data
4. Executes E2E test suites
5. Generates test reports

### Running Specific E2E Tests

To run specific E2E tests:

```bash
# Run all voice flow tests
python -m pytest tests/e2e/test_voice_flow.py -v

# Run a specific test
python -m pytest tests/e2e/test_complete_order_flow_e2e.py::test_end_to_end_order_flow -v
```

## Key E2E Test Suites

### 1. Complete Order Flow (`test_complete_order_flow_e2e.py`)

Tests the full order flow from customer call to order completion.

**Key tests:**
- `test_end_to_end_order_flow`: Complete happy path flow
- `test_order_flow_with_error_recovery`: Tests error recovery
- `test_order_flow_with_timeouts`: Tests timeout handling

**Architecture tested:**
- Voice API endpoints
- NLP processing
- Order creation and validation
- Deliverect integration
- Notification generation

### 2. Voice System Tests (`test_comprehensive_voice_flow.py`)

Tests comprehensive voice interactions with customers.

**Key tests:**
- `test_voice_greeting_flow`: Tests initial greeting flow
- `test_menu_inquiry_flow`: Tests menu questions
- `test_voice_order_flow`: Tests ordering through voice
- `test_voice_error_recovery`: Tests error handling in voice interactions

**Architecture tested:**
- Twilio interaction
- Speech processing
- Conversation state management
- Context preservation

### 3. Silence Handling (`test_silence_handling.py`)

Tests the system's response to customer silence.

**Key tests:**
- `test_initial_silence_handling`: Tests silence at greeting
- `test_progressive_timeouts`: Tests escalating timeout behavior
- `test_silence_fallback_to_dtmf`: Tests fallback to touch-tone input
- `test_silence_recovery`: Tests recovery after silence

**Architecture tested:**
- Timeout detection
- Fallback mechanisms
- Session management
- Graceful recovery

### 4. Error Recovery Flow (`test_error_recovery_flow.py`)

Tests the system's ability to recover from errors.

**Key tests:**
- `test_database_error_recovery`: Tests recovery from database errors
- `test_deliverect_api_error_recovery`: Tests recovery from API errors
- `test_voice_recognition_error_recovery`: Tests recovery from voice processing errors

**Architecture tested:**
- Error detection
- Graceful degradation
- Retry mechanisms
- User feedback

## Mock Services for E2E Testing

### Mock Twilio Service

The mock Twilio service simulates phone interactions:

```javascript
// mocks/twilio/server.js
const express = require('express');
const app = express();
const port = 3000;

app.use(express.json());

// Mock voice endpoint
app.post('/voice', (req, res) => {
  res.set('Content-Type', 'application/xml');
  res.send(`
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Say>Mock Twilio response</Say>
    </Response>
  `);
});

// Mock speech transcription
app.post('/transcription', (req, res) => {
  const { text } = req.body;
  res.json({
    status: 'success',
    transcription: text || 'I want to order sushi'
  });
});

app.listen(port, () => {
  console.log(`Mock Twilio server running on port ${port}`);
});
```

### Mock OpenAI Service

The mock OpenAI service simulates NLP processing:

```javascript
// mocks/openai/server.js
const express = require('express');
const app = express();
const port = 3000;

app.use(express.json());

// Mock completion endpoint
app.post('/v1/chat/completions', (req, res) => {
  const { messages } = req.body;
  const lastMessage = messages[messages.length - 1].content;
  
  let response;
  if (lastMessage.includes('menu')) {
    response = "Our menu includes California Roll, Spicy Tuna, and Dragon Roll.";
  } else if (lastMessage.includes('order')) {
    response = "I'll add that to your order. Would you like anything else?";
  } else {
    response = "I'm here to help with your sushi order. What would you like?";
  }
  
  res.json({
    id: 'mock-completion-id',
    object: 'chat.completion',
    created: Date.now(),
    model: 'gpt-3.5-turbo',
    choices: [
      {
        message: {
          role: 'assistant',
          content: response
        },
        finish_reason: 'stop',
        index: 0
      }
    ]
  });
});

app.listen(port, () => {
  console.log(`Mock OpenAI server running on port ${port}`);
});
```

### Mock Deliverect Service

The mock Deliverect service simulates order processing:

```javascript
// mocks/deliverect/server.js
const express = require('express');
const app = express();
const port = 3000;

app.use(express.json());

// Store orders in memory for the test
const orders = {};

// Mock order creation endpoint
app.post('/:channelName/order/:channelLinkId', (req, res) => {
  const { channelOrderId } = req.body;
  
  if (!channelOrderId) {
    return res.status(400).json({
      error: 'channelOrderId is required'
    });
  }
  
  // Store the order
  orders[channelOrderId] = {
    ...req.body,
    status: 10, // Initial status (received)
    orderId: `mock-order-${Date.now()}`
  };
  
  res.status(201).json({
    status: 'success',
    orderId: orders[channelOrderId].orderId
  });
});

// Mock order status endpoint
app.get('/:channelName/order/:channelLinkId/:channelOrderId', (req, res) => {
  const { channelOrderId } = req.params;
  
  if (!orders[channelOrderId]) {
    return res.status(404).json({
      error: 'Order not found'
    });
  }
  
  // Auto-advance status for testing
  const currentTime = Date.now();
  const orderTime = parseInt(orders[channelOrderId].orderId.split('-')[2]);
  const minutesPassed = (currentTime - orderTime) / 60000;
  
  let status = 10; // Received
  if (minutesPassed > 1) status = 20; // Accepted
  if (minutesPassed > 2) status = 30; // In Preparation
  if (minutesPassed > 3) status = 70; // Ready for Pickup
  if (minutesPassed > 5) status = 80; // Delivered
  
  orders[channelOrderId].status = status;
  
  res.json({
    orderId: orders[channelOrderId].orderId,
    status: orders[channelOrderId].status,
    channelOrderId,
    location: 'mock-location',
    channelLink: 'mock-channel-link'
  });
});

app.listen(port, () => {
  console.log(`Mock Deliverect server running on port ${port}`);
});
```

## Writing Effective E2E Tests

### 1. Test Complete User Flows

Focus on testing complete user journeys from start to finish:

```python
def test_end_to_end_order_flow(docker_client):
    """Test a complete order flow from call to completion."""
    # Simulate incoming call
    response = docker_client.post('/webhook/voice', data={
        'CallSid': 'TEST-E2E-CALL-123',
        'From': '+15551234567'
    })
    assert response.status_code == 200
    
    # Simulate customer name input
    response = docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-E2E-CALL-123',
        'SpeechResult': 'My name is John',
        'Confidence': '0.9'
    })
    assert response.status_code == 200
    
    # Simulate order input
    response = docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-E2E-CALL-123',
        'SpeechResult': 'I want to order a California Roll with extra avocado',
        'Confidence': '0.9'
    })
    assert response.status_code == 200
    
    # Simulate confirmation
    response = docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-E2E-CALL-123',
        'SpeechResult': 'Yes, that is correct',
        'Confidence': '0.9'
    })
    assert response.status_code == 200
    
    # Check order was created in database
    with docker_client.application.app_context():
        from app.models.order import Order
        order = Order.query.filter_by(customer_phone='+15551234567').first()
        assert order is not None
        assert order.status == 10  # Initial status
        
        # Check order has correct items
        assert len(order.items) == 1
        assert order.items[0].menu_item_plu == 'CALI-ROLL'
        assert len(order.items[0].modifiers) == 1
        assert order.items[0].modifiers[0].modifier_plu == 'EXTRA-AVO'
```

### 2. Use Scenario-Based Testing

Organize tests around realistic scenarios:

```python
def test_comprehensive_voice_flow(docker_client):
    """Test a realistic conversation with menu questions and ordering."""
    # Conversation flow:
    # 1. Greeting
    # 2. Ask about menu
    # 3. Place order
    # 4. Confirm order
    
    # Initialize call
    init_response = docker_client.post('/webhook/voice', data={
        'CallSid': 'TEST-SCENARIO-123',
        'From': '+15551234567'
    })
    assert init_response.status_code == 200
    
    # Provide name
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-SCENARIO-123',
        'SpeechResult': 'My name is Sarah',
        'Confidence': '0.9'
    })
    
    # Ask about menu
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-SCENARIO-123',
        'SpeechResult': 'Tell me about your sushi rolls',
        'Confidence': '0.9'
    })
    
    # Ask specific question
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-SCENARIO-123',
        'SpeechResult': 'What\'s in the Dragon Roll?',
        'Confidence': '0.9'
    })
    
    # Place order
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-SCENARIO-123',
        'SpeechResult': 'I\'d like to order the Dragon Roll and a Miso Soup',
        'Confidence': '0.9'
    })
    
    # Confirm order
    final_response = docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-SCENARIO-123',
        'SpeechResult': 'Yes, that\'s correct',
        'Confidence': '0.9'
    })
    
    # Check conversation store
    with docker_client.application.app_context():
        from app.utils.conversation_store import ConversationStore
        cs = ConversationStore()
        conversation = cs.get_conversation('TEST-SCENARIO-123')
        assert conversation is not None
        assert conversation['state'] == 'order_completed'
        
        # Check order was created
        from app.models.order import Order
        order = Order.query.filter_by(customer_phone='+15551234567').order_by(Order.id.desc()).first()
        assert order is not None
        assert len(order.items) == 2
```

### 3. Test Error Scenarios

Include tests for error handling and recovery:

```python
def test_error_recovery_flow(docker_client, monkeypatch):
    """Test recovery from errors during the order process."""
    # Set up call
    docker_client.post('/webhook/voice', data={
        'CallSid': 'TEST-ERROR-123',
        'From': '+15551234567'
    })
    
    # Provide name
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-ERROR-123',
        'SpeechResult': 'My name is Error Tester',
        'Confidence': '0.9'
    })
    
    # Simulate database error during menu query
    with docker_client.application.app_context():
        from app.utils.menu_db_store import menu_db_store
        from sqlalchemy.exc import OperationalError
        
        # Mock database error that occurs only once
        original_query = menu_db_store.get_menu_item_by_plu
        call_count = 0
        
        def mock_error_query(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                raise OperationalError("Test error", None, None)
            return original_query(*args, **kwargs)
        
        monkeypatch.setattr(menu_db_store, "get_menu_item_by_plu", mock_error_query)
    
    # Place order (should trigger the error and recovery)
    response = docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-ERROR-123',
        'SpeechResult': 'I want to order a California Roll',
        'Confidence': '0.9'
    })
    
    # System should recover and still process the order
    assert response.status_code == 200
    
    # Confirm order
    docker_client.post('/webhook/voice/input', data={
        'CallSid': 'TEST-ERROR-123',
        'SpeechResult': 'Yes, correct',
        'Confidence': '0.9'
    })
    
    # Verify order was created despite the error
    with docker_client.application.app_context():
        from app.models.order import Order
        order = Order.query.filter_by(customer_phone='+15551234567').order_by(Order.id.desc()).first()
        assert order is not None
        assert len(order.items) == 1
        assert order.items[0].menu_item_plu == 'CALI-ROLL'
```

## Best Practices for Docker E2E Tests

1. **Isolated Test Environment**
   - Each test should run in isolation
   - Reset state between tests
   - Use unique identifiers for test data

2. **Realistic Data Flows**
   - Test realistic user journeys
   - Include both happy paths and error scenarios
   - Test timing-dependent operations

3. **Component Interaction**
   - Test interactions between all components
   - Verify database state after operations
   - Check for side effects

4. **Performance Considerations**
   - Keep tests focused and efficient
   - Parallelize independent tests
   - Use fixtures to reduce setup time

5. **Maintainable Test Code**
   - Use descriptive test names
   - Document test scenarios
   - Keep assertions clear and specific

## Troubleshooting E2E Tests

### Common Issues

1. **Container Startup Issues**
   - Check container logs: `docker-compose -f tests/docker-compose-e2e.yml logs app`
   - Verify health checks are passing
   - Check for port conflicts

2. **Test Failures**
   - Review test logs for specific failure points
   - Check container logs for errors
   - Verify mock services are responding correctly

3. **Timing Issues**
   - Add explicit waits for asynchronous operations
   - Ensure containers are fully initialized before tests
   - Check for race conditions in tests

### Resetting the Environment

If tests are failing consistently, reset the environment:

```bash
# Stop all containers
docker-compose -f tests/docker-compose-e2e.yml down

# Remove volumes to clear persistent data
docker-compose -f tests/docker-compose-e2e.yml down -v

# Rebuild images
docker-compose -f tests/docker-compose-e2e.yml build

# Start fresh environment
docker-compose -f tests/docker-compose-e2e.yml up -d
```

## Future Enhancements

1. **Parallelized Testing**
   - Run tests in parallel for faster execution
   - Use separate database schemas for parallel tests

2. **Video Recording**
   - Record test execution for debugging
   - Capture screenshots at key points

3. **Load Testing**
   - Add load tests for concurrent users
   - Test system performance under load

4. **CI/CD Integration**
   - Run E2E tests in CI pipeline
   - Gate deployments on E2E test results

5. **Test Data Management**
   - Develop comprehensive test data sets
   - Create data generators for edge cases