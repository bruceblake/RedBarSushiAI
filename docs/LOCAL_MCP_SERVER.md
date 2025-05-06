# RedBarSushiAI Local MCP Testing Environment

This document explains how to set up and use the local MCP (Model Context Protocol) server Docker environment for testing RedBarSushiAI locally before deploying to staging.

## Overview

The local MCP server environment replicates the Render staging stack with:
- MCP JSON-RPC server with the same tools (`run_test`, `echo`, etc.)
- PostgreSQL database with staging-equivalent schema and seed data
- Redis instance for conversation state and caching
- Proper networking between services

This allows you to run the same tests locally that would be run against the staging environment, providing faster feedback cycles and reducing the risk of staging breakage.

## Prerequisites

- Docker Engine v20.10+ 
- Docker Compose v1.29+
- Python 3.9+
- curl (for validation)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/RedBarSushiAI.git
   cd RedBarSushiAI
   ```

2. **Configure environment**
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local if needed
   ```

3. **Start the environment**
   ```bash
   docker-compose up -d
   ```

4. **Validate the setup**
   ```bash
   python mcp/validate_local_mcp.py
   ```

5. **Run tests**
   ```bash
   # Run the MCP tests
   python tests/mcp/test_local_mcp.py
   
   # Or run individual tests with curl:
   
   # Basic test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tool/call","params":{"name":"run_test","arguments":{"test_type":"basic"}}}'
   
   # Menu test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tool/call","params":{"name":"run_test","arguments":{"test_type":"menu"}}}'
   
   # Order test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tool/call","params":{"name":"run_test","arguments":{"test_type":"order"}}}'
   
   # All tests
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tool/call","params":{"name":"run_test","arguments":{"test_type":"all"}}}'
   ```

6. **Use with Claude Code**
   Use the following command in Claude Code to connect to your local MCP server:
   ```
   /mcp run_test test_type="basic"
   ```

7. **Shutdown the environment**
   ```bash
   docker-compose down -v  # -v removes volumes for a clean slate
   ```

## Available MCP Methods

The local MCP server implements the full MCP JSON-RPC 2.0 protocol and supports the following methods:

### Control Methods

- **initialize**: Initialize the MCP session
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "sampling": {}
      },
      "clientInfo": {
        "name": "MCP Test Client",
        "version": "1.0.0"
      }
    }
  }
  ```

- **tools/list**: List available tools
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }
  ```

### Tool Methods

- **tool/call**: Call a tool
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tool/call",
    "params": {
      "name": "echo",
      "arguments": {
        "message": "Hello, World!"
      }
    }
  }
  ```

### Available Tools

- **echo**: Simple echo test
  ```json
  {"name": "echo", "arguments": {"message": "Hello, World!"}}
  ```

- **check_docker_status**: Check Docker container status
  ```json
  {"name": "check_docker_status", "arguments": {}}
  ```

- **setup_docker_env**: Set up Docker testing environment
  ```json
  {"name": "setup_docker_env", "arguments": {"project_path": "/path/to/project"}}
  ```

- **run_test**: Run tests against the local environment
  ```json
  {"name": "run_test", "arguments": {"test_type": "basic"}}
  ```
  
  Available test types:
  - `basic`: Basic connectivity tests
  - `database`: Database schema and CRUD operations
  - `redis`: Redis connection and operations
  - `menu`: Menu functionality tests
  - `order`: Order processing tests
  - `full_menu`: Comprehensive menu integration tests
  - `full_order`: Comprehensive order integration tests
  - `all`: End-to-end tests across all components

- **cleanup_docker_env**: Clean up Docker environment
  ```json
  {"name": "cleanup_docker_env", "arguments": {}}
  ```

## Service Details

### MCP Server

- **Port**: 4000 (configurable in `.env.local`)
- **Endpoints**:
  - `/mcp`: JSON-RPC endpoint for MCP methods
  - `/health`: Health check endpoint
- **Protocol Version**: 2024-11-05

### PostgreSQL

- **Port**: 5432 (configurable in `.env.local`)
- **Credentials**: postgres/postgres (configurable in `.env.local`)
- **Database**: redbarsushi
- **Schema**: Includes all tables required for menu and order processing

### Redis

- **Port**: 6379 (configurable in `.env.local`)
- **No authentication by default**
- **Used for**: Caching, conversation state management

## Directory Structure

```
mcp/
├── Dockerfile.mcp       # Dockerfile for MCP server
├── README.md            # General MCP server documentation
├── db/                  # Database initialization scripts
│   └── init/
│       ├── 01_schema.sql    # Database schema
│       └── 02_seed_data.sql # Initial seed data
├── db_init.py           # Python script for database initialization
├── enhanced_mcp_server.py # MCP server implementation
├── entrypoint.sh        # Docker entrypoint script
├── requirements.txt     # Python dependencies
├── simple_mcp_server.py # Original MCP server
└── validate_local_mcp.py # Validation script
```

## Troubleshooting

### Common Issues

1. **Docker containers not starting**
   ```bash
   docker-compose ps  # Check status
   docker-compose logs  # View logs
   ```

2. **Health checks failing**
   ```bash
   # Check MCP server logs
   docker-compose logs mcp-server
   
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Check Redis logs
   docker-compose logs redis
   ```

3. **Database migration issues**
   ```bash
   # Connect to PostgreSQL
   docker-compose exec postgres psql -U postgres -d redbarsushi
   
   # Check if tables exist
   \dt
   ```

4. **Redis connectivity issues**
   ```bash
   # Connect to Redis
   docker-compose exec redis redis-cli
   
   # Test connection
   ping
   ```

### Resetting the Environment

To completely reset the environment:

```bash
docker-compose down -v  # Removes all containers and volumes
docker-compose up -d    # Restart with fresh services
```

## Development Notes

- The seed data provides minimal test data suitable for basic testing
- For more comprehensive testing, you may need to add more seed data
- The local environment is isolated from staging/production for safety
- No production credentials or sensitive data should be used in this environment

## Updating the Environment

When the staging environment changes:

1. Update the database schema in `mcp/db/init/01_schema.sql`
2. Update the seed data in `mcp/db/init/02_seed_data.sql`
3. Rebuild the environment:
   ```bash
   docker-compose down -v
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Additional Resources

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [Docker Compose Documentation](https://docs.docker.com/compose/)