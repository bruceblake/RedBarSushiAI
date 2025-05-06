# RedBarSushiAI MCP Server

The Model Context Protocol (MCP) server for RedBarSushiAI provides tools for testing and debugging the application.

## Directory Structure

- **src/**: Main implementation files
  - `redbarsushi_mcp.py`: Primary MCP server implementation with all tools
  - `utils.py`: Utility functions used by the server

- **docker/**: Docker-related files
  - `Dockerfile.fastmcp`: Dockerfile for FastMCP-based server
  - `Dockerfile.mcp`: Dockerfile for basic MCP server
  - `entrypoint.sh`: Docker entrypoint script

- **db/**: Database initialization scripts
  - Contains SQL schema and seed data

- **logs/**: Server log files
  - Log files from various server runs

- **archive/**: Old implementation files
  - Previous versions of the MCP server

## Tools

The MCP server provides the following tools for testing and debugging:

1. **echo**: Simple echo tool for testing connectivity
2. **check_docker_status**: Check Docker availability and running containers
3. **setup_docker_env**: Set up Docker environment with PostgreSQL and Redis
4. **run_test**: Run different types of tests (basic, database, redis, menu, order, routes, etc.)
5. **cleanup_docker_env**: Clean up Docker environment after testing
6. **inspect_db_tables**: Inspect database tables and their contents
7. **inspect_redis_keys**: Inspect Redis keys and their values
8. **system_diagnostics**: Run comprehensive system diagnostics

## Usage

Start the server with:

```bash
cd /home/proxyie/MySoftware/RedBarSushiAI
bash start_redbarsushi_mcp.sh
```

Then use Claude with commands like:

```
/mcp check_docker_status
/mcp setup_docker_env project_path="/home/proxyie/MySoftware/RedBarSushiAI"
/mcp run_test test_type="basic"
```

Stop the server with:

```bash
pkill -f "python.*mcp/src/redbarsushi_mcp.py"
```
EOF < /dev/null