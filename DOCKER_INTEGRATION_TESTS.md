# Docker Integration Tests for RedBarSushiAI

This document provides instructions for running and writing integration tests using Docker for the RedBarSushiAI system.

## Overview

The integration tests use Docker containers to provide isolated, reproducible environments for testing database interactions and other external dependencies. The tests run against:

- **PostgreSQL**: A containerized PostgreSQL database for testing database interactions
- **Redis**: A containerized Redis instance for testing caching and session management

These Docker containers provide consistent environments across different development machines, making tests more reliable and predictable.

## Prerequisites

- Docker and Docker Compose installed on your system
- Python 3.8+ and pip

## Running Integration Tests

### Using the Script

The simplest way to run the integration tests is to use the provided script:

```bash
# Run all integration tests
./run_docker_integration_tests.sh

# Run a specific test file
./run_docker_integration_tests.sh test_menu_db_integration.py
```

The script will:
1. Start the required Docker containers
2. Ensure the containers are healthy
3. Set up the necessary environment variables
4. Activate a virtual environment
5. Run the specified tests
6. Ask if you want to stop the containers when done

### Manual Execution

If you prefer to run tests manually:

1. **Start the Docker containers**:
   ```bash
   docker-compose -f tests/docker-compose-test.yml up -d
   ```

2. **Run the tests**:
   ```bash
   # Set environment variables
   export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
   export TEST_REDIS_URL="redis://localhost:6379/0"
   
   # Run tests
   pytest tests/integration/
   ```

3. **Stop the containers when done**:
   ```bash
   docker-compose -f tests/docker-compose-test.yml down
   ```

## Writing Integration Tests

When writing integration tests that use Docker containers, follow these guidelines:

### 1. Use the Correct Fixtures

The `conftest.py` file in the integration test directory provides several useful fixtures:

- `app`: A Flask app with in-memory SQLite for fast tests
- `app_with_db`: A Flask app with a real PostgreSQL database for more realistic tests
- `flask_client`: A test client for the Flask app
- `mock_deliverect`: Mocks the Deliverect API
- Various fixtures for test data

Use these fixtures in your test functions:

```python
def test_menu_db_store_initialization(app_with_db):
    """Test that the menu_db_store initializes correctly."""
    with app_with_db.app_context():
        # Your test code here
        assert menu_db_store.initialized is True
```

### 2. Clean Up After Tests

Ensure your tests clean up any data they create:

```python
@pytest.fixture
def app_with_db(app):
    """Set up the app with an initialized database."""
    with app.app_context():
        # Create tables if they don't exist
        from app import db
        
        db.create_all()
        
        # Clear existing data
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

### 3. Test Database Interactions Thoroughly

Since you're using real databases, test various database interactions:

- **Create**: Test creating records in the database
- **Read**: Test retrieving records from the database
- **Update**: Test updating existing records
- **Delete**: Test deleting records
- **Relationships**: Test that relationships between models work correctly
- **Constraints**: Test that database constraints are enforced
- **Transactions**: Test that transactions work correctly (commit and rollback)

### 4. Test Failure Scenarios

Test what happens when operations fail:

- Database connection failures
- Constraint violations
- Invalid data
- Concurrent updates
- Transaction rollbacks

### 5. Use Transactions for Test Isolation

Use database transactions to isolate tests from each other:

```python
def test_something(app_with_db):
    with app_with_db.app_context():
        from app import db
        
        try:
            # Your test code here
            
            # Only commit if you want changes to persist
            # db.session.commit()
        finally:
            # Roll back any uncommitted changes
            db.session.rollback()
```

## Test Organization

Organize your integration tests by functionality:

- `test_menu_db_integration.py`: Tests for menu database integration
- `test_deliverect_api_integration.py`: Tests for Deliverect API integration
- `test_deliverect_menu_synchronization.py`: Tests for menu synchronization
- `test_deliverect_price_handling.py`: Tests for price handling
- `test_snooze_functionality.py`: Tests for snooze/unsnooze functionality

## Troubleshooting

### Container Health Checks

The Docker Compose file includes health checks for both PostgreSQL and Redis:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U test_user -d test_redbarsushi"]
  interval: 1s
  timeout: 3s
  retries: 10
```

If tests fail because containers are not healthy, you can check their status:

```bash
docker ps
docker logs tests-postgres-test-1
docker logs tests-redis-test-1
```

### Port Conflicts

If you already have PostgreSQL or Redis running on your machine, you may encounter port conflicts. You can change the exposed ports in the Docker Compose file:

```yaml
ports:
  - "5433:5432"  # Map host port 5433 to container port 5432
```

### Database Connection Issues

If tests fail to connect to the database, check:

1. The database URL in your test code
2. The database container is running
3. The database container is healthy
4. The database is accessible from your host

## Contributing New Tests

When adding new integration tests:

1. Create a new file in `tests/integration/` with a descriptive name
2. Use appropriate fixtures from `conftest.py`
3. Follow the testing best practices outlined above
4. Update this documentation if you add new functionality or requirements