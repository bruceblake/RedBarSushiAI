# Docker Testing Guide

This guide explains how to run the comprehensive test suite using Docker.

## Prerequisites

- Docker and Docker Compose installed
- `.env` file with required API keys (OPENAI_API_KEY at minimum)

## Running Tests

### Quick Start

Run all tests:
```bash
./run-docker-tests.sh
```

### Running Specific Test Categories

**Unit tests only:**
```bash
./run-docker-tests.sh unit
```

**Integration tests only:**
```bash
./run-docker-tests.sh integration
```

**E2E tests only:**
```bash
./run-docker-tests.sh e2e
```

**Specific test file:**
```bash
./run-docker-tests.sh specific tests/unit/test_fsm_core.py
```

### Docker Compose Commands

**Run tests with docker-compose directly:**
```bash
docker-compose --profile test run --rm test
```

**Run tests and keep services running:**
```bash
KEEP_SERVICES=true ./run-docker-tests.sh
```

**View test logs:**
```bash
docker-compose logs test
```

## Test Environment

The test service uses:
- **Database**: `redbarsushi_test` (separate from main database)
- **Redis**: DB 2 for app, DB 3 for Celery (separate from main Redis DBs)
- **Environment**: `TESTING=true` and `FASTAPI_ENV=testing`

## Test Structure

```
tests/
├── unit/                    # Fast, isolated unit tests
│   ├── test_fsm_core.py     # FSM state transitions
│   ├── test_intent_detector.py  # LLM-based intent detection
│   ├── test_agents.py       # Individual agent behavior
│   └── test_menu_matcher.py # Menu matching logic
├── integration/             # Tests with real services
│   ├── test_agent_orchestration.py  # Agent coordination
│   ├── test_voice_flow.py   # Voice processing pipeline
│   └── test_database_operations.py # DB operations
└── e2e/                     # Full system tests
    ├── test_complete_order_flow.py  # End-to-end ordering
    ├── test_websocket_connection.py # WebSocket handling
    └── test_deliverect_integration.py # POS integration
```

## Coverage Reports

Tests are run with coverage by default. View coverage report:
```bash
docker-compose --profile test run --rm test pytest --cov=app --cov-report=html
```

Then open `htmlcov/index.html` in a browser.

## Debugging Failed Tests

**Run with verbose output:**
```bash
docker-compose --profile test run --rm test pytest -vv -s
```

**Run with debugging:**
```bash
docker-compose --profile test run --rm test pytest --pdb
```

**View detailed logs:**
```bash
docker-compose logs -f postgres redis test
```

## Environment Variables for Testing

Key environment variables used in tests:
- `TESTING=true` - Enables test mode
- `TEST_DATABASE_URL` - Test database connection
- `OPENAI_API_KEY` - Required for LLM-based tests
- `MOCK_EXTERNAL_APIS=true` - Mock external services (optional)

## CI/CD Integration

The same Docker setup can be used in CI/CD:
```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    docker-compose --profile test run --rm test
```

## Troubleshooting

**Tests fail with database connection errors:**
- Ensure PostgreSQL is healthy: `docker-compose ps`
- Check test database exists: `docker-compose exec postgres psql -U postgres -l`

**Tests fail with Redis connection errors:**
- Ensure Redis is healthy: `docker-compose exec redis redis-cli ping`

**Tests hang or timeout:**
- Check for proper async/await usage
- Ensure WebSocket connections are properly closed
- Review asyncio task management