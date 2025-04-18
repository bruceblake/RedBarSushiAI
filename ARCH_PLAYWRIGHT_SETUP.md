# Setting Up Playwright for Arch Linux

This guide explains how to set up Playwright for end-to-end testing on Arch Linux.

## Installation

We've provided a script that installs Playwright using pip within a virtual environment, which works reliably on Arch Linux:

```bash
# Run the installation script
./install-playwright-pip.sh
```

This script:
1. Creates a Python virtual environment
2. Installs Playwright and pytest
3. Downloads the Chromium browser for testing

## Running Tests

After installation, you can run the tests using the npm scripts we've set up:

```bash
# Run a simple test
npm run test:e2e:simple

# Run all tests
npm run test:e2e

# Run tests with UI (headed mode)
npm run test:e2e:ui
```

Or directly with Python:

```bash
# First activate the virtual environment
source venv/bin/activate

# Run a specific test
python -m pytest tests/e2e/custom-test.py

# Run all tests
python -m pytest tests/e2e
```

## Troubleshooting

### Common Issues

1. **Missing Python packages**:
   ```bash
   # Make sure the virtual environment is activated
   source venv/bin/activate
   
   # Install missing packages
   pip install playwright pytest pytest-playwright python-dotenv
   ```

2. **Browser not installed**:
   ```bash
   # Install the Chromium browser
   python -m playwright install chromium
   ```

3. **Permission issues**:
   ```bash
   # Fix permissions for the installation script
   chmod +x install-playwright-pip.sh
   ```

## Running Tests with Different Browsers

By default, tests run with Chromium. To use a different browser:

```bash
# Install additional browsers
python -m playwright install firefox webkit

# Run tests with Firefox
BROWSER=firefox python -m pytest tests/e2e

# Run tests with WebKit
BROWSER=webkit python -m pytest tests/e2e
```

## CI/CD Integration

The tests are configured to run in headless mode by default, which is suitable for CI/CD environments. Just make sure to install the dependencies in your CI workflow:

```yaml
- name: Set up Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'

- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install playwright pytest pytest-playwright python-dotenv
    python -m playwright install chromium

- name: Run tests
  run: python -m pytest tests/e2e
```