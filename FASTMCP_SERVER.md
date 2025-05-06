# RedBarSushiAI FastMCP Server

This document provides instructions on how to set up and use the FastMCP server for RedBarSushiAI.

## Overview

The FastMCP server for RedBarSushiAI provides tools for menu management, order processing, and restaurant information through the Model Context Protocol (MCP). It is built using the FastMCP framework from the MCP library, which provides a more ergonomic interface for building MCP servers.

## Installation Options

### Option 1: Local Installation

1. Create a virtual environment:

```bash
python -m venv mcp_venv
source mcp_venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r mcp/requirements.txt
```

### Option 2: Docker Installation

Use Docker Compose to run the FastMCP server along with PostgreSQL and Redis:

```bash
./run_docker_fastmcp.sh
```

This will start the FastMCP server on port 8050, PostgreSQL on port 5433, and Redis on port 6380.

## Starting the Server

### Local Mode

Use the provided script to start the server locally:

```bash
./start_fastmcp.sh
```

This will start the FastMCP server on port 8050.

### Docker Mode

Use the provided script to start the server in Docker:

```bash
./run_docker_fastmcp.sh
```

## Registering with Claude

To register the FastMCP server with Claude, use the provided script:

```bash
./add_mcp_config.sh
```

This will add the FastMCP server to your Claude configuration and start the server in the background.

Alternatively, you can manually register the server with Claude:

```bash
claude mcp add redbarsushi-mcp http://localhost:8050
```

## Testing the Server

You can test the server using the provided test client:

```bash
python test_fastmcp_client.py
```

This will test the health endpoint, available tools, and some basic functionality.

## Project Structure

```
mcp/
├── main.py                 # Main FastMCP server entry point
├── redbarsushi_mcp/        # RedBarSushiAI MCP package
│   ├── __init__.py         # Package initialization
│   └── utils.py            # Utility functions
├── requirements.txt        # Python dependencies
└── Dockerfile.fastmcp      # Docker configuration
```

## Available Tools

The FastMCP server provides the following tools:

### Menu Management

- `get_menu_items(category_id)`: Get menu items, optionally filtered by category.
- `get_menu_categories()`: Get menu categories.
- `search_menu_items(query)`: Search menu items by name or description.

### Cart Management

- `get_cart(session_id)`: Get the current cart for a session.
- `add_to_cart(session_id, item_plu, quantity, modifiers)`: Add an item to the cart.
- `remove_from_cart(session_id, item_index)`: Remove an item from the cart.
- `clear_cart(session_id)`: Clear the cart.

### Order Processing

- `place_order(session_id, customer_name, customer_phone, order_type, delivery_address)`: Place an order from the cart.

### Restaurant Information

- `get_restaurant_info_tool()`: Get information about the restaurant.

### Testing

- `echo(message)`: Echo a message back (for testing).

## API Endpoints

The FastMCP server provides the following endpoints:

- `GET /health`: Check the health of the server.
- `GET /tools`: List all available tools.
- `POST /tools`: Execute a tool with arguments.
- `GET /sse`: Server-Sent Events endpoint for Claude integration.

## Environment Variables

The server uses the following environment variables:

- `HOST`: The host to bind to (default: "0.0.0.0").
- `PORT`: The port to listen on (default: 8050).
- `DATABASE_URL`: The database connection URL (default: "postgresql://postgres:postgres@localhost:5432/redbarsushi").
- `REDIS_URL`: The Redis connection URL (default: "redis://localhost:6379/0").

## Development

To modify the server, edit the files in the `mcp/redbarsushi_mcp` directory. New tools can be added by defining new functions with the `@mcp.tool()` decorator in `mcp/main.py`.

### Adding a New Tool

1. Define a new function in `mcp/main.py` with the `@mcp.tool()` decorator:

```python
@mcp.tool()
async def my_new_tool(ctx: Context, param1: str, param2: int = 0) -> str:
    """
    Description of the new tool.
    
    Args:
        ctx: The MCP server provided context
        param1: Description of param1
        param2: Description of param2 (optional)
        
    Returns:
        JSON string with result
    """
    # Tool implementation
    return json.dumps({"success": True, "result": "Tool output"})
```

2. Restart the server to make the new tool available.

## Cleanup

To stop the FastMCP server and clean up:

```bash
./cleanup_fastmcp.sh
```

To also remove the FastMCP server from Claude configuration:

```bash
./cleanup_fastmcp.sh --remove-config
```

## Troubleshooting

If you encounter issues with the server, check the logs in `mcp/redbarsushi_mcp.log`. Common issues include:

- Database connection errors: Check that PostgreSQL is running and accessible.
- Redis connection errors: Check that Redis is running and accessible.
- Port conflicts: Check if another process is using port 8050.

You can also check the server status with:

```bash
curl http://localhost:8050/health
```

For Docker deployments, check the logs with:

```bash
docker-compose -f docker-compose-fastmcp.yml logs fastmcp
```