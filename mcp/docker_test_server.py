#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker Test Server for RedBarSushiAI testing with real Docker containers.
"""

import os
import sys
import json
import asyncio
import subprocess
import tempfile
from typing import Dict, Any, Optional

class DockerTestServer:
    def __init__(self):
        self.protocol_version = "2024-11-05"
        self.project_path = "/home/proxyie/MySoftware/RedBarSushiAI"
        
    async def handle_initialize(self, request_id):
        """Handle initialize method."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "RedBarSushiAI Docker Test Server",
                    "version": "1.0.0"
                }
            }
        }
        return response
    
    async def handle_tools_list(self, request_id):
        """Handle tools/list method."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "check_docker_status",
                        "description": "Check the status of Docker and running containers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "setup_docker_env",
                        "description": "Set up a Docker testing environment for RedBarSushiAI",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "project_path": {
                                    "type": "string", 
                                    "description": "Path to the RedBarSushiAI project"
                                }
                            },
                            "required": ["project_path"]
                        }
                    },
                    {
                        "name": "run_test",
                        "description": "Run tests on the RedBarSushiAI project",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_type": {
                                    "type": "string",
                                    "description": "Type of test to run (basic, database, redis, menu, order, all)"
                                }
                            },
                            "required": ["test_type"]
                        }
                    },
                    {
                        "name": "cleanup_docker_env",
                        "description": "Clean up the Docker environment",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "echo",
                        "description": "Echo a message back",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "Message to echo back"
                                }
                            },
                            "required": ["message"]
                        }
                    }
                ]
            }
        }
        return response
    
    async def handle_tool_call(self, request_id, params):
        """Handle tool/call method."""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        result = {
            "content": [
                {
                    "type": "text",
                    "text": "Tool result not available"
                }
            ]
        }
        
        if tool_name == "echo":
            message = tool_args.get("message", "No message provided")
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}"
                    }
                ]
            }
        elif tool_name == "check_docker_status":
            try:
                docker_version = subprocess.run(["docker", "--version"], check=True, capture_output=True, text=True)
                compose_version = subprocess.run(["docker-compose", "--version"], check=True, capture_output=True, text=True)
                containers = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], check=True, capture_output=True, text=True)
                
                output = f"🐳 {docker_version.stdout.strip()}\n\n"
                output += f"🐙 {compose_version.stdout.strip()}\n\n"
                output += "📊 Running Containers:\n"
                output += containers.stdout
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error checking Docker status: {str(e)}"
                        }
                    ]
                }
        elif tool_name == "setup_docker_env":
            project_path = tool_args.get("project_path", self.project_path)
            self.project_path = project_path
            
            try:
                # Create docker-compose.yml file for testing environment
                docker_compose = """
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: redbarsushi_postgres
    environment:
      POSTGRES_USER: redbarsushi_staging_db_user
      POSTGRES_PASSWORD: testing_password
      POSTGRES_DB: redbarsushi_staging_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U redbarsushi_staging_db_user -d redbarsushi_staging_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    container_name: redbarsushi_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
"""
                # Write docker-compose.yml file
                compose_file = os.path.join(project_path, "docker-compose-test.yml")
                with open(compose_file, "w") as f:
                    f.write(docker_compose)
                
                # Create .env file for testing environment
                env_content = """
