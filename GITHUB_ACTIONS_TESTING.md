# RedBarSushiAI E2E Testing in GitHub Actions

This document describes how E2E tests run in GitHub Actions CI/CD environment.

## Overview

The E2E tests for RedBarSushiAI are designed to run in both local environments (including Arch Linux) and in GitHub Actions workflows running on Ubuntu.

## GitHub Actions Workflows

There are three main GitHub Actions workflows:

1. **Verify Playwright** (`verify-playwright.yml`):
   - Minimal workflow to verify Playwright installation
   - Manually triggered or runs on branches with "e2e-testing" or "playwright" in name
   - Just installs Playwright and runs direct_test.py
   - Useful for quick verification that Playwright works in CI

2. **Regular Tests** (`run-tests.yml`):
   - Runs automatically on push to main/staging branches and PRs
   - Excludes E2E tests but properly installs Playwright to avoid import errors
   - Focuses on unit and integration tests

3. **E2E Tests** (`e2e-tests.yml`):
   - Manually triggered workflow (using workflow_dispatch)
   - Runs E2E tests with real API keys
   - Uses cross-platform testing approach

## How E2E Tests Run in GitHub Actions

The E2E tests in GitHub Actions:

1. Install Ubuntu-specific dependencies (including xvfb)
2. Install Playwright and its system dependencies 
3. Use socket-based server connection checks (instead of curl)
4. Run the tests in an Ubuntu-compatible manner
5. Use Xvfb for headed browser tests

### Installing Playwright

We now have cross-platform installation scripts:

1. **Universal Installation Script**:
   ```bash
   ./setup-playwright.sh
   ```
   This script automatically detects your OS and installs the right dependencies for both Arch Linux and Ubuntu.
   
2. **Ubuntu-Specific Installation**:
   ```bash
   ./install-playwright-ubuntu.sh
   ```
   This script:
   - Installs required system dependencies
   - Sets up a Python virtual environment
   - Installs Playwright and its browsers
   - Installs system dependencies for Playwright

3. **Verifying Installation**:
   ```bash
   python verify-playwright.py
   ```
   This script checks:
   - Playwright can be imported
   - Browser can be launched
   - Screenshots can be taken

## Setting Up API Keys for GitHub Actions

To use real APIs in the GitHub Actions tests, add these secrets:

- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `DELIVERECT_CLIENT_ID`
- `DELIVERECT_CLIENT_SECRET`

## Running E2E Tests Manually

To run E2E tests in GitHub Actions:

1. Go to the "Actions" tab in GitHub
2. Select "E2E Tests with Real APIs" workflow
3. Click "Run workflow"
4. Select the branch to run on
5. Click "Run workflow" button

## Test Artifacts

The workflow saves these artifacts:

- Test screenshots (for debugging)
- Coverage reports
- Test logs

## Troubleshooting

If E2E tests fail in GitHub Actions:

1. Run the simplified verification workflow first (`verify-playwright.yml`)
2. Check the "Actions" tab for detailed logs
3. Look at the uploaded artifacts for screenshots
4. Look for errors related to API connectivity
5. Verify your API keys are correctly set as secrets

### Common Issues in GitHub Actions

1. **"ModuleNotFoundError: No module named 'playwright'"**:
   - The workflow is not properly installing Playwright
   - Verify that the workflow includes `pip install playwright==1.41.2`

2. **Cannot find browser executable**:
   - Playwright browsers aren't installed
   - Ensure workflow includes `python -m playwright install chromium`

3. **Missing system dependencies**:
   - Ensure workflow includes `python -m playwright install-deps chromium` 
   - Make sure the system packages are installed:
     ```yaml
     sudo apt-get install -y xvfb libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm-dev libasound2
     ```

4. **Permission issues**:
   - Make sure scripts are executable: `chmod +x *.sh`

## Differences from Local Testing

GitHub Actions E2E tests differ from local testing in these ways:

1. Runs on Ubuntu instead of Arch Linux
2. Uses GitHub Secrets for API keys
3. Has time and resource limitations
4. Requires xvfb for headed browser tests