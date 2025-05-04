# Docker Integration Tests for RedBarSushiAI

This comprehensive guide covers how to run and expand integration tests using Docker for the RedBarSushiAI project. Using Docker for integration tests ensures consistent testing environments across development machines and provides more realistic testing conditions than in-memory alternatives.

## Docker Testing Environment

### Environment Setup

The integration test environment is defined in `tests/docker-compose-test.yml` and includes:

1. **PostgreSQL Container (postgres-test)**
   - PostgreSQL 15 Alpine image
   - Configured with test credentials:
     - Database: `test_redbarsushi`
     - Username: `test_user`
     - Password: `test_password`
   - Port 5432 exposed to host
   - Health checks ensure database readiness

2. **Redis Container (redis-test)**
   - Redis Alpine image
   - Port 6379 exposed to host
   - Health checks ensure service availability

This setup allows tests to run against actual database and cache services instead of in-memory alternatives, providing more realistic testing scenarios.

## Running Integration Tests with Docker

### Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ with pip and venv

### Starting the Environment

Start the Docker containers with:

```bash
docker-compose -f tests/docker-compose-test.yml up -d
```

Verify containers are running with:

```bash
docker ps
```

### Running Tests

Use the included script to run all integration tests:

```bash
./run_docker_integration_tests.sh
```

Or run a specific test:

```bash
./run_docker_integration_tests.sh test_menu_db_integration.py
```

Alternatively, run tests manually:

```bash
# Export environment variables for tests
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
export TEST_REDIS_URL="redis://localhost:6379/0"

# Run integration tests
python -m pytest tests/integration/ -v

# Run a specific test
python -m pytest tests/integration/test_menu_db_integration.py -v
```

### Stopping the Environment

Stop and remove the containers when done:

```bash
docker-compose -f tests/docker-compose-test.yml down
```

## Key Integration Tests

The following tests benefit from Docker-based testing:

### 1. Menu Database Integration (`test_menu_db_integration.py`)

This test suite verifies menu data storage and retrieval in PostgreSQL.

**Key tests:**
- Database store initialization
- Menu data migration to database
- Loading menu data from database
- Writing menu data to both database and file
- Updating menu items
- Processing product changes

**Docker benefits:** Tests actual PostgreSQL database operations with real constraints and transaction behavior.

### 2. Redis Caching and Fallback (`test_redis_caching_fallback.py`)

Tests Redis caching mechanisms and fallbacks when Redis is unavailable.

**Key tests:**
- Storing and retrieving menu data from Redis
- Fallback to database when Redis is unavailable
- Cache invalidation
- TTL functionality

**Docker benefits:** Tests with a real Redis instance instead of in-memory mocks, confirming TTL behavior.

### 3. Conversation Store (`test_conversation_store.py`)

Tests conversation state storage in Redis.

**Key tests:**
- Storing and retrieving conversation state
- Session expiration
- Fallback mechanisms
- Concurrency handling

**Docker benefits:** Tests actual Redis operations with real TTL and atomic operations.

### 4. Deliverect API Integration (`test_deliverect_api_integration.py`)

Tests integration with the Deliverect API.

**Key tests:**
- Preparing orders for Deliverect
- Building Deliverect payload
- Submitting orders
- Tracking order status
- Error handling
- Retry mechanisms

**Docker benefits:** While the API itself is still mocked, Docker ensures database operations are realistic.

### 5. Order Processing Workflow (`test_order_processing_workflow.py`)

Tests the end-to-end order processing flow.

**Key tests:**
- Order creation and validation
- Order submission to Deliverect
- Status updates and tracking
- Notification generation
- Error recovery

**Docker benefits:** Tests complex workflows with proper database transactions.

### 6. Menu Synchronization (`test_deliverect_menu_synchronization.py`)

Tests synchronizing menu data with Deliverect.

**Key tests:**
- Processing Deliverect menu format
- Storing menu data in database
- Handling menu updates
- Price changes and variant calculations
- Rollback on failure

**Docker benefits:** Tests database constraints and transaction behavior with realistic data volumes.

## Extending Docker Integration Tests

### 1. Update Test Fixtures

The current `conftest.py` can be enhanced to better use Docker:

```python
@pytest.fixture
def app_with_docker_db(app):
    """
    Create a Flask app with Docker PostgreSQL database.
    """
    from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
    from app.db import db
    
    # Get database URL from environment
    db_url = os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
    )
    
    # Configure app to use Docker PostgreSQL
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Clean existing data
        MenuModifierGroup.query.delete()
        MenuModifier.query.delete()
        MenuItem.query.delete()
        db.session.commit()
        
        yield app
        
        # Clean up after tests
        MenuModifierGroup.query.delete()
        MenuModifier.query.delete()
        MenuItem.query.delete()
        db.session.commit()
```

