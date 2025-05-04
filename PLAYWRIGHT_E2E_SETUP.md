# Playwright E2E Testing Setup

This document provides an overview of the Playwright integration for browser automation testing in the RedBarSushiAI project.

## Overview

Playwright has been integrated into the End-to-End (E2E) testing environment to enable browser automation testing. This allows us to simulate real user interactions with the web application, test JavaScript functionality, and verify complex user flows such as voice call handling.

## Key Components

### 1. Docker Environment Configuration

The `docker-compose-e2e.yml` file has been updated to support browser automation:

```yaml
# Test runner service with Playwright support
test-runner:
  build:
    context: .
    dockerfile: Dockerfile
  command: >
    /bin/bash -c "
    echo 'Installing E2E test dependencies...' &&
    pip install -r requirements.e2e.txt &&
    python -m playwright install --with-deps chromium &&
    echo 'Waiting for web app to be ready...' &&
    sleep 10 &&
    xvfb-run --server-args='-screen 0 1280x720x24' pytest tests/e2e/ -v
    "
  environment:
    # Standard environment variables
    - DATABASE_URL=postgresql://test_user:test_password@postgres-e2e:5432/test_redbarsushi
    - REDIS_URL=redis://redis-e2e:6379/0
    - TEST_MODE=e2e
    - FLASK_ENV=testing
    - TESTING=true
    - BASE_URL=http://web-app:5000
    - DELIVERECT_API_URL=http://mock-deliverect:5000
    - SKIP_DB_SETUP=false
    # Playwright specific environment variables
    - DISPLAY=:99.0
    - PLAYWRIGHT_BROWSERS_PATH=/app/.playwright-browsers
    - PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
  # ... other configuration ...
  volumes:
    - ./:/app
    - ./tests/e2e/reports:/app/reports
    - playwright-browsers:/app/.playwright-browsers
```

A new volume `playwright-browsers` has been added to persist browser binaries between test runs.

### 2. E2E Test Runner

The `run_e2e_tests.sh` script has been updated to handle Playwright dependencies:

```bash
# Install required dependencies first
log "Installing required dependencies for E2E tests..."
pip install -q -r requirements.e2e.txt

# Install playwright browsers
if ! python -c "import playwright" &> /dev/null; then
  log "Installing Playwright browsers..."
  python -m playwright install --with-deps chromium
fi
```

### 3. CI/CD Pipeline

The GitHub Actions workflow (`staging-cd.yml`) has been updated to support browser automation:

```yaml
- name: Install dependencies
  run: |
    # Install system dependencies
    sudo apt-get update
    sudo apt-get install -y curl jq xvfb
    
    # Install Python dependencies
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements.e2e.txt
    
    # Install Playwright and browsers
    python -m playwright install --with-deps chromium

- name: Run E2E tests
  run: |
    # Start Xvfb for headless browser tests
    Xvfb :99 -screen 0 1280x720x24 > /dev/null 2>&1 &
    export DISPLAY=:99.0
    
    # Run E2E tests
    ./run_e2e_tests.sh --mode staging --pattern "tests/e2e/test_*.py" --verbose
  env:
    # Existing environment variables...
    DISPLAY: :99.0
    PLAYWRIGHT_BROWSERS_PATH: /home/runner/.cache/ms-playwright
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: 0
```

### 4. Dependencies

A dedicated `requirements.e2e.txt` file contains all necessary dependencies for E2E testing:

```
# E2E test dependencies
pytest==8.3.5
pytest-asyncio==0.26.0
psycopg2-binary==2.9.9
playwright==1.42.0
pytest-playwright==0.4.0
redis==5.2.1
requests==2.32.3
python-dotenv==1.0.1
Jinja2>=3.1.6,<4.0
```

### 5. Documentation

The MCP documentation (`MCP_DOCKER_TESTS.md`) has been updated to include information about browser automation capabilities:

- Added a new section about Playwright in the overview
- Added information about browser automation environment variables
- Updated the usage examples to reference Playwright-based testing

## Usage

### Running Tests Locally

```bash
./run_e2e_tests.sh --mode local
```

This will automatically install Playwright dependencies and run the tests.

### Running Tests in Docker

```bash
docker-compose -f docker-compose-e2e.yml up test-runner
```

This will start all necessary services and run the E2E tests with Playwright support.

### Running Tests in CI/CD

The GitHub Actions workflow will automatically run the E2E tests with Playwright support after deploying to staging.

## Troubleshooting

### Common Issues

1. **Missing browser binaries**:
   - Run `python -m playwright install --with-deps chromium` to install browser binaries
   - Check that the `PLAYWRIGHT_BROWSERS_PATH` environment variable is set correctly

2. **Display errors**:
   - Ensure Xvfb is installed and running: `Xvfb :99 -screen 0 1280x720x24 > /dev/null 2>&1 &`
   - Verify the `DISPLAY` environment variable is set to `:99.0`

3. **Dependency issues**:
   - Ensure all dependencies are installed: `pip install -r requirements.e2e.txt`
   - Check that system dependencies are installed: `apt-get install -y xvfb`

4. **Docker container issues**:
   - Check container logs: `docker-compose -f docker-compose-e2e.yml logs test-runner`
   - Verify the container has access to the virtual display

### Debugging

For detailed browser debugging, you can use:

```python
# In your test file
browser = playwright.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()
```

For screenshots and tracing:

```python
# Capture screenshots
page.screenshot(path="screenshot.png")

# Enable tracing
context.tracing.start(screenshots=True, snapshots=True)
# ... test actions ...
context.tracing.stop(path="trace.zip")
```

## Future Improvements

- Add more comprehensive browser tests for core user flows
- Integrate browser testing with API testing for end-to-end validation
- Add support for multiple browsers (Firefox, WebKit)