# End-to-End Testing for RedBarSushiAI

This directory contains end-to-end tests for the RedBarSushiAI application using Playwright.

## Quick Start

### New Simplified Setup (Recommended)

For a quick setup and verification of Playwright that works on both Arch Linux and Ubuntu:

```bash
# Install and verify Playwright in one step
./setup-playwright.sh
```

Once installed, you can run the most reliable direct test:

```bash
# Run the direct test
python tests/e2e/direct_test.py
```

### Legacy Setup Options

For testing on Arch Linux, use the specialized script:

```bash
./run-e2e-tests-arch.sh
```

This script is optimized for Arch Linux with options for:
1. **Direct test** - Most reliable headless test
2. **API test** - Test API endpoints directly 
3. **Full UI test** - UI tests with Xvfb virtual display

For all other platforms, use the comprehensive test suite:

```bash
./run-full-e2e-tests.sh
```

This will present a menu of testing options:

1. **Basic Test** - Run the most reliable direct test
2. **Comprehensive Test** - Run the full test suite
3. **Debug Mode** - Run tests with debugging options
4. **API Test** - Test API endpoints only
5. **Performance Mode** - Run tests with performance tracing
6. **Single File Test** - Run a specific test file
7. **Kill Flask Instances** - Kill any running Flask servers

## Viewing Test Logs

After running tests, you can view and manage logs:

```bash
./view-test-logs.sh [command]
```

Available commands:
- `list` - List all available test logs
- `view [log_file]` - View a specific log file
- `latest` - View the most recent log file 
- `summary [log]` - Show test summary for a log file
- `cleanup` - Remove old log files

## Test Structure

The e2e tests are organized as follows:

### Standalone Tests (Most Reliable)

- `direct_test.py` - Simple standalone test that doesn't rely on pytest
- `basic_ui_test.py` - Basic UI test that doesn't require pytest

### pytest Tests

- `conftest.py` - Test fixtures and configurations
- `test_menu.py` - Menu-related tests
- `test_order.py` - Order processing tests
- `test_api.py` - API endpoint tests
- `comprehensive_test.py` - Full application tests

## Test Configuration

Tests can be configured using environment variables in `.env.test` or setting them before running tests:

- `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1` - Required for Arch Linux
- `HEADED=true` - Show browser UI during tests
- `USE_REAL_API_KEYS=true` - Use real API keys instead of mocks
- `RUN_EXTERNAL_API_TESTS=true` - Run tests that require external APIs
- `DEBUG=pw:api` - Enable Playwright API debugging
- `DEBUG_LEVEL=debug` - Set debug log level

## CI/CD Integration

We've set up GitHub Actions to run E2E tests with real APIs:

### Available Workflows

1. **verify-playwright.yml** - Minimal workflow to verify Playwright installation
   - Manual trigger or runs on branches with "e2e-testing" or "playwright" in the name
   - Installs Playwright and runs the most reliable direct test
   - Useful for quickly testing if Playwright is correctly installed in CI

2. **e2e-tests.yml** - Comprehensive workflow for E2E tests with real APIs
   - Manually triggered (will be configured for automatic runs when stable)
   - Uses real API keys (if configured)
   - Runs direct tests, API tests, and UI tests with Xvfb

### Setup

1. Add your API keys as GitHub secrets:
   - `OPENAI_API_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `DELIVERECT_CLIENT_ID`
   - `DELIVERECT_CLIENT_SECRET`

2. The workflow uses these secrets to create the `.env.test` file in CI

3. Screenshots are saved as artifacts for debugging

For detailed information, see the workflow files:
- `.github/workflows/verify-playwright.yml`
- `.github/workflows/e2e-tests.yml`
- `.github/workflows/run-tests.yml` (includes special handling for E2E test dependencies)

## Documentation

For detailed information about running tests on Arch Linux, see:

- `ARCH_LINUX_TESTING.md` in the project root directory

## Test Data

- Screenshots are saved in the `screenshots` directory 
- Test logs are saved in `$HOME/redbar_test_logs`
- Test data files are stored in `test-data` subdirectory

## Troubleshooting

If you encounter issues with tests:

1. Verify your Playwright installation: `python verify-playwright.py`
2. Check test logs with `./view-test-logs.sh latest`
3. Run tests in debug mode with `./run-full-e2e-tests.sh` (select option 3)
4. Kill any lingering Flask instances with option 7
5. Check screenshots for visual state of the application

### Common Issues

1. **Module not found: playwright**
   - Run `pip install playwright==1.41.2`

2. **Browser executable not found**
   - Run `python -m playwright install chromium`

3. **Missing system dependencies**
   - On Ubuntu: `sudo apt-get install -y xvfb libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm-dev libasound2`
   - On Arch: `sudo pacman -Sy --noconfirm xorg-server-xvfb mesa libcups nss at-spi2-core alsa-lib xorg-server-xvfb libxss libxrandr`
   - Or use: `python -m playwright install-deps chromium`

4. **Port conflicts**
   - The tests automatically find available ports
   - If issues persist, manually kill running Flask processes

5. **Permission issues in GitHub Actions**
   - Make sure scripts are executable: `chmod +x *.sh`

## Extending the Tests

To add new tests:

1. For simple additions, modify `direct_test.py`
2. For pytest tests, see existing files like `test_menu.py` as examples
3. Use the `api_client` fixture for API tests
4. Use the `base_url` fixture for navigation