### 2. Create Docker Redis Fixture

```python
@pytest.fixture
def app_with_docker_redis(app):
    """
    Configure app to use Docker Redis.
    """
    # Get Redis URL from environment
    redis_url = os.environ.get(
        "TEST_REDIS_URL", 
        "redis://localhost:6379/0"
    )
    
    # Configure app to use Docker Redis
    app.config["REDIS_URL"] = redis_url
    app.config["CELERY_BROKER_URL"] = redis_url
    app.config["CELERY_RESULT_BACKEND"] = redis_url
    
    yield app
```

### 3. Create Full Docker Environment Fixture

```python
@pytest.fixture
def app_with_docker(app_with_docker_db, app_with_docker_redis):
    """
    Configure app with both Docker PostgreSQL and Redis.
    """
    return app_with_docker_db
```

### 4. Test Database Connection Resilience

Add tests for database connection retry logic:

```python
def test_db_retry_logic(app_with_docker_db, monkeypatch):
    """Test database connection retry logic."""
    with app_with_docker_db.app_context():
        from app.utils.database import get_menu_items_with_retry
        from sqlalchemy.exc import OperationalError
        
        # Mock a database error that happens twice then succeeds
        call_count = 0
        original_function = db.session.query
        
        def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OperationalError("mock error", None, None)
            return original_function(*args, **kwargs)
        
        monkeypatch.setattr(db.session, "query", mock_query)
        
        # Should successfully get menu items after retries
        result = get_menu_items_with_retry()
        assert call_count == 3
```

### 5. Test Redis Failure Scenarios

Test Redis failure handling:

```python
def test_redis_failure_fallback(app_with_docker, monkeypatch):
    """Test fallback when Redis fails."""
    with app_with_docker.app_context():
        from app.utils.menu_db_store import menu_db_store
        from redis.exceptions import RedisError
        
        # Mock a Redis error
        def mock_redis_get(*args, **kwargs):
            raise RedisError("mock error")
        
        monkeypatch.setattr(menu_db_store.redis_client, "get", mock_redis_get)
        
        # Should fall back to database
        result = menu_db_store.get_menu_data()
        assert result is not None
```

## Best Practices for Docker Integration Tests

1. **Container Health Checks:**
   - The Docker Compose file includes health checks
   - Wait for containers to be healthy before running tests

2. **Test Data Management:**
   - Clean up test data after each test
   - Use transaction rollbacks when possible
   - Ensure tests are isolated from each other

3. **Environmental Awareness:**
   - Read database and Redis URLs from environment variables
   - Allow fallback to default values for local testing

4. **Error Scenario Testing:**
   - Use Docker to test real error scenarios
   - Test connection failures and recovery
   - Test database constraints and transaction behavior

5. **Performance Testing:**
   - Use Docker to test with realistic data volumes
   - Benchmark query performance
   - Test connection pooling

## Troubleshooting

### Port Conflicts

If you already have PostgreSQL or Redis running on your system, you may encounter port conflicts. Change the port mapping in `docker-compose-test.yml`:

```yaml
ports:
  - "5433:5432"  # Map container port 5432 to host port 5433
```

Then update your connection strings:

```
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5433/test_redbarsushi"
```

### Container Health

If tests fail due to container health issues:

```bash
# Check container status
docker ps

# Check container logs
docker logs tests-postgres-test-1
docker logs tests-redis-test-1
```

### Database Connection Issues

If tests can't connect to the database:

1. Verify containers are running:
   ```bash
   docker ps | grep postgres
   ```

2. Check PostgreSQL logs:
   ```bash
   docker logs tests-postgres-test-1
   ```

3. Test connection directly:
   ```bash
   docker exec -it tests-postgres-test-1 psql -U test_user -d test_redbarsushi
   ```

## Future Improvements

1. **Container Orchestration:**
   - Add container startup/shutdown in pytest fixtures
   - Ensure clean test environment for each test run

2. **Docker Network Isolation:**
   - Create dedicated test network
   - Ensure tests don't interfere with other services

3. **Volume Persistence:**
   - Use volumes for test data persistence
   - Speed up repeated test runs

4. **Multi-Container Tests:**
   - Add more services to simulate full environment
   - Test with mock Twilio and OpenAI services

5. **CI/CD Integration:**
   - Run Docker integration tests in CI pipeline
   - Ensure consistent test environment in CI