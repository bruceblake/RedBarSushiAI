# Comprehensive Testing with Docker for RedBarSushiAI

This guide provides a comprehensive overview of testing the RedBarSushiAI system using Docker, covering integration and end-to-end (E2E) testing approaches.

## Benefits of Docker-Based Testing

Using Docker for testing provides several key advantages:

1. **Consistent Environments:** Tests run in the same environment regardless of the developer's machine
2. **Isolation:** Tests run in isolated containers without affecting the host system
3. **Realistic Testing:** Tests interact with actual database and cache services
4. **Reproducibility:** Environment configuration is version-controlled
5. **Parallel Testing:** Multiple test environments can run concurrently
6. **CI/CD Integration:** Docker-based tests integrate easily with CI/CD pipelines

## Docker Testing Architecture

The RedBarSushiAI testing architecture uses Docker at two levels:

### 1. Integration Testing

Integration tests verify that components work together correctly. The Docker setup includes:

- **PostgreSQL container:** For database integration tests
- **Redis container:** For caching and session management tests

### 2. End-to-End Testing

E2E tests verify complete user workflows. The Docker setup includes:

- **Application container:** Running the full application
- **PostgreSQL container:** For database operations
- **Redis container:** For caching and session management
- **Mock service containers:** For external service simulation
  - Mock Twilio service
  - Mock OpenAI service
  - Mock Deliverect service

## Test Organization

Tests are organized into three categories:

1. **Unit Tests:** Tests for individual components (no Docker required)
2. **Integration Tests:** Tests for component interactions (uses Docker PostgreSQL and Redis)
3. **E2E Tests:** Tests for complete workflows (uses full Docker environment)

## Integration Testing with Docker

### Setting Up Integration Test Environment

Start the integration test environment:

```bash
docker-compose -f tests/docker-compose-test.yml up -d
```

This starts PostgreSQL and Redis containers configured for testing.

### Running Integration Tests

Run integration tests with:

```bash
./run_docker_integration_tests.sh
```

Or manually:

```bash
# Set environment variables
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
export TEST_REDIS_URL="redis://localhost:6379/0"

# Run tests
pytest tests/integration/
```

### Key Integration Test Areas

1. **Database Operations**
   - Menu data storage and retrieval
   - Order processing
   - Database transaction handling
   - Error recovery

2. **Redis Operations**
   - Caching mechanisms
   - Session management
   - TTL functionality
   - Failure handling

3. **Service Integration**
   - Deliverect API integration
   - Menu synchronization
   - Order submission and tracking

## End-to-End Testing with Docker

### Setting Up E2E Test Environment

Start the E2E test environment:

```bash
docker-compose -f tests/docker-compose-e2e.yml up -d
```

This starts a complete environment with the application and all required services.

### Running E2E Tests

Run E2E tests with:

```bash
./run_e2e_tests.sh
```

Or manually:

```bash
# Run all E2E tests
pytest tests/e2e/

# Run specific E2E test
pytest tests/e2e/test_complete_order_flow_e2e.py
```

### Key E2E Test Areas

1. **Order Processing**
   - Complete order workflow
   - Order validation
   - Payment processing
   - Order tracking

2. **Voice Interaction**
   - Phone call handling
   - Speech recognition
   - Conversation flow
   - Silence handling
   - Error recovery

3. **Menu Interaction**
   - Menu inquiries
   - Item availability
   - Modifier selection
   - Price calculation

## Example Test Code

### Integration Test Example

```python
def test_redis_caching(docker_app, test_menu_data):
    """
    Test Redis caching operations using the Docker Redis instance.
    """
    with docker_app.app_context():
        # Store menu data in Redis
        menu_db_store.store_menu_data(test_menu_data)
        
        # Retrieve menu data from Redis
        retrieved_data = menu_db_store.get_menu_data()
        
        assert len(retrieved_data["items"]) == len(test_menu_data["items"])
        assert retrieved_data["items"][0]["name"] == test_menu_data["items"][0]["name"]
        
        # Test TTL functionality
        test_key = "docker:test:ttl"
        menu_db_store.redis_client.set(test_key, "test value", ex=2)
        
        # Verify key exists
        assert menu_db_store.redis_client.get(test_key) == "test value"
        
        # Wait for expiration
        time.sleep(3)
        
        # Verify key has expired
        assert menu_db_store.redis_client.get(test_key) is None
```

### E2E Test Example

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

## Test Fixtures and Utilities

### Integration Test Fixtures

```python
@pytest.fixture
def docker_db_app(app):
    """Configure app to use Docker PostgreSQL."""
    # Get database URL from environment
    db_url = os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
    )
    
    # Configure app to use Docker database
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    
    # Initialize database
    with app.app_context():
        from app import db
        db.create_all()
        
        # Clear existing data
        # ...
        
        yield app
        
        # Clean up after tests
        # ...
```

### E2E Test Client

```python
@pytest.fixture
def docker_client(app_with_docker):
    """Create a test client for the Flask app configured with Docker services."""
    return app_with_docker.test_client()
```

## Best Practices for Docker Testing

### 1. Container Management

- Use health checks to ensure containers are ready
- Clean up containers and volumes after tests
- Use unique container names to avoid conflicts

### 2. Test Data Management

- Initialize test data in fixtures
- Clean up test data after tests
- Use transactions to isolate tests

### 3. Test Structure

- Organize tests by functionality
- Use descriptive test names
- Document test scenarios
- Include both happy paths and error scenarios

### 4. Test Environment

- Configure environment variables for testing
- Use consistent ports across environments
- Document environment setup

### 5. Test Execution

- Run tests in a specific order when needed
- Handle timing-dependent operations
- Document test execution steps

## Continuous Integration (CI) Integration

### GitHub Actions Configuration

```yaml
name: Docker Integration Tests

on:
  push:
    branches: [ main, staging ]
  pull_request:
    branches: [ main ]

jobs:
  integration_tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Docker
        uses: docker/setup-buildx-action@v1
      
      - name: Start Docker containers
        run: docker-compose -f tests/docker-compose-test.yml up -d
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Wait for containers to be healthy
        run: |
          sleep 10
          docker ps
      
      - name: Run integration tests
        run: |
          export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
          export TEST_REDIS_URL="redis://localhost:6379/0"
          pytest tests/integration/
```

## Troubleshooting

### Connection Issues

If tests can't connect to Docker services:

1. Check container status: `docker ps`
2. Verify ports are correctly mapped
3. Check container logs: `docker logs tests-postgres-test-1`
4. Check connection strings in test configuration

### Test Failures

If tests fail:

1. Check test logs for error messages
2. Verify test data is correctly initialized
3. Ensure containers are healthy before tests run
4. Check for timing issues in async operations

### Container Management

To reset the testing environment:

```bash
# Stop containers
docker-compose -f tests/docker-compose-test.yml down

# Remove volumes (clears data)
docker-compose -f tests/docker-compose-test.yml down -v

# Start fresh containers
docker-compose -f tests/docker-compose-test.yml up -d
```

## Conclusion

Docker-based testing provides a robust, consistent environment for verifying the RedBarSushiAI system's functionality. By combining integration and E2E tests with Docker, you can ensure the system works correctly across all components and services.

For detailed information, see:
- [Docker Integration Tests Guide](DOCKER_INTEGRATION_TESTS_GUIDE.md)
- [Docker E2E Tests](DOCKER_E2E_TESTS.md)
- [Integration Tests README](tests/integration/README.md)
- [E2E Tests README](tests/e2e/README.md)