# Setting Up MCP Server for RedBarSushiAI E2E Testing

This document outlines the steps for setting up a Mission Control Platform (MCP) server to run end-to-end tests on the RedBarSushiAI staging environment and implement automatic fixing of detected issues.

## Overview

The MCP server will:
1. Connect to the Render staging environment
2. Run E2E tests to verify system functionality
3. Report test results and failures
4. Attempt to fix issues automatically when tests fail

## Available MCP Servers

There are three main MCP servers available for testing RedBarSushiAI:

1. **Basic Refactor Test Server** (`/mcp/refactor_test_server.py`): Tests refactored code with basic checks
2. **Docker Test Server** (`/mcp/docker_test_server.py`): Tests the application in a full Docker environment that closely resembles the Render staging environment
3. **Simple MCP Server** (`/mcp/simple_mcp_server.py`): A standalone JSON-RPC 2.0 implementation for testing with real Docker containers without SDK dependencies

## Prerequisites

- Access to Render dashboard for RedBarSushiAI staging environment
- GitHub repository access for code changes
- API access tokens for necessary services
- A server/VM to host the MCP orchestrator
- Docker and Docker Compose (for Docker-based testing)

## Step 1: Server Setup

### Server Requirements

- Linux-based server (Ubuntu 20.04+ recommended)
- Python 3.11+
- Docker (for containerized test execution)
- Redis (for job queuing)
- PostgreSQL (for test results and logging)

### Installation Commands

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3.11 python3.11-venv python3.11-dev python3-pip -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Redis
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create PostgreSQL user and database
sudo -u postgres psql -c "CREATE USER mcp WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "CREATE DATABASE mcp_testing;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mcp_testing TO mcp;"
```

## Step 2: MCP Service Implementation

Create a Python project for the MCP service with the following structure:

```
redbarsushi-mcp/
├── README.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── mcp/
│   ├── __init__.py
│   ├── config.py
│   ├── app.py
│   ├── models.py
│   ├── scheduler.py
│   ├── db.py
│   ├── render_client.py
│   ├── slack_client.py
│   ├── github_client.py
│   ├── test_runner.py
│   ├── result_analyzer.py
│   ├── fix_generator.py
│   └── utils.py
└── tests/
    ├── __init__.py
    ├── test_render_client.py
    ├── test_test_runner.py
    └── test_fix_generator.py
```

### Key Components:

1. **Scheduler**: Manages when tests are run (scheduled/triggered)
2. **Render Client**: API interactions with Render
3. **Test Runner**: Executes E2E tests from the RedBarSushiAI repo
4. **Result Analyzer**: Interprets test results and identifies issues
5. **Fix Generator**: Creates patches for common issues
6. **GitHub Client**: Creates PRs with fixes when needed

## Step 3: Configuration for RedBarSushiAI

Create the `.env` file for configuration:

```
# Basic configuration
MCP_ENV=production
LOG_LEVEL=INFO

# Database connection
DATABASE_URL=postgresql://mcp:secure_password@localhost:5432/mcp_testing

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

## Step 4: Test Runner Implementation

The test runner will:

1. Clone the RedBarSushiAI repository
2. Configure the test environment
3. Run the E2E tests using pytest
4. Capture and parse test results

Example implementation of `test_runner.py`:

```python
import os
import subprocess
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class TestRunner:
    def __init__(self, config):
        self.config = config
        self.repo_url = f"https://github.com/{config.GITHUB_REPO}.git"
        self.branch = config.GITHUB_TEST_BRANCH or "staging"
        self.base_url = config.TEST_BASE_URL
        
    def prepare_test_environment(self, work_dir: Path) -> Tuple[bool, str]:
        """Set up the test environment in the given directory"""
        try:
            # Clone the repository
            cmd = ["git", "clone", "--depth", "1", "--branch", self.branch, self.repo_url, str(work_dir)]
            subprocess.check_call(cmd)
            
            # Create test environment file
            env_file = work_dir / ".env.test"
            with open(env_file, "w") as f:
                f.write(f"TESTING=True\n")
                f.write(f"BASE_URL={self.base_url}\n")
                f.write(f"TWILIO_ACCOUNT_SID={self.config.TEST_TWILIO_ACCOUNT_SID}\n")
                f.write(f"TWILIO_AUTH_TOKEN={self.config.TEST_TWILIO_AUTH_TOKEN}\n")
                f.write(f"TWILIO_NUMBER={self.config.TEST_TWILIO_PHONE}\n")
                f.write(f"OPENAI_API_KEY={self.config.TEST_OPENAI_API_KEY}\n")
                f.write(f"DEFAULT_TEST_CUSTOMER_NUMBER={self.config.TEST_CUSTOMER_PHONE}\n")
                f.write(f"DATABASE_URL={self.config.TEST_DATABASE_URL}\n")
                f.write(f"REDIS_URL={self.config.TEST_REDIS_URL}\n")
                
            # Create virtual environment and install dependencies
            subprocess.check_call(["python", "-m", "venv", ".venv"], cwd=work_dir)
            pip_path = work_dir / ".venv" / "bin" / "pip"
            
            # Install test dependencies
            subprocess.check_call([str(pip_path), "install", "-r", "requirements.txt"], cwd=work_dir)
            subprocess.check_call([str(pip_path), "install", "pytest", "playwright"], cwd=work_dir)
            
            # Install Playwright browsers
            venv_python = work_dir / ".venv" / "bin" / "python"
            subprocess.check_call([str(venv_python), "-m", "playwright", "install", "chromium"], cwd=work_dir)
            
            return True, "Environment prepared successfully"
        except Exception as e:
            logger.error(f"Failed to prepare test environment: {e}")
            return False, f"Failed to prepare environment: {e}"
    
    def run_tests(self, specific_tests: Optional[List[str]] = None) -> Dict:
        """Run the E2E tests and return results"""
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            success, message = self.prepare_test_environment(work_dir)
            
            if not success:
                return {
                    "success": False,
                    "message": message,
                    "tests": []
                }
            
            # Prepare command to run tests
            python_path = work_dir / ".venv" / "bin" / "python"
            cmd = [str(python_path), "-m", "pytest", "tests/e2e", "-v", "--junitxml=results.xml"]
            
            if specific_tests:
                cmd.extend(specific_tests)
                
            # Run the tests
            try:
                result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
                
                # Parse the results XML file
                import xml.etree.ElementTree as ET
                tree = ET.parse(work_dir / "results.xml")
                root = tree.getroot()
                
                tests = []
                for testcase in root.findall(".//testcase"):
                    test = {
                        "name": testcase.get("name"),
                        "classname": testcase.get("classname"),
                        "time": float(testcase.get("time")),
                        "success": True,
                        "error": None,
                        "failure": None,
                    }
                    
                    # Check for errors or failures
                    error = testcase.find("error")
                    failure = testcase.find("failure")
                    
                    if error is not None:
                        test["success"] = False
                        test["error"] = {
                            "message": error.get("message"),
                            "type": error.get("type"),
                            "text": error.text
                        }
                    
                    if failure is not None:
                        test["success"] = False
                        test["failure"] = {
                            "message": failure.get("message"),
                            "type": failure.get("type"),
                            "text": failure.text
                        }
                    
                    tests.append(test)
                
                # Calculate overall success rate
                total_tests = len(tests)
                successful_tests = sum(1 for test in tests if test["success"])
                
                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "tests": tests,
                    "summary": {
                        "total": total_tests,
                        "passed": successful_tests,
                        "failed": total_tests - successful_tests,
                        "pass_rate": successful_tests / total_tests if total_tests > 0 else 0
                    }
                }
                
            except Exception as e:
                logger.error(f"Test execution failed: {e}")
                return {
                    "success": False,
                    "message": f"Test execution failed: {e}",
                    "tests": []
                }
```

## Step 5: Using the Docker-based MCP Server

The Docker-based MCP server provides a comprehensive testing environment that mirrors the Render staging environment. This allows you to test your code with real databases and services.

### Setting Up the Docker MCP Server

```bash
# Run the Docker setup script
./mcp/setup_docker_mcp.sh
```

This will:
1. Create a Python virtual environment for the MCP server
2. Install the required packages
3. Make the MCP server executable
4. Register the MCP server with Claude

### Running the Docker MCP Server

```bash
# Start the Docker MCP server
./mcp/run_docker_mcp.sh
```

### Testing with the Docker MCP Server

Once the server is running, you can use it from Claude with the following commands:

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

## Step 6: Using the Basic Refactor Test Server

For simpler testing needs, you can use the basic refactor test server:

### Setting Up the Basic Test Server

```bash
# Run the setup script
./mcp/setup.sh
```

### Testing with the Basic Test Server

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

## Step 7: Using the Simple MCP Server

The Simple MCP Server is a standalone implementation that uses JSON-RPC 2.0 protocol directly without SDK dependencies. It provides comprehensive testing capabilities using real Docker containers for PostgreSQL and Redis.

### Setting Up the Simple MCP Server

```bash
# Run the Simple MCP startup script
./start_redbarsushi_mcp.sh
```

This script will:
1. Update the Claude configuration to use the server
2. Kill any existing MCP server processes
3. Start the server in the background
4. Register it with Claude as "redbarsushi-test"

### Testing with the Simple MCP Server

After starting the server, you can use Claude with these commands:

```
# Check if the server is connected
/mcp

# Check Docker environment status
/mcp check_docker_status

# Set up Docker environment
/mcp setup_docker_env project_path="/home/proxyie/MySoftware/RedBarSushiAI"

# Run basic connectivity tests
/mcp run_test test_type="basic"

# Run database schema and operations tests
/mcp run_test test_type="database"

# Run Redis cache operations tests
/mcp run_test test_type="redis"

# Run menu system tests
/mcp run_test test_type="menu"

# Run order system tests
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

## Conclusion

This MCP server setup will enable comprehensive testing of the RedBarSushiAI application in an environment that closely resembles the Render staging environment. By leveraging Docker, you can test your code with real databases and services, ensuring that it will work correctly when deployed.