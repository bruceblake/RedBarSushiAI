# RedBarSushiAI Testing with MCP

This directory contains MCP (Model Context Protocol) servers that help test the RedBarSushiAI application in various environments.

## Available MCP Servers

1. **Refactor Test Server** (`refactor_test_server.py`): Tests refactored code with basic checks
2. **Docker Test Server** (`docker_test_server.py`): Tests the application in a full Docker environment that closely resembles the Render staging environment
3. **Simple MCP Server** (`simple_mcp_server.py`): A standalone JSON-RPC 2.0 implementation for testing with real Docker containers without SDK dependencies

## Docker Test Environment

The Docker test environment provides a comprehensive testing solution that includes:

- **PostgreSQL**: A database service that mirrors the Render PostgreSQL database
- **Redis**: A Redis service that mirrors the Render Redis instance
- **Application Container**: Your application running in a Docker container with the refactored code

This environment allows for much more thorough testing, including database operations, Redis integration, and full application flow.

## Simple MCP Server Features

The `simple_mcp_server.py` implementation provides a robust, standalone testing solution that:

- Implements the JSON-RPC 2.0 protocol directly without SDK dependencies
- Uses the correct protocol version "2024-11-05" required by Claude
- Sets up and interacts with real Docker containers for PostgreSQL and Redis
- Creates actual database schema matching production
- Tests menu functionality with database persistence
- Tests order processing with Redis cart management
- Tests the full conversation flow with FSM state transitions
- Cleans up resources when testing is complete

### Simple MCP Server Tools

The Simple MCP server implements the following tools:

1. **check_docker_status**: Check the status of Docker and running containers
2. **setup_docker_env**: Set up a Docker testing environment with PostgreSQL and Redis
3. **run_test**: Run tests on the RedBarSushiAI project (various test types)
4. **cleanup_docker_env**: Clean up the Docker environment after testing
5. **echo**: Simple echo tool for testing connectivity

### Simple MCP Test Types

The `run_test` tool supports several test types:

- **basic**: Basic connectivity tests for PostgreSQL and Redis
- **database**: Database schema creation and CRUD operations
- **redis**: Redis connection and key-value operations
- **menu**: Menu schema creation, data insertion, and querying
- **order**: Order schema creation, order processing, and querying
- **full_menu**: Comprehensive menu integration tests using Python
- **full_order**: Comprehensive order integration tests using Python
- **all**: End-to-end integration tests across all components

## Setup

### For Basic Refactor Testing

```bash
# Run the setup script
./mcp/setup.sh
```

### For Docker Environment Testing

```bash
# Run the Docker setup script
./mcp/setup_docker_mcp.sh
```

### For Simple MCP Server

```bash
# Run the Simple MCP startup script
./start_redbarsushi_mcp.sh
```

These scripts:
1. Create a Python virtual environment for the MCP server
2. Install the required packages
3. Make the MCP server scripts executable
4. Register the MCP servers with Claude
5. Start the server in the background

## Usage

### Basic Refactor Testing

After setting up the basic test server, restart Claude and use the following commands:

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

### Docker Environment Testing

After setting up the Docker test server, restart Claude and use the following commands:

```
# Check Docker environment status
/mcp redbarsushi-docker-test check_docker_status

# Set up Docker environment
/mcp redbarsushi-docker-test setup_docker_env project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Run import tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="imports"

# Run database tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="database"

# Run Redis tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="redis"

# Run Flask blueprint tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="flask"

# Run end-to-end tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="e2e"

# Run menu utility tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="menu"

# Run agent utility tests in Docker
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="agents"

# Run all tests (most comprehensive)
/mcp redbarsushi-docker-test run_docker_test project_path="/home/proxyie/MySoftware/RedBarSushiAI" test_type="all"

# View PostgreSQL logs
/mcp redbarsushi-docker-test view_postgres_logs project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# View Redis logs
/mcp redbarsushi-docker-test view_redis_logs project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# View application logs
/mcp redbarsushi-docker-test view_app_logs project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Clean up Docker environment when done
/mcp redbarsushi-docker-test cleanup_docker_env project_path="/home/proxyie/MySoftware/RedBarSushiAI"
```

### Simple MCP Server Testing

After starting the simple MCP server with the startup script, use Claude with these commands:

```
# Check if the server is connected
/mcp

# Check Docker environment status
/mcp check_docker_status

# Set up Docker environment
/mcp setup_docker_env project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Run basic connectivity tests
/mcp run_test test_type="basic"

# Run tests for the menu system
/mcp run_test test_type="menu"

# Run tests for the order system
/mcp run_test test_type="order"

# Run full menu integration tests
/mcp run_test test_type="full_menu"

# Run full order integration tests
/mcp run_test test_type="full_order"

# Run all tests (most comprehensive)
/mcp run_test test_type="all"

# Clean up Docker environment when done
/mcp cleanup_docker_env
```

## Database Schema

The tests create and interact with the following database schema:

### Menu Schema
- `menu_categories`: Menu categories
- `menu_items`: Individual menu items with prices
- `menu_modifier_groups`: Groups of modifiers
- `menu_modifiers`: Individual modifiers with prices
- `item_modifier_groups`: Links items to modifier groups
- `menu_name_variants`: Natural language variants for menu items

### Order Schema
- `orders`: Customer orders with status
- `order_items`: Items in an order
- `order_item_modifiers`: Modifiers for order items
- `locations`: Restaurant locations

## Redis Data

The Redis instance is used for:

1. **Caching menu data**: Fast access to menu items by PLU
2. **Managing carts**: Storing customer cart data during ordering
3. **Storing conversation context**: Finite State Machine (FSM) state and context

## Requirements

- Docker and Docker Compose (for Docker testing)
- Python 3.9+ with pip
- jq (for JSON processing in the setup scripts)

## Troubleshooting

If you encounter any issues:

1. Make sure Docker is running (for Docker testing)
2. Check that the MCP servers are registered correctly with Claude
3. Verify that the project path is correct
4. Look at the logs for detailed error messages
5. Run `docker ps` to see if containers are running properly
6. Run `docker-compose logs` to see detailed container logs

For Simple MCP Server issues:

1. Check the log file at `mcp_server.log`
2. Kill any existing server process with `pkill -f "python.*mcp/simple_mcp_server.py"`
3. Restart the server with `./start_redbarsushi_mcp.sh`

If the tests fail, fix the issues in your refactored code and try again.