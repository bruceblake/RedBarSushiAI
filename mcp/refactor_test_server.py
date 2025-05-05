#!/usr/bin/env python3
"""
MCP Server for testing refactored RedBarSushiAI code.
This server provides tools to test the refactored code in a Docker environment
with Redis and PostgreSQL that resembles the staging environment.
"""

import os
import sys
import json
import asyncio
import subprocess
import tempfile
from typing import Dict, List, Any, Optional

# Import MCP SDK
try:
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.types import TextContent
except ImportError:
    print("Error: MCP SDK not installed. Install with 'pip install mcp'")
    sys.exit(1)

# Create Docker Compose configuration template
DOCKER_COMPOSE = """
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: redbarsushi_staging_db_user
      POSTGRES_PASSWORD: testing_password
      POSTGRES_DB: redbarsushi_staging_db
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U redbarsushi_staging_db_user -d redbarsushi_staging_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build:
      context: {project_path}
      dockerfile: Dockerfile.test
    environment:
      - SQLALCHEMY_DATABASE_URI=postgresql://redbarsushi_staging_db_user:testing_password@postgres:5432/redbarsushi_staging_db
      - DATABASE_URL=postgresql://redbarsushi_staging_db_user:testing_password@postgres:5432/redbarsushi_staging_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - FLASK_APP=run.py
      - FLASK_ENV=testing
      - TESTING=true
      - TEST_TYPE={test_type}
    volumes:
      - {project_path}:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
"""