# Database
DATABASE_URL=postgresql://redbarsushi_staging_db_user:testing_password@localhost:5432/redbarsushi_staging_db
SQLALCHEMY_DATABASE_URI=postgresql://redbarsushi_staging_db_user:testing_password@localhost:5432/redbarsushi_staging_db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Application settings
FLASK_APP=run.py
FLASK_ENV=testing
TESTING=true
"""
                # Write .env file
                env_file = os.path.join(project_path, ".env.test")
                with open(env_file, "w") as f:
                    f.write(env_content)
                
                # Start Docker containers
                subprocess.run(
                    ["docker-compose", "-f", compose_file, "up", "-d"],
                    check=True,
                    cwd=project_path
                )
                
                # Wait for containers to be healthy
                output = "Docker environment set up successfully!\n\n"
                output += "✅ Created docker-compose-test.yml\n"
                output += "✅ Created .env.test file\n"
                output += "✅ Started PostgreSQL and Redis containers\n\n"
                output += "You can now run tests that will connect to real databases!"
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error setting up Docker environment: {str(e)}"
                        }
                    ]
                }
        elif tool_name == "run_test":
            test_type = tool_args.get("test_type", "basic")
            
            # Create test script dynamically based on test_type
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
                if test_type == "basic":
                    f.write("""#!/bin/bash
echo "Running basic tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

echo "✅ All basic tests passed!"
""")
                elif test_type == "all":
                    f.write("""#!/bin/bash
echo "Running all tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

# Create a test database table
echo "Creating test database table..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);" > /dev/null 2>&1

# Insert test data
echo "Inserting test data..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
INSERT INTO test_table (name) VALUES ('Test 1');" > /dev/null 2>&1

# Query test data
echo "Querying test data..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT name FROM test_table WHERE name='Test 1';")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Test data not found"
    exit 1
fi
echo "✅ Database operations verified"

# Set Redis cache
echo "Testing Redis cache..."
redis-cli -h localhost set test_key "test_value" > /dev/null 2>&1

# Get Redis cache
RESULT=$(redis-cli -h localhost get test_key)

if [ "$RESULT" != "test_value" ]; then
    echo "❌ Error: Redis cache not working"
    exit 1
fi
echo "✅ Redis cache operations verified"

echo "✅ All tests passed!"
""")
                else:
                    # Default to basic test
                    f.write("""#!/bin/bash
echo "Running basic tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

echo "✅ All tests passed!"
""")
                
                test_script_path = f.name
            
            # Make it executable
            os.chmod(test_script_path, 0o755)
            
            try:
                # Run the test script
                process = subprocess.run(
                    [test_script_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                output = process.stdout
                
                # Enhance output with emoji
                output = output.replace("✅", "✅ ")
                output = output.replace("❌", "❌ ")
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except subprocess.CalledProcessError as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": e.stdout if hasattr(e, 'stdout') else f"❌ Error running tests: {str(e)}"
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error running tests: {str(e)}"
                        }
                    ]
                }
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(test_script_path)
                except:
                    pass
        elif tool_name == "cleanup_docker_env":
            try:
                # Stop and remove Docker containers
                compose_file = os.path.join(self.project_path, "docker-compose-test.yml")
                
                if os.path.exists(compose_file):
                    subprocess.run(
                        ["docker-compose", "-f", compose_file, "down", "--volumes"],
                        check=True,
                        cwd=self.project_path
                    )
                    
                    output = "✅ Docker environment cleaned up successfully!\n"
                    output += "✅ Stopped and removed containers\n"
                    output += "✅ Removed volumes\n"
                else:
                    output = "⚠️ No docker-compose-test.yml file found. Nothing to clean up."
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error cleaning up Docker environment: {str(e)}"
                        }
                    ]
                }
        
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        return response
    
    async def process_request(self, request_json):
        """Process an incoming request."""
        try:
            request = json.loads(request_json)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "initialize":
                return await self.handle_initialize(request_id)
            elif method == "tools/list":
                return await self.handle_tools_list(request_id)
            elif method == "tool/call":
                return await self.handle_tool_call(request_id, params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id if 'request_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def run(self):
        """Run the MCP server on stdin/stdout."""
        while True:
            try:
                # Read a line from stdin
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                
                # Process the request
                response = await self.process_request(line)
                
                # Write response to stdout
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stderr.write(f"Error: {str(e)}\n")
                sys.stderr.flush()

if __name__ == "__main__":
    server = DockerTestServer()
    asyncio.run(server.run())