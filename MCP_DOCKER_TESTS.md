# Docker Testing with Model Context Protocol (MCP)

This document provides information on how to use the enhanced MCP server to run Docker-based tests via Claude Code.

## Overview

The Enhanced MCP server provides Claude with the ability to run various tests in Docker environments, including:

1. Integration tests - using a lightweight test environment
2. End-to-End (E2E) tests - using a full production-like environment with multiple services
3. Browser automation tests - using Playwright for simulating user interactions in a browser

These capabilities are exposed through a set of MCP tools that can be accessed using Claude Code.

### Playwright Browser Automation

The E2E test environment now includes support for browser automation through Playwright, allowing tests to:

- Simulate real user interactions in a browser
- Test JavaScript functionality and UI components
- Verify voice call flows with simulated browser interactions
- Run headless browser tests through Xvfb virtual display

This functionality is built into the E2E Docker setup with all necessary dependencies.

## Available MCP Tools

The following tools are available through the `/mcp docker-test` command in Claude:

 < /dev/null |  Tool | Description | Usage |
|------|-------------|-------|
| `run_test` | Run tests on the staging environment | `/mcp docker-test run_test test_type="basic"` |
| `docker_start` | Start Docker containers for a specific test environment | `/mcp docker-test docker_start test_type="integration"` |
| `docker_stop` | Stop and remove Docker containers | `/mcp docker-test docker_stop test_type="all"` |
| `docker_test` | Run integration tests inside Docker | `/mcp docker-test docker_test test_file="test_deliverect_api_integration.py"` |
| `docker_status` | Show the status of all test containers | `/mcp docker-test docker_status` |

## Setup Instructions

1. Make sure Docker is installed and running on your system
2. Ensure Claude CLI is installed
3. Run the setup script to register the enhanced MCP server:

```bash
./run_enhanced_mcp.sh
```

4. Verify the MCP server is registered and running:

```bash
claude /mcp
```

You should see `docker-test: connected` in the output.

## Usage Examples

### Start the Integration Test Environment

```
/mcp docker-test docker_start test_type="integration"
```

This starts the PostgreSQL and Redis containers required for integration testing.

### Run All Integration Tests

```
/mcp docker-test docker_test test_file="all"
```

This runs all integration tests in the Docker environment.

### Run a Specific Integration Test

```
/mcp docker-test docker_test test_file="test_deliverect_api_integration.py"
```

This runs a specific integration test file in the Docker environment.

### Start the Full E2E Environment

```
/mcp docker-test docker_start test_type="e2e"
```

This starts all containers required for end-to-end testing, including:

- PostgreSQL database
- Redis cache and message broker
- Web application server
- Celery worker
- Mock Deliverect API
- Test runner

### Check Container Status

```
/mcp docker-test docker_status
```

This shows the status of all running Docker containers.

### Stop All Containers

```
/mcp docker-test docker_stop test_type="all"
```

This stops and removes all Docker containers used for testing.

## Testing Workflow

A typical workflow for running tests via Claude Code:

1. Start the Docker containers:
   ```
   /mcp docker-test docker_start test_type="integration"
   ```

2. Run the tests:
   ```
   /mcp docker-test docker_test test_file="all"
   ```

3. Check container status (optional):
   ```
   /mcp docker-test docker_status
   ```

4. Stop the containers when finished:
   ```
   /mcp docker-test docker_stop test_type="integration"
   ```

## Troubleshooting

If you encounter issues with the MCP server:

1. Check the log file at `enhanced_mcp.log`
2. Restart the MCP server using `./run_enhanced_mcp.sh`
3. Verify Docker is running with `docker ps`
4. Check if there are any conflicting containers with `docker ps -a`

## Environment Variables

The Docker testing environment uses these key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `TEST_MODE`: Set to "docker" for Docker-based tests
- `SKIP_DB_SETUP`: Control database initialization
- `BASE_URL`: URL for the web app service

### Playwright Browser Automation Variables

For browser automation tests, the following additional environment variables are set:

- `DISPLAY`: Set to ":99.0" for Xvfb virtual display
- `PLAYWRIGHT_BROWSERS_PATH`: Path for storing browser binaries
- `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD`: Controls automatic browser download

These are automatically configured by the Docker Compose setup.

## Further Information

For more details on the testing infrastructure, refer to:

- `docker-compose-e2e.yml` - Full E2E test environment configuration
- `tests/docker-compose-test.yml` - Integration test environment configuration
- `run_e2e_tests.sh` - Script for running E2E tests locally
- `run_docker_integration_tests.sh` - Script for running integration tests locally