# Create test Dockerfile template
TEST_DOCKERFILE = """
# Use the same base as production
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PORT=8080 \\
    FLASK_APP=run.py \\
    FLASK_ENV=testing \\
    TESTING=true \\
    NO_X11=1 \\
    HEADLESS=1 \\
    PYNPUT_HEADLESS=1 \\
    OPENAI_REALTIME_NO_DISPLAY=1

# Install system dependencies
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
        git \\
        gcc \\
        g++ \\
        libpq-dev \\
        curl \\
        && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements.prod.txt requirements.docker.txt ./

# Install dependencies with fallbacks
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \\
    pip install --no-cache-dir psycopg2-binary && \\
    pip install --no-cache-dir -r requirements.docker.txt || \\
    pip install --no-cache-dir -r requirements.prod.txt || \\
    pip install --no-cache-dir -r requirements.txt

# Create test script
RUN echo '#!/bin/bash\\n\\
echo "=================================="\\n\\
echo "Running refactored code tests..."\\n\\
echo "=================================="\\n\\
\\n\\
# Function to run a specific test\\n\\
run_test() {\\n\\
    test_name=$1\\n\\
    test_cmd=$2\\n\\
    echo "\\n>> Running test: $test_name"\\n\\
    echo "> Command: $test_cmd"\\n\\
    echo "-----------------------------------"\\n\\
    eval $test_cmd\\n\\
    if [ $? -eq 0 ]; then\\n\\
        echo "✅ Test passed: $test_name"\\n\\
        return 0\\n\\
    else\\n\\
        echo "❌ Test failed: $test_name"\\n\\
        return 1\\n\\
    fi\\n\\
}\\n\\
\\n\\
# Check environment variables\\n\\
echo ">> Environment variables:"\\n\\
echo "DATABASE_URL: $DATABASE_URL"\\n\\
echo "REDIS_URL: $REDIS_URL"\\n\\
echo "SQLALCHEMY_DATABASE_URI: $SQLALCHEMY_DATABASE_URI"\\n\\
echo "FLASK_APP: $FLASK_APP"\\n\\
echo "FLASK_ENV: $FLASK_ENV"\\n\\
echo "TESTING: $TESTING"\\n\\
echo "TEST_TYPE: $TEST_TYPE"\\n\\
\\n\\
all_passed=true\\n\\
\\n\\
# Import tests\\n\\
if [ "$TEST_TYPE" = "imports" ] || [ "$TEST_TYPE" = "all" ]; then\\n\\
    run_test "Order module import test" "python -c \\"from app.routes.order import order_bp; print(\\\\"✅ Successfully imported order_bp\\\\")\\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
\\n\\
    run_test "Agent utils import test" "python -c \\"from app.utils.agent_utils import OrderParsingAgent; print(\\\\"✅ Successfully imported OrderParsingAgent\\\\")\\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
\\n\\
    run_test "ContactRequest model import test" "python -c \\"from app.models import ContactRequest; print(\\\\"✅ Successfully imported ContactRequest\\\\")\\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
fi\\n\\
\\n\\
# Database tests\\n\\
if [ "$TEST_TYPE" = "database" ] || [ "$TEST_TYPE" = "all" ]; then\\n\\
    run_test "Database connection test" "python -c \\"\\n\\
    import os\\n\\
    from app import create_app, db\\n\\
    from app.models import Order, ContactRequest\\n\\
    print(f\\\\\\\"Using database: {os.environ.get(\\\\\\\\\\\\\\\"SQLALCHEMY_DATABASE_URI\\\\\\\\\\\\\\\")}\\\\\\\")\\n\\
    app = create_app()\\n\\
    with app.app_context():\\n\\
        # Try to create and query a test record\\n\\
        test_contact = ContactRequest(id=\\\\\\"test-id\\\\\\", customer_name=\\\\\\"Test User\\\\\\", customer_phone=\\\\\\"123456789\\\\\\", request_type=\\\\\\"test\\\\\\")\\n\\
        try:\\n\\
            db.session.add(test_contact)\\n\\
            db.session.commit()\\n\\
            result = ContactRequest.query.filter_by(id=\\\\\\"test-id\\\\\\").first()\\n\\
            assert result is not None, \\\\\\"Failed to retrieve test record\\\\\\"\\n\\
            print(\\\\\\"✅ Database test passed\\\\\\")\\n\\
        except Exception as e:\\n\\
            print(f\\\\\\"DB Error: {str(e)}\\\\\\")\\n\\
            raise\\n\\
    \\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
fi\\n\\
\\n\\
# Redis tests\\n\\
if [ "$TEST_TYPE" = "redis" ] || [ "$TEST_TYPE" = "all" ]; then\\n\\
    run_test "Redis connection test" "python -c \\"\\n\\
    import redis\\n\\
    import os\\n\\
    redis_url = os.environ.get(\\\\\\"REDIS_URL\\\\\\")\\n\\
    print(f\\\\\\"Using Redis URL: {redis_url}\\\\\\")\\n\\
    r = redis.Redis.from_url(redis_url)\\n\\
    r.set(\\\\\\"test-key\\\\\\", \\\\\\"test-value\\\\\\")\\n\\
    value = r.get(\\\\\\"test-key\\\\\\")\\n\\
    assert value.decode() == \\\\\\"test-value\\\\\\", f\\\\\\"Expected test-value, got {value}\\\\\\"\\n\\
    print(\\\\\\"✅ Redis connection test passed\\\\\\")\\n\\
    \\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
fi\\n\\
\\n\\
# Blueprint registration tests\\n\\
if [ "$TEST_TYPE" = "flask" ] || [ "$TEST_TYPE" = "all" ]; then\\n\\
    run_test "Flask blueprint registration" "python -c \\"\\n\\
    from app import create_app\\n\\
    app = create_app()\\n\\
    print(\\\\\\"Registered blueprints:\\\\\\")\\n\\
    for name, blueprint in app.blueprints.items():\\n\\
        print(f\\\\\\"  - {name}\\\\\\")\\n\\
    assert \\\\\\"order\\\\\\" in app.blueprints, \\\\\\"order blueprint not registered\\\\\\"\\n\\
    print(\\\\\\"✅ Flask blueprint registration test passed\\\\\\")\\n\\
    \\""\\n\\
    if [ $? -ne 0 ]; then all_passed=false; fi\\n\\
fi\\n\\
\\n\\
# Print test summary\\n\\
echo "\\n====================================="\\n\\
echo "           TEST SUMMARY              "\\n\\
echo "====================================="\\n\\
if $all_passed; then\\n\\
    echo "✅ All tests PASSED"\\n\\
    exit 0\\n\\
else\\n\\
    echo "❌ Some tests FAILED"\\n\\
    exit 1\\n\\
fi\\n\\
' > /app/run_tests.sh && chmod +x /app/run_tests.sh

# Default command to run tests
CMD ["/app/run_tests.sh"]
"""

# Create MCP server
mcp = FastMCP("RefactorTest", version="1.0.0", description="Test RedBarSushiAI refactored code")

@mcp.tool(description="Test the imports in the refactored code")
def test_imports(ctx: Context, project_path: str) -> List[TextContent]:
    """
    Test the imports in the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        List of test results
    """
    return run_docker_test(project_path, "imports")

@mcp.tool(description="Test database connectivity in the refactored code")
def test_database(ctx: Context, project_path: str) -> List[TextContent]:
    """
    Test database connectivity in the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        List of test results
    """
    return run_docker_test(project_path, "database")

