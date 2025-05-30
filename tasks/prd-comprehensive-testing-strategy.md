# PRD: Comprehensive Testing Strategy for RedBarSushiAI

## Introduction/Overview

This PRD outlines a comprehensive testing strategy for the RedBarSushiAI voice ordering system. The goal is to implement thorough testing at all levels (unit, integration, and end-to-end) to ensure system reliability, correctness, and maintainability. Tests will leverage the existing Docker infrastructure with real PostgreSQL and Redis services to provide realistic testing conditions.

## Goals

1. Achieve >90% code coverage across all application modules
2. Validate all agent behaviors and interactions in isolation and as a system
3. Ensure FSM state transitions are correct and handle all edge cases
4. Verify data consistency between PostgreSQL and Redis under various conditions
5. Test complete conversation flows from initial greeting to order completion
6. Validate menu update processing and cache synchronization
7. Ensure system resilience to failures and error conditions
8. Provide fast feedback to developers during development

## User Stories

1. **As a developer**, I want to run unit tests quickly to verify individual components work correctly, so that I can catch bugs early in development.

2. **As a developer**, I want integration tests to verify that agents communicate properly with each other and with external services, so that I can ensure system components work together.

3. **As a QA engineer**, I want end-to-end tests that simulate real customer interactions, so that I can verify the entire system works as expected from a user's perspective.

4. **As a DevOps engineer**, I want all tests to run in Docker containers, so that I can ensure consistent test execution across different environments.

5. **As a team lead**, I want comprehensive test reports showing coverage and failure details, so that I can track code quality over time.

## Functional Requirements

### 1. Test Infrastructure
1.1. The system must provide separate test configurations for unit, integration, and E2E tests
1.2. The system must use real PostgreSQL and Redis instances running in Docker containers
1.3. The system must support parallel test execution where possible
1.4. The system must provide detailed logging for test failures
1.5. The system must clean up test data after each test run

### 2. Unit Tests
2.1. The system must test each agent class (BaseAsyncAgent, MenuAgent, CartAgent, etc.) individually
2.2. The system must test FSM state transitions and event handling
2.3. The system must test utility functions (menu matching, text normalization, etc.)
2.4. The system must test database models and CRUD operations
2.5. The system must test Redis operations (get, set, delete, pub/sub)
2.6. The system must mock external API calls (OpenAI, Twilio, Deliverect) for unit tests

### 3. Integration Tests
3.1. The system must test agent-to-agent communication and handoffs
3.2. The system must test FSM with real state persistence in Redis
3.3. The system must test menu synchronization between Deliverect webhooks and database
3.4. The system must test conversation state management across multiple interactions
3.5. The system must test database transactions and rollback scenarios
3.6. The system must test Redis cache invalidation and synchronization
3.7. The system must test WebSocket connection handling and message flow
3.8. The system must test concurrent operations and race conditions

### 4. End-to-End Tests
4.1. The system must test complete conversation flows from greeting to order submission
4.2. The system must test voice call handling via Twilio webhooks
4.3. The system must test WebSocket audio streaming with simulated audio data
4.4. The system must test order validation and submission to Deliverect
4.5. The system must test error recovery scenarios (service restarts, network failures)
4.6. The system must test multiple concurrent conversations
4.7. The system must test menu updates during active conversations
4.8. The system must test escalation flows to human agents

### 5. Test Data Management
5.1. The system must provide fixtures for menu items, modifiers, and categories
5.2. The system must create test locations with Deliverect credentials
5.3. The system must generate test orders with various configurations
5.4. The system must reset database state between test runs
5.5. The system must provide tools to inspect database and Redis state during test debugging

### 6. Test Execution
6.1. The system must provide separate commands for running unit, integration, and E2E tests
6.2. The system must support running all tests with a single command
6.3. The system must generate test coverage reports in HTML and XML formats
6.4. The system must support test filtering by name, module, or marker
6.5. The system must provide verbose output mode for debugging
6.6. The system must capture and display test execution time

### 7. Test Reporting
7.1. The system must generate JUnit-compatible XML reports for CI/CD integration
7.2. The system must provide code coverage reports with line-by-line details
7.3. The system must highlight slow tests (>1 second for unit, >5 seconds for integration)
7.4. The system must save test logs and artifacts for failed tests
7.5. The system must provide a summary report showing pass/fail counts and coverage

## Non-Goals (Out of Scope)

1. Performance/load testing (this will be a separate PRD)
2. Security/penetration testing
3. UI/frontend testing (API only)
4. Testing of actual third-party services (will use mocks/stubs)
5. Cross-browser compatibility testing
6. Mobile app testing

## Design Considerations

### Test Structure
```
tests/
├── unit/
│   ├── agents/
│   │   ├── test_base_agent.py
│   │   ├── test_menu_agent.py
│   │   ├── test_cart_agent.py
│   │   └── ...
│   ├── fsm/
│   │   ├── test_core.py
│   │   ├── test_handlers.py
│   │   └── test_transitions.py
│   ├── utils/
│   │   ├── test_menu_matcher.py
│   │   ├── test_conversation_store.py
│   │   └── ...
│   └── models/
│       ├── test_menu_models.py
│       └── test_order_models.py
├── integration/
│   ├── test_agent_orchestration.py
│   ├── test_menu_synchronization.py
│   ├── test_redis_operations.py
│   ├── test_websocket_flow.py
│   └── test_database_transactions.py
├── e2e/
│   ├── test_complete_order_flow.py
│   ├── test_voice_conversation.py
│   ├── test_error_recovery.py
│   ├── test_concurrent_conversations.py
│   └── test_menu_update_during_conversation.py
├── fixtures/
│   ├── menu_data.py
│   ├── order_data.py
│   └── conversation_data.py
└── conftest.py
```

### Docker Configuration
- Separate `docker-compose.test.yml` for test environment
- Test-specific database and Redis instances
- Volume mounts for test code and results
- Environment variables for test configuration

## Technical Considerations

1. **Test Isolation**: Each test should be independent and not rely on the state from previous tests
2. **Database Migrations**: Tests should run migrations automatically before test execution
3. **Async Testing**: Use `pytest-asyncio` for testing async functions and methods
4. **Mock Management**: Use `pytest-mock` for creating mocks and spies
5. **Fixture Reuse**: Create reusable fixtures for common test data and setups
6. **Parallel Execution**: Use `pytest-xdist` for parallel test execution where safe
7. **Time Handling**: Mock time-dependent operations for deterministic tests
8. **Random Data**: Use fixed seeds for any random data generation

## Success Metrics

1. **Code Coverage**: Achieve and maintain >90% code coverage
2. **Test Execution Time**: 
   - Unit tests complete in <2 minutes
   - Integration tests complete in <5 minutes
   - E2E tests complete in <10 minutes
   - Full suite completes in <15 minutes
3. **Test Reliability**: <1% test flakiness rate
4. **Bug Detection**: >80% of bugs caught by tests before production
5. **Developer Productivity**: <5 minutes to run relevant tests during development
6. **CI/CD Integration**: All tests passing required for deployment

## Open Questions

1. Should we implement contract testing for the Deliverect and Twilio integrations?
2. Do we need to test different PostgreSQL and Redis versions for compatibility?
3. Should we add mutation testing to verify test effectiveness?
4. Do we need to test specific voice codecs and audio formats?
5. Should we implement visual regression testing for any generated reports?
6. How should we handle testing of time-sensitive features (e.g., business hours)?
7. Should we add benchmarking tests to track performance over time?
8. Do we need to test database backup and restore procedures?