# Local MCP Server Docker Environment

This document outlines the implementation plan for a containerized MCP server environment that mirrors the Render staging stack for local testing.

## High Level Objective

Create a Docker Compose-based local environment that fully replicates our Render staging infrastructure, including:
- MCP JSON-RPC server with the same tools (`run_test`, `echo`, etc.)
- PostgreSQL database with staging-equivalent schema and seed data
- Redis instance for conversation state and caching
- Proper networking between services

The environment should enable developers to run the same end-to-end tests locally that would be run against staging, providing faster feedback cycles and reducing the risk of staging breakage.

## Method Changes

### 1. Docker Compose Configuration

Create a `docker-compose.yml` file in the project root with three primary services:

```yaml
version: '3.8'

services:
  mcp-server:
    build:
      context: ./mcp
      dockerfile: Dockerfile.mcp
    ports:
      - "${MCP_PORT:-4000}:4000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/redbarsushi
      - MCP_PROTOCOL_VERSION=2024-11-05
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - ./mcp:/app/mcp
    networks:
      - redbarsushi-network

  postgres:
    image: postgres:14
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=redbarsushi
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./mcp/db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - redbarsushi-network

  redis:
    image: redis:6
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - redbarsushi-network

networks:
  redbarsushi-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
```

### 2. MCP Server Implementation

#### 2.1 Create Dockerfile for MCP Server

Create `mcp/Dockerfile.mcp`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY simple_mcp_server.py .
COPY entrypoint.sh .

# Make scripts executable
RUN chmod +x entrypoint.sh

# HTTP port for MCP server
EXPOSE 4000

# Startup command
ENTRYPOINT ["/app/entrypoint.sh"]
```

#### 2.2 Create MCP Server Entrypoint

Create `mcp/entrypoint.sh`:

```bash
#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h postgres -U postgres -d redbarsushi -c '\q'; do
  sleep 1
done
echo "PostgreSQL is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis..."
until redis-cli -h redis ping | grep -q PONG; do
  sleep 1
done
echo "Redis is ready!"

# Run database migrations if not already done
if [ ! -f /data/migrations_applied ]; then
  echo "Running database migrations..."
  python db_init.py
  touch /data/migrations_applied
fi

# Start the MCP server
echo "Starting MCP server..."
exec python simple_mcp_server.py
```

#### 2.3 Enhance the Simple MCP Server

Modify `mcp/simple_mcp_server.py` to add health endpoints and ensure it works properly in Docker:

```python
# Add health endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the MCP server."""
    try:
        # Check PostgreSQL
        with Session() as session:
            session.execute(text("SELECT 1"))
            postgres_status = "connected"
    except Exception as e:
        postgres_status = f"error: {str(e)}"
    
    # Check Redis
    try:
        redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    return jsonify({
        "mcp": "ok",
        "postgres": postgres_status,
        "redis": redis_status
    })
```

### 3. Database Initialization Scripts

Create initialization scripts for the PostgreSQL database:

#### 3.1 Schema Initialization Script

Create `mcp/db/init/01_schema.sql`:

```sql
-- Create required schemas
CREATE SCHEMA IF NOT EXISTS public;

-- Menu tables
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Other tables omitted for brevity (would include the complete schema)
```

#### 3.2 Seed Data Script

Create `mcp/db/init/02_seed_data.sql`:

```sql
-- Insert sample menu categories
INSERT INTO menu_categories (name, description) VALUES
('Sushi Rolls', 'Fresh and delicious sushi rolls'),
('Sashimi', 'Premium cuts of raw fish'),
('Appetizers', 'Starters to begin your meal')
ON CONFLICT DO NOTHING;

-- Insert sample menu items
INSERT INTO menu_items (category_id, name, description, price, plu) VALUES
(1, 'California Roll', 'Crab, avocado, cucumber', 1200, 'CALI-ROLL'),
(1, 'Spicy Tuna Roll', 'Fresh tuna with spicy sauce', 1300, 'SPICY-TUNA'),
(2, 'Salmon Sashimi', 'Fresh cuts of salmon', 1500, 'SALMON-SASH'),
(3, 'Edamame', 'Steamed soybeans with sea salt', 600, 'EDAMAME')
ON CONFLICT DO NOTHING;

-- Other seed data omitted for brevity
```

### 4. Environment Configuration

Create a template `.env.local.example` file:

```
# MCP Server
MCP_PORT=4000
MCP_PROTOCOL_VERSION=2024-11-05

# PostgreSQL
POSTGRES_PORT=5432
POSTGRES_PASSWORD=postgres

# Redis
REDIS_PORT=6379
```

Add to `.gitignore`:
```
.env.local
```

## Test Changes

### 1. Adapt Tests for Local Environment

Create a new test configuration file `tests/config/local_mcp_config.py`:

```python
"""Configuration for local MCP testing."""

import os

# Local MCP server URL
MCP_SERVER_URL = "http://localhost:4000/mcp"

# Test database URL (for local testing)
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")

# Test Redis URL (for local testing)
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Test configuration
TEST_CONFIG = {
    "environment": "local",
    "mcp_server": MCP_SERVER_URL,
    "database": TEST_DATABASE_URL,
    "redis": TEST_REDIS_URL
}
```

### 2. Create Local MCP Test Runner

Create `tests/mcp/test_local_mcp.py`:

```python
"""Tests for the local MCP server environment."""

import requests
import json
import pytest
from tests.config.local_mcp_config import MCP_SERVER_URL

def call_mcp_method(method, params=None):
    """Call an MCP method on the local server."""
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    response = requests.post(MCP_SERVER_URL, json=payload)
    return response.json()