@mcp.tool(description="Test Redis connectivity in the refactored code")
def test_redis(ctx: Context, project_path: str) -> List[TextContent]:
    """
    Test Redis connectivity in the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        List of test results
    """
    return run_docker_test(project_path, "redis")

@mcp.tool(description="Test Flask blueprint registration in the refactored code")
def test_flask(ctx: Context, project_path: str) -> List[TextContent]:
    """
    Test Flask blueprint registration in the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        List of test results
    """
    return run_docker_test(project_path, "flask")

@mcp.tool(description="Run all tests on the refactored code")
def test_all(ctx: Context, project_path: str) -> List[TextContent]:
    """
    Run all tests on the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        List of test results
    """
    return run_docker_test(project_path, "all")

def run_docker_test(project_path: str, test_type: str) -> List[TextContent]:
    """
    Run Docker tests for the refactored code.
    
    Args:
        project_path: Path to the RedBarSushiAI project
        test_type: Type of test to run (imports, database, redis, flask, all)
    
    Returns:
        List of test results
    """
    results = []
    results.append(TextContent(text=f"Running {test_type} tests for project at {project_path}"))
    
    # Validate project path
    if not os.path.exists(project_path):
        results.append(TextContent(text=f"❌ Error: Project path does not exist: {project_path}"))
        return results
    
    try:
        # Create temporary files for Docker configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as compose_file:
            compose_file.write(DOCKER_COMPOSE.format(
                project_path=project_path,
                test_type=test_type
            ))
            compose_path = compose_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dockerfile', delete=False) as dockerfile:
            dockerfile.write(TEST_DOCKERFILE)
            dockerfile_path = dockerfile.name
        
        # Copy the Dockerfile to the project directory
        subprocess.run(
            ["cp", dockerfile_path, os.path.join(project_path, "Dockerfile.test")],
            check=True
        )
        
        results.append(TextContent(text=f"✅ Created Docker configurations"))
        
        # Run the Docker Compose test
        results.append(TextContent(text=f"🚀 Starting Docker containers for testing..."))
        
        # Capture Docker output to a file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as output_file:
            process = subprocess.Popen(
                ["docker-compose", "-f", compose_path, "up", "--build", "--abort-on-container-exit"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=project_path
            )
            
            for line in process.stdout:
                output_file.write(line)
                
            process.wait()
            output_path = output_file.name
        
        # Read the output
        with open(output_path, 'r') as f:
            docker_output = f.read()
        
        # Extract relevant log lines
        test_output = []
        capture_logs = False
        
        for line in docker_output.splitlines():
            if "Running refactored code tests" in line:
                capture_logs = True
                test_output.append(line)
            elif capture_logs and line.strip():
                test_output.append(line)
            
            # Add specific test results to output
            if "✅ Test passed" in line or "❌ Test failed" in line:
                results.append(TextContent(text=line))
            
            # Add test summary
            if "TEST SUMMARY" in line:
                results.append(TextContent(text=line))
                # Add the following summary lines
                summary_index = docker_output.splitlines().index(line)
                for i in range(1, 6):
                    if summary_index + i < len(docker_output.splitlines()):
                        summary_line = docker_output.splitlines()[summary_index + i]
                        results.append(TextContent(text=summary_line))
        
        # Check if the test passed based on exit code
        if process.returncode == 0:
            results.append(TextContent(text=f"✅ {test_type} tests passed!"))
        else:
            results.append(TextContent(text=f"❌ {test_type} tests failed!"))
        
        # Clean up Docker containers
        subprocess.run(
            ["docker-compose", "-f", compose_path, "down", "--volumes"],
            check=True,
            cwd=project_path
        )
        
        # Clean up temporary files
        os.unlink(compose_path)
        os.unlink(dockerfile_path)
        os.unlink(output_path)
        
        # Clean up project Dockerfile
        os.unlink(os.path.join(project_path, "Dockerfile.test"))
        
        results.append(TextContent(text="🧹 Cleaned up test environment"))
        
    except Exception as e:
        results.append(TextContent(text=f"❌ Error running tests: {str(e)}"))
        # Try to clean up
        try:
            subprocess.run(
                ["docker-compose", "-f", compose_path, "down", "--volumes"],
                cwd=project_path
            )
        except:
            pass
            
    return results

async def run_server():
    """Run the MCP server."""
    try:
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(read_stream, write_stream)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_server())