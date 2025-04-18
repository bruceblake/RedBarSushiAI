# Testing Guide for RedBarSushiAI

This document outlines the testing strategies and procedures for the RedBarSushiAI project.

## Testing Levels

We implement multiple testing levels to ensure application quality:

1. **Unit Tests**: Tests individual components in isolation
2. **Integration Tests**: Tests interactions between components
3. **End-to-End Tests**: Tests complete user flows using Playwright

## Running Tests

### Unit and Integration Tests

Run all tests:
```bash
python -m pytest
```

Run specific test categories:
```bash
# Unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Load tests
python -m pytest tests/load/
```

Run with coverage:
```bash
python -m pytest --cov=app --cov-report=html
```

### End-to-End Tests

We use Playwright for end-to-end tests to simulate real user interactions with the application.

Setup:
```bash
# Install dependencies
npm install

# Install browser engines
npm run install:playwright
```

Run tests:
```bash
# Run all E2E tests
npm run test:e2e

# Run with UI mode for debugging
npm run test:e2e:ui
```

## GitHub Actions Local Testing

Test GitHub Actions workflows locally using [nektos/act](https://github.com/nektos/act):

```bash
# Install act and set up test environment
./act-install.sh

# Test specific jobs
npm run act:verify    # Test production verification
npm run act:ci        # Test CI workflow
```

## CI/CD Pipeline Tests

Our CI/CD pipeline runs the following tests:

1. **On Pull Request**: 
   - Unit tests, linting, and E2E tests

2. **On Push to Staging**:
   - Full test suite including E2E tests
   - Deployment to staging environment

3. **On Promotion to Main**:
   - Critical verification tests
   - Smoke tests to ensure functionality
   - Production deployment (if tests pass)

## Mocking External Services

For testing, we mock the following external services:

- **OpenAI**: Mocked responses for AI requests
- **Twilio**: Mocked SMS and voice interactions
- **Deliverect**: Mocked API responses for menu and order operations

Set the environment variables to enable test mocks:
```
TESTING=true
DISABLE_OPENAI=true
```

## Test Data

Test data is stored in:
- `/tests/conftest.py`: Common test fixtures
- `/testing_data/`: Test payloads for external services

## Debugging Tests

For verbose output:
```bash
python -m pytest -v
```

For specific failures:
```bash
python -m pytest -v path/to/test.py::test_function
```

For Playwright tests, use the UI mode:
```bash
npm run test:e2e:ui
```