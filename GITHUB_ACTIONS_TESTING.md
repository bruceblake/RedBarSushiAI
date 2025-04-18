# RedBarSushiAI E2E Testing in GitHub Actions

This document describes how E2E tests run in GitHub Actions CI/CD environment.

## Overview

The E2E tests for RedBarSushiAI are designed to run in both local environments (including Arch Linux) and in GitHub Actions workflows running on Ubuntu.

## GitHub Actions Workflows

There are two main GitHub Actions workflows:

1. **Regular Tests** (`run-tests.yml`):
   - Runs automatically on push to main/staging branches and PRs
   - Excludes E2E tests to avoid dependency issues
   - Focuses on unit and integration tests

2. **E2E Tests** (`e2e-tests.yml`):
   - Manually triggered workflow (using workflow_dispatch)
   - Runs E2E tests with real API keys
   - Uses cross-platform testing approach

## How E2E Tests Run in GitHub Actions

The E2E tests in GitHub Actions:

1. Install Ubuntu-specific dependencies (including xvfb)
2. Use socket-based server connection checks (instead of curl)
3. Run the tests in an Ubuntu-compatible manner
4. Use Xvfb for headed browser tests

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

1. Check the "Actions" tab for detailed logs
2. Look at the uploaded artifacts for screenshots
3. Look for errors related to API connectivity
4. Verify your API keys are correctly set as secrets

## Differences from Local Testing

GitHub Actions E2E tests differ from local testing in these ways:

1. Runs on Ubuntu instead of Arch Linux
2. Uses GitHub Secrets for API keys
3. Has time and resource limitations
4. Requires xvfb for headed browser tests