# RedBarSushiAI Test Suite

This directory contains comprehensive unit, integration, and end-to-end tests for the RedBarSushiAI voice ordering system.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures and test configuration
├── unit/                # Unit tests for individual components
│   ├── test_models.py   # Database model tests
│   ├── test_agents.py   # AI agent tests
│   ├── test_fsm.py      # Finite State Machine tests
│   ├── test_menu_matching.py  # Menu matching tests
│   └── test_simple.py   # Simple tests for setup verification
├── integration/         # Integration tests
│   ├── test_api_endpoints.py    # API endpoint tests
│   └── test_agent_orchestration.py  # Agent coordination tests
└── e2e/                 # End-to-end tests
    ├── test_complete_voice_flow.py  # Full voice ordering flow
    └── test_websocket_flow.py       # WebSocket communication tests
```

## Running Tests

### Local Development
```bash
# Run all tests
./test.sh

# Run specific test category
python -m pytest tests/unit -v
python -m pytest tests/integration -v
python -m pytest tests/e2e -v

# Run specific test file
python -m pytest tests/unit/test_models.py -v

# Run specific test
python -m pytest tests/unit/test_models.py::TestMenuModels::test_menu_item_creation -v
```

### Docker Environment
```bash
# Run tests in Docker
./test-docker.sh

# Run tests in existing container
./run-tests-docker.sh
```

## Test Categories

### Unit Tests
- **Models**: Test database models, relationships, and data integrity
- **Agents**: Test individual AI agents and their tools
- **FSM**: Test state machine transitions and handlers
- **Menu Matching**: Test fuzzy matching and menu search

### Integration Tests
- **API Endpoints**: Test REST API endpoints with database
- **Agent Orchestration**: Test multi-agent coordination

### E2E Tests
- **Voice Flow**: Test complete ordering flow from call to submission
- **WebSocket**: Test real-time audio streaming

## Key Fixtures

### Database Fixtures
- `db_session`: Async database session for tests
- `sample_menu_data`: Pre-populated menu items for testing
- `sample_location`: Test restaurant location

### Mock Fixtures
- `mock_redis`: Mock Redis client
- `mock_openai_client`: Mock OpenAI API client
- `mock_twilio_client`: Mock Twilio client
- `mock_deliverect_client`: Mock Deliverect API client
- `mock_websocket`: Mock WebSocket connection

## Writing New Tests

### Unit Test Example
```python
@pytest.mark.asyncio
async def test_menu_item_creation(db_session):
    item = MenuItem(
        name="Test Roll",
        price=999,
        plu="TEST_001"
    )
    db_session.add(item)
    await db_session.commit()
    
    assert item.id is not None
    assert item.price_display == "$9.99"
```

### Integration Test Example
```python
@pytest.mark.asyncio
async def test_menu_api(test_client, sample_menu_data):
    response = await test_client.get("/api/menu/items")
    assert response.status_code == 200
    assert len(response.json()) == 3
```

### E2E Test Example
```python
@pytest.mark.asyncio
async def test_complete_order(test_client, mock_deliverect_client):
    # Start call
    response = await test_client.post("/voice/webhook", 
        data={"CallSid": "CA123", "From": "+1234567890"})
    
    # Continue through flow...
    assert response.status_code == 200
```

## Test Configuration

See `pytest.ini` for test configuration including:
- Coverage requirements (70% minimum)
- Test markers
- Timeout settings
- Environment variables

## Continuous Integration

Tests run automatically on:
- Pull requests to staging/main branches
- Pushes to staging branch (all tests)
- Pushes to main branch (all tests)

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure PYTHONPATH includes the app directory
2. **Database Errors**: Tests use SQLite in-memory database by default
3. **Async Errors**: Use `@pytest.mark.asyncio` for async tests
4. **Mock Failures**: Check fixture initialization in conftest.py

### Debug Tips

- Use `-v` for verbose output
- Use `-s` to see print statements
- Use `--tb=short` for shorter tracebacks
- Use `-k` to run specific tests by name pattern