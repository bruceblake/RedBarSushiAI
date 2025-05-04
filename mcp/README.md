# RedBarSushiAI Mission Control Platform (MCP)

This package provides tools for running end-to-end tests on the RedBarSushiAI staging environment, analyzing test results, and generating fixes for issues.

## Features

- **Test Runner**: Execute E2E tests against the staging environment
- **Result Analyzer**: Identify patterns in test failures
- **Fix Generator**: Create patches for common issues
- **Render API Client**: Interact with the Render staging environment
- **CLI Tool**: Run tests and analyze results from the command line
- **Claude Code Integration**: Run tests directly from Claude Code using the MCP integration

## Installation

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the `mcp` directory with the following environment variables:

```
# Basic configuration
MCP_ENV=production
LOG_LEVEL=INFO

# Database connection
DATABASE_URL=postgresql://user:password@localhost:5432/mcp_testing

# Redis connection
REDIS_URL=redis://localhost:6379/0

# Render API
RENDER_API_KEY=your_render_api_key
RENDER_SERVICE_ID=srv-123456 # Your staging service ID

# GitHub configuration
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=owner/RedBarSushiAI
GITHUB_BASE_BRANCH=staging

# Slack notifications (optional)
SLACK_WEBHOOK_URL=your_slack_webhook_url
SLACK_CHANNEL=#redbarsushi-alerts

# Test configuration
TEST_BASE_URL=https://redbarsushi-staging.onrender.com
TEST_TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
TEST_TWILIO_AUTH_TOKEN=your_auth_token
TEST_TWILIO_PHONE=+18333247207
TEST_OPENAI_API_KEY=your_openai_api_key
TEST_CUSTOMER_PHONE=+YOUR_TEST_PHONE
```

## Usage

### Running E2E Tests

```bash
# Run all E2E tests
python -m mcp.cli run-tests

# Run a specific test
python -m mcp.cli run-tests --test tests/e2e/test_complete_order_flow.py::test_complete_order_workflow

# Save test results to a file
python -m mcp.cli run-tests --output test_results.json
```

### Analyzing Test Results

```bash
# Run tests and analyze results
python -m mcp.cli analyze

# Generate suggestions for fixing issues
python -m mcp.cli analyze --auto-fix

# Save analysis results to a file
python -m mcp.cli analyze --output analysis_results.json
```

### Generating Fixes from Previous Results

```bash
# Generate fixes from a previous test run
python -m mcp.cli generate-fixes --input test_results.json
```

## Development

### Code Style

```bash
# Format code
black mcp

# Sort imports
isort mcp

# Lint code
flake8 mcp
```

### Adding New Fix Strategies

1. Identify a common issue pattern in test failures
2. Add a new method to `FixGenerator` to handle the issue
3. Update the `generate_fix` method to dispatch to your new method
4. Add appropriate tests for the new fix strategy

## Architecture

The MCP follows a modular architecture with these main components:

- **Config**: Loads configuration from environment variables
- **Test Runner**: Executes tests against the staging environment
- **Result Analyzer**: Identifies patterns in test failures
- **Fix Generator**: Creates patches for common issues
- **Render Client**: Interacts with the Render API
- **CLI**: Command-line interface for running tests and analyzing results

## Claude Code Integration

The MCP now supports integration with Claude Code through a simple HTTP server that handles Claude Code MCP commands.

### Setup

1. Start the MCP server:
   ```bash
   ../start_mcp_server.sh
   ```

2. Connect to the MCP from Claude Code:
   ```
   /mcp connect
   ```

3. List available tests:
   ```
   /mcp list-tests staging
   ```

4. Run a test:
   ```
   /mcp run-test staging e2e
   ```

5. Check service health:
   ```
   /mcp check-health staging web
   ```

6. Restart a service:
   ```
   /mcp restart-service staging web
   ```

7. Fix an issue:
   ```
   /mcp fix-issue connection_error
   ```

### Configuration

The MCP configuration for Claude Code is stored in `.claude-mcp.json` in the project root. This file contains the configuration for:

- Available environments
- Tests that can be run
- Services that can be managed
- Fix strategies for common issues

### Troubleshooting

If you encounter issues with the MCP integration:

1. Make sure the MCP server is running (`../start_mcp_server.sh`)
2. Check that your Claude Code configuration is correct (`~/.config/anthropic/claude-code/config.json`)
3. Set the required environment variables (`RENDER_API_KEY`, `RENDER_SERVICE_ID`)

## License

Proprietary - All Rights Reserved