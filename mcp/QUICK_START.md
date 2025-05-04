# RedBarSushiAI MCP Quick Start Guide

This guide will help you quickly set up and start using the RedBarSushiAI Mission Control Platform (MCP) for running E2E tests on the staging environment.

## 1. Setup

### Option A: Local Installation

```bash
# Clone the repository if you haven't already
git clone https://github.com/proxyie/RedBarSushiAI.git
cd RedBarSushiAI/mcp

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your specific values
```

### Option B: Docker Installation

```bash
# Clone the repository if you haven't already
git clone https://github.com/proxyie/RedBarSushiAI.git
cd RedBarSushiAI/mcp

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your specific values

# Build and start the Docker containers
docker-compose up -d
```

## 2. Configuration

Make sure to set the following required environment variables in your `.env` file:

- `RENDER_API_KEY`: Your Render API key
- `RENDER_SERVICE_ID`: The Render service ID for the staging environment
- `TEST_TWILIO_AUTH_TOKEN`: Your Twilio auth token
- `TEST_OPENAI_API_KEY`: Your OpenAI API key
- `TEST_CUSTOMER_PHONE`: A valid phone number for testing

## 3. Running Tests

### Basic Test Run

```bash
# Run all E2E tests
python -m mcp.cli run-tests

# Run a specific test
python -m mcp.cli run-tests --test tests/e2e/test_complete_order_flow.py::test_complete_order_workflow
```

### Analyzing Test Results

```bash
# Run tests and analyze results
python -m mcp.cli analyze

# With automatic fix suggestions
python -m mcp.cli analyze --auto-fix
```

## 4. Interpreting Results

The MCP test runner will output a summary of the test results:

```
Test Results:
  Total: 10
  Passed: 8
  Failed: 2
  Pass Rate: 80.00%

Failed Tests:
  - test_complete_order_workflow (tests.e2e.test_complete_order_flow)
    Failure: AssertionError: ...
  - test_menu_update_and_retrieval_workflow (tests.e2e.test_complete_order_flow)
    Error: ConnectionError: ...
```

## 5. Common Issues and Fixes

### Connection Errors

If you see connection errors, check:

1. Is the staging environment up and running?
2. Are the Render API credentials correct?

You can use the MCP to restart the service:

```bash
# Check the service health
curl -X GET "https://api.render.com/v1/services/{SERVICE_ID}" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer {RENDER_API_KEY}"

# Restart the service
curl -X POST "https://api.render.com/v1/services/{SERVICE_ID}/restart" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer {RENDER_API_KEY}"
```

### Authentication Errors

If you see Twilio or OpenAI authentication errors:

1. Verify that the API keys are correct in your `.env` file
2. Check that the API keys have the necessary permissions

## 6. Troubleshooting

### Test runner can't find the repository

Make sure you have Git installed and that the repository URL is correct.

### Playwright installation errors

If you encounter Playwright dependency issues, run:

```bash
# Install Playwright
pip install playwright
playwright install
playwright install-deps
```

### Database connection errors

If using Docker, make sure the database service is running:

```bash
docker-compose ps
```

## 7. Next Steps

- Schedule regular test runs
- Set up automated notifications
- Create custom fix strategies for your common issues

For more details, see the full [MCP Setup Documentation](./mcp_setup.md).