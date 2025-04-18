# Comprehensive End-to-End Testing Guide

This guide outlines how to run comprehensive end-to-end tests for the RedBarSushiAI application.

## Overview

Our E2E testing suite includes:

1. **Basic UI Tests** - Test core UI functionality
2. **Comprehensive E2E Tests** - Test complete user flows
3. **Full API Integration Tests** - Test actual API integrations with external services

## Setup

### 1. Configure API Keys

Edit the `.env.test` file to include your actual API keys:

```
# OpenAI
DISABLE_OPENAI=false  
OPENAI_API_KEY=sk-your-actual-openai-key

# Twilio
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_NUMBER=+15551234567

# Deliverect
DELIVERECT_CLIENT_ID=your-deliverect-client-id
DELIVERECT_CLIENT_SECRET=your-deliverect-client-secret
DELIVERECT_ACCOUNT_ID=your-deliverect-account-id

# Test Configuration
RUN_EXTERNAL_API_TESTS=true
```

### 2. Install Dependencies

```bash
# Install npm dependencies
npm install

# Install Playwright browsers
npm run install:playwright
```

## Running Tests

### Option 1: Run All Tests (Recommended)

Run the comprehensive test script:

```bash
./run-comprehensive-tests.sh
```

This script will:
1. Check for API keys
2. Start the application
3. Run all tests
4. Generate reports

### Option 2: Run Specific Test Suites

```bash
# Run basic UI tests
npm run test:e2e:simple

# Run comprehensive E2E tests
npm run test:e2e:comprehensive

# Run API integration tests
npm run test:api
```

### Option 3: Run Tests with UI Debugging

```bash
# Run with UI mode for debugging
npm run test:e2e:ui
```

## Test Coverage

Our test suite covers:

### UI Tests
- Menu rendering and navigation
- Order placement workflow
- Admin dashboard functionality
- Order status tracking

### API Integration Tests
- OpenAI integration for voice and text processing
- Twilio integration for SMS and voice
- Deliverect integration for menu synchronization

## Mocking vs Real APIs

By default, the comprehensive tests will use real API keys if provided. To use mocks instead:

1. Set `DISABLE_OPENAI=true` in `.env.test`
2. Set `RUN_EXTERNAL_API_TESTS=false` in `.env.test`

## Troubleshooting

### Common Issues

1. **Tests timeout when connecting to APIs**
   - Check your API keys and network connection
   - Try increasing the test timeout in playwright.config.js

2. **UI tests fail to find elements**
   - Check if selectors have changed in the application
   - Use the UI mode to debug: `npm run test:e2e:ui`

3. **Application fails to start during testing**
   - Check the Flask logs for errors
   - Verify database connection settings

## Continuous Integration

These tests are also integrated with our GitHub Actions CI/CD pipeline:

- Basic tests run on every PR
- Comprehensive tests run when merging to staging
- Critical verification tests run when promoting to production