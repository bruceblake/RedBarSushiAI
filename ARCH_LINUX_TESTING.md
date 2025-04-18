# Testing RedBarSushiAI on Arch Linux

This guide explains how to run end-to-end tests on Arch Linux where Playwright has compatibility challenges.

## Quick Start

For the most reliable tests on Arch Linux, use the specialized Arch script:

```bash
# Run the Arch Linux specific test script (recommended)
./run-e2e-tests-arch.sh
# Select option 1 for "Direct test" when prompted

# Alternatively, use the general test script
./run-full-e2e-tests.sh
# Select option 1 for "Basic Test" when prompted
```

## Overview of Testing Approaches

We've created three different testing approaches, in order of reliability:

1. **Direct Standalone Test** (`direct_test.py`):
   - Most reliable on Arch Linux
   - Doesn't depend on external tools or pytest
   - Handles its own Flask server and browser
   - Generates screenshots even if server fails

2. **Basic UI Test** (`basic_ui_test.py`):
   - Standalone pytest-independent test
   - More complex server handling
   - May have issues with port conflicts

3. **Pytest Tests** (various `test_*.py` files):
   - Most comprehensive tests
   - Uses pytest fixtures and conftest.py
   - Uses APIClient fixture for API testing

## Installation

### 1. Install System Dependencies

First, install the required system packages for Playwright on Arch Linux:

```bash
sudo pacman -S --needed chromium firefox webkit2gtk \
  libx11 libxcomposite libxdamage libxext libxfixes libxrandr \
  libxcursor libxi libxkbcommon alsa-lib at-spi2-core libxss pango \
  nss nspr libcups libdrm mesa xorg-server-xvfb
```

### 2. Install Python Dependencies

You can use the provided install script to create a virtual environment and install Python dependencies:

```bash
./install-playwright-pip.sh
```

This script will:
1. Create a Python virtual environment in the `venv` directory
2. Install Playwright and pytest-playwright packages
3. Install the Chromium browser for Playwright

## What Gets Tested

The direct test verifies:
- Playwright browser launches correctly
- Basic UI interactions work
- Screenshots can be taken
- Flask application starts (optional)

The more comprehensive tests cover:
- Menu functionality
- Order placement
- API integrations
- OpenAI integration (optional)
- Twilio integration (optional)
- Deliverect menu sync (optional)

## Running Different Test Types

### Option 1: Using the Arch-Specific Test Script (Recommended)

```bash
./run-e2e-tests-arch.sh
```

This script is optimized for Arch Linux and offers these options:
1. **Direct test** - Runs the most reliable headless test 
2. **API test** - Tests the API endpoints directly
3. **Full UI test** - Runs UI tests using Xvfb (virtual display)

This approach handles all the Arch Linux specific requirements automatically.

### Option 2: Using the Comprehensive Test Script

```bash
./run-full-e2e-tests.sh
```

This offers more options but may have compatibility issues on Arch:
1. **Basic Test** - Just runs the direct test (most reliable)
2. **Comprehensive Test** - Runs full test suite (may have issues)
3. **Debug Mode** - Runs tests with enhanced logging
4. **API Test** - Tests API endpoints only
5. **Performance Mode** - Runs with performance tracing
6. **Single File Test** - Run a specific test file
7. **Kill Flask Instances** - Kill any running Flask servers

### Option 3: Run Tests Directly

For the direct standalone test (most reliable):
```bash
# Activate the virtual environment
source venv/bin/activate

# Set the environment variable to skip Playwright host validation
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

# Run the direct test
python tests/e2e/direct_test.py
```

For pytest-integrated tests (may need Xvfb):
```bash
# Activate the virtual environment
source venv/bin/activate

# Set the environment variable to skip Playwright host validation
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

# Run with Xvfb for headed browser support
xvfb-run python -m pytest tests/e2e/test_menu.py -v

# Or run headless
export HEADED=false
python -m pytest tests/e2e/test_menu.py -v
```

## Troubleshooting

### Port Conflicts

If you see `ERR_CONNECTION_REFUSED`:
- Check if anything is using port 5000: `ss -tulpn | grep 5000`
- Try stopping other Flask instances: `pkill -f flask`
- Edit `flask_port` in conftest.py and direct_test.py to use a different port

### TopRequest Object Errors

If you see `AttributeError: 'TopRequest' object has no attribute 'get'/'post'`:
- Use the updated test files that use the `api_client` fixture
- This has been fixed by creating a custom API client fixture that wraps Playwright's request object

### Chromium Issues

If Chromium fails to launch:
- Make sure `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1` is set
- Try Firefox instead: modify test files to use `playwright.firefox`
- Check error messages for missing dependencies

### System Dependencies

If you get errors about missing system libraries:
```bash
sudo pacman -S nss nspr atk at-spi2-atk cups libx11 libxcomposite \
libxdamage libxext libxfixes libxrandr mesa libxcb libxkbcommon \
pango cairo alsa-lib at-spi2-core
```

## Debugging

### Debug Techniques

1. Run with visible browser:
   ```bash
   HEADED=true PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python -m pytest tests/e2e/test_menu.py -v
   ```

2. Look at screenshot artifacts:
   - `test-page.png` - The simple test page
   - `homepage.png` - The app homepage (if available)
   - Check the `screenshots` directory for additional test screenshots

3. Run Flask and Playwright independently:
   ```bash
   # Terminal 1: Run Flask
   python run.py
   
   # Terminal 2: Run direct test
   PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python tests/e2e/direct_test.py
   ```

## API Testing

We support both mock API testing and real API integration testing. To use real APIs:

1. Create a `.env.test` file with your API keys
2. Set `USE_REAL_API_KEYS=true` in the `.env.test` file
3. Run the tests with the external API tests enabled:
   ```bash
   RUN_EXTERNAL_API_TESTS=true ./run-e2e-tests.sh
   ```

## Extending Tests

### To add more tests:

1. Start by modifying the direct test (`direct_test.py`) - most reliable for Arch Linux
2. For pytest tests, follow these patterns:
   - Use `api_client` fixture for API testing
   - Use absolute URLs with the `base_url` fixture
   - Create proper test data directories
   - Use `page.goto(f"{base_url}/path")` pattern for navigation