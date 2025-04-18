# Comprehensive End-to-End Testing for RedBarSushiAI

This guide explains how to run comprehensive end-to-end tests that test every aspect of your application with real API keys.

## Overview

The E2E testing suite includes:

1. **UI Tests** - Test the user interface and interactions
2. **API Tests** - Test API endpoints directly
3. **Integration Tests** - Test the integration with external services (OpenAI, Twilio, etc.)

## Getting Started

### 1. Install Dependencies

Make sure your virtual environment is set up with all required dependencies:

```bash
# Activate the virtual environment
source venv/bin/activate

# Install required packages if needed
pip install playwright pytest-playwright python-dotenv flask flask-sqlalchemy sqlalchemy
pip install openai twilio stripe
```

### 2. Run the Test Script

The easiest way to run the tests is using the provided script:

```bash
./run-e2e-tests.sh
```

This script will:
1. Check for the virtual environment
2. Ask if you want to use real API keys
3. Create or update the `.env.test` file with your settings
4. Let you choose which tests to run
5. Run the selected tests and display results

### 3. Using Real API Keys

When prompted, choose "y" to use real API keys. The script will:
- Ask for any missing API keys
- Store them in the `.env.test` file
- Enable full API testing

### 4. Test Output

The tests will:
- Take screenshots for debugging (stored in the screenshots directory)
- Print detailed logs of what's being tested
- Report any failures or issues

## Manual Testing

If you prefer to run tests manually:

```bash
# Basic menu tests
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python -m pytest tests/e2e/test_menu.py -v

# Order flow tests
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python -m pytest tests/e2e/test_order.py -v

# API tests (requires real keys or mock flag)
USE_REAL_API_KEYS=true PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python -m pytest tests/e2e/test_api.py -v
```

## Test Files

The test suite includes:

- `test_menu.py` - Tests for the menu display and functionality
- `test_order.py` - Tests for the complete order process
- `test_api.py` - Tests for API endpoints and integration

## Troubleshooting

### Browser Issues
If you encounter browser launch problems:
```bash
# Try using Firefox instead
BROWSER=firefox ./run-e2e-tests.sh
```

### Test Failures
If tests fail, check:
1. The screenshot files for visual debugging
2. The application logs for errors
3. Network connectivity for API tests

### Page Structure Differences
The tests try to be flexible and adapt to your page structure, but if elements aren't found:
1. Review the test files to see what selectors are being used
2. Modify selectors to match your actual page structure
3. Add additional debug logging if needed

## Extending the Tests

To add more tests:
1. Create new test files in the `tests/e2e/` directory
2. Follow the same pattern as existing tests
3. Update the `run-e2e-tests.sh` script if needed to include new tests