# RedBarSushiAI Refactored Code Testing with MCP

This directory contains an MCP (Model Context Protocol) server that helps test the refactored code in a Docker environment that closely resembles the staging environment. It enables you to test your refactored code before pushing it to GitHub and deploying to Render.

## Features

- Test imports to verify that refactored modules are correctly structured
- Test database connectivity to verify that refactored code works with PostgreSQL
- Test Redis connectivity to verify that refactored code works with Redis
- Test Flask blueprint registration to verify that refactored routes are correctly registered
- Run all tests in a single command to comprehensively validate changes

## Setup

Before using the MCP server, you need to set it up:

```bash
# Run the setup script
./mcp/setup.sh
```

This script:
1. Creates a Python virtual environment for the MCP server
2. Installs the required packages
3. Makes the MCP server script executable
4. Registers the MCP server with Claude

## Usage

After setting up the MCP server, restart Claude and use the following commands to test your refactored code:

```
# Test imports only (fastest test)
/mcp redbarsushi-test test_imports project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Test Flask blueprint registration
/mcp redbarsushi-test test_flask project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Test database connectivity
/mcp redbarsushi-test test_database project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Test Redis connectivity
/mcp redbarsushi-test test_redis project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Run all tests (most comprehensive)
/mcp redbarsushi-test test_all project_path="/home/proxyie/MySoftware/RedBarSushiAI"
```

## How It Works

The MCP server sets up a Docker environment with the following services:

1. **PostgreSQL**: A database service that mimics the staging PostgreSQL database
2. **Redis**: A Redis service that mimics the staging Redis instance
3. **App**: Your application running in a Docker container with the refactored code

The tests are run inside the Docker environment to ensure that they closely resemble the staging environment. This helps catch issues that might not be apparent when running the code locally.

## Requirements

- Docker and Docker Compose
- Python 3.9+ with pip
- jq (for JSON processing in the setup script)

## Troubleshooting

If you encounter any issues:

1. Make sure Docker is running
2. Check that the MCP server is registered correctly with Claude
3. Verify that the project path is correct
4. Look at the logs for detailed error messages

If the tests fail, fix the issues in your refactored code and try again.