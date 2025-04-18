# E2E Testing for RedBarSushiAI on Arch Linux

This guide explains how to run end-to-end tests for the RedBarSushiAI application on Arch Linux.

## Quick Start

We've created a standalone test solution that works reliably on Arch Linux:

```bash
# Run the test script
./run-e2e-tests.sh
```

This will give you options to:
1. Run basic UI tests only
2. Run the full test suite
3. Select specific test files to run

## Test Files

### Standalone Test (Most Reliable)

The `basic_ui_test.py` file is a completely standalone test that:
- Starts its own Flask server
- Launches Playwright directly
- Tests basic application functionality
- Works independently of pytest fixtures

This is the most reliable way to test on Arch Linux as it avoids scope conflicts with pytest fixtures.

### Pytest Tests

The other test files use pytest and offer more comprehensive testing:
- `test_menu.py`: Tests menu functionality
- `test_order.py`: Tests order processing
- `test_api.py`: Tests API endpoints

## Visual Debugging

All tests take screenshots that are saved in the root directory:
- `homepage.png`
- `menu-page.png`
- `before-submit.png`
- `after-submit.png`

Check these screenshots if tests fail to see what the UI looked like.

## Using Real API Keys

When running the test script, you'll be asked if you want to use real API keys. Select "y" if you want to test with actual OpenAI, Twilio, etc. integration.

## Troubleshooting

### Scope Mismatch Errors

If you see "ScopeMismatch" errors with pytest, use the standalone test instead:

```bash
python tests/e2e/basic_ui_test.py
```

### Browser Launch Issues

If the browser fails to launch:
1. Make sure the environment variable is set:
   ```bash
   export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
   ```

2. Try running with Firefox instead:
   ```bash
   BROWSER=firefox ./run-e2e-tests.sh
   ```

### Server Start Issues

If the Flask server fails to start:
1. Check if port 5000 is already in use
2. Try manually starting the server:
   ```bash
   FLASK_APP=run.py TESTING=true FLASK_ENV=testing python -m flask run
   ```

## Extending Tests

To add more tests:
1. For simple tests, modify the `basic_ui_test.py` file
2. For more complex tests, add new test files following the existing patterns

Remember to keep the standalone test approach for maximum compatibility with Arch Linux.