def test_mcp_echo():
    """Test the echo method of the MCP server."""
    message = "Hello, MCP!"
    result = call_mcp_method("echo", {"message": message})
    
    assert "result" in result
    assert result["result"]["content"][0]["text"] == message

def test_mcp_health():
    """Test the health endpoint of the MCP server."""
    response = requests.get(MCP_SERVER_URL.replace("/mcp", "/health"))
    result = response.json()
    
    assert response.status_code == 200
    assert result["mcp"] == "ok"
    assert result["postgres"] == "connected"
    assert result["redis"] == "connected"

def test_mcp_run_test_basic():
    """Test the run_test method with basic test type."""
    result = call_mcp_method("run_test", {"test_type": "basic"})
    
    assert "result" in result
    assert "success" in result["result"]
    assert result["result"]["success"] == True

# Additional tests for database, redis, menu, order, etc.
```

## Self Validation

Create a validation script to verify the local MCP server setup:

Create `mcp/validate_local_mcp.py`:

```python
#!/usr/bin/env python
"""
Validation script for the local MCP server environment.
Runs through a series of checks to ensure the environment is working correctly.
"""

import argparse
import json
import requests
import sys
import time

def check_service(url, description):
    """Check if a service is available at the given URL."""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {description} is available")
            return True
        else:
            print(f"❌ {description} returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ {description} is not available: {str(e)}")
        return False

def call_mcp_method(base_url, method, params=None):
    """Call an MCP method on the server."""
    if params is None:
        params = {}
    
    url = f"{base_url}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to call MCP method {method}: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Validate local MCP server setup.')
    parser.add_argument('--host', default='localhost', help='Host where MCP server is running')
    parser.add_argument('--port', default=4000, type=int, help='Port where MCP server is running')
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    
    print("\n----- Local MCP Server Validation -----\n")
    
    # Step 1: Check if MCP server is running
    print("Checking if MCP server is running...")
    if not check_service(f"{base_url}/health", "MCP server health endpoint"):
        sys.exit(1)
    
    # Step 2: Check MCP echo method
    print("\nTesting MCP echo method...")
    echo_result = call_mcp_method(base_url, "echo", {"message": "Hello, MCP!"})
    if echo_result and "result" in echo_result:
        print("✅ MCP echo method working")
    else:
        print("❌ MCP echo method failed")
        sys.exit(1)
    
    # Step 3: Check MCP run_test basic method
    print("\nTesting MCP run_test basic method...")
    test_result = call_mcp_method(base_url, "run_test", {"test_type": "basic"})
    if test_result and "result" in test_result and test_result["result"].get("success") == True:
        print("✅ MCP run_test basic method working")
    else:
        print("❌ MCP run_test basic method failed")
        sys.exit(1)
    
    # Step 4: Check database connection
    print("\nTesting database connection through MCP...")
    db_result = call_mcp_method(base_url, "run_test", {"test_type": "database"})
    if db_result and "result" in db_result and db_result["result"].get("success") == True:
        print("✅ Database connection working")
    else:
        print("❌ Database connection failed")
        sys.exit(1)
    
    # Step 5: Check Redis connection
    print("\nTesting Redis connection through MCP...")
    redis_result = call_mcp_method(base_url, "run_test", {"test_type": "redis"})
    if redis_result and "result" in redis_result and redis_result["result"].get("success") == True:
        print("✅ Redis connection working")
    else:
        print("❌ Redis connection failed")
        sys.exit(1)
    
    print("\n----- Validation Complete -----")
    print("✅ Local MCP server environment is working correctly")

if __name__ == "__main__":
    main()
```

## README Changes

Create a comprehensive README for the local MCP server:

```markdown
# RedBarSushiAI Local MCP Testing Environment

This document explains how to set up and use the local MCP server Docker environment for testing RedBarSushiAI.

## Overview

The local MCP server environment replicates the Render staging stack with:
- MCP JSON-RPC server
- PostgreSQL database
- Redis instance

This allows you to run the same tests locally that would be run against the staging environment.

## Prerequisites

- Docker Engine v20.10+ 
- Docker Compose v1.29+
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
   # Basic test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"run_test","params":{"test_type":"basic"}}'
   
   # Menu test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"run_test","params":{"test_type":"menu"}}'
   
   # Order test
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"run_test","params":{"test_type":"order"}}'
   
   # All tests
   curl -X POST http://localhost:4000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"run_test","params":{"test_type":"all"}}'
   ```

6. **Shutdown the environment**
   ```bash
   docker-compose down -v  # -v removes volumes for a clean slate
   ```

## Available MCP Methods

The local MCP server supports the following methods:

- **echo**: Simple echo test
  ```json
  {"jsonrpc":"2.0","id":1,"method":"echo","params":{"message":"Hello, World!"}}
  ```

- **run_test**: Run tests against the local environment
  ```json
  {"jsonrpc":"2.0","id":1,"method":"run_test","params":{"test_type":"basic"}}
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

## Service Details

### MCP Server

- **Port**: 4000 (configurable in `.env.local`)
- **Endpoints**:
  - `/mcp`: JSON-RPC endpoint for MCP methods
  - `/health`: Health check endpoint

### PostgreSQL

- **Port**: 5432 (configurable in `.env.local`)
- **Credentials**: postgres/postgres (configurable in `.env.local`)
- **Database**: redbarsushi

### Redis

- **Port**: 6379 (configurable in `.env.local`)
- **No authentication by default**

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
```

This comprehensive plan provides all the components needed to implement a Docker-based local MCP server environment that mirrors the Render staging stack. The implementation follows the requirements specified in the PRD and provides detailed documentation for setting up, using, and troubleshooting the environment.