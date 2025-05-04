# Setting Up MCP Server for RedBarSushiAI E2E Testing

This document outlines the steps for setting up a Mission Control Platform (MCP) server to run end-to-end tests on the RedBarSushiAI staging environment and implement automatic fixing of detected issues.

## Overview

The MCP server will:
1. Connect to the Render staging environment
2. Run E2E tests to verify system functionality
3. Report test results and failures
4. Attempt to fix issues automatically when tests fail

## Prerequisites

- Access to Render dashboard for RedBarSushiAI staging environment
- GitHub repository access for code changes
- API access tokens for necessary services
- A server/VM to host the MCP orchestrator

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

## Step 5: Result Analyzer and Fix Generator

The result analyzer will identify patterns in test failures. The fix generator will create patches for common issues:

```python
class ResultAnalyzer:
    def __init__(self, config):
        self.config = config
        
    def analyze_test_results(self, results):
        """Analyze test results and identify common issues"""
        issues = []
        
        for test in results.get("tests", []):
            if not test["success"]:
                issue = self._identify_issue(test)
                if issue:
                    issues.append(issue)
        
        return issues
    
    def _identify_issue(self, test):
        """Identify the issue based on test failure"""
        error_text = ""
        if test.get("error"):
            error_text = test["error"].get("text", "")
        elif test.get("failure"):
            error_text = test["failure"].get("text", "")
        
        # Check for common patterns
        if "ConnectionError" in error_text or "Connection refused" in error_text:
            return {
                "type": "connection_error",
                "test": test["name"],
                "description": "API connection error - possible service outage",
                "severity": "high"
            }
        elif "Timeout" in error_text:
            return {
                "type": "timeout",
                "test": test["name"],
                "description": "API response timeout - possible performance issue",
                "severity": "medium"
            }
        elif "AssertionError" in error_text:
            # Extract assertion details
            return {
                "type": "assertion_error",
                "test": test["name"],
                "description": "Test assertion failed - data validation issue",
                "severity": "medium"
            }
        
        return {
            "type": "unknown",
            "test": test["name"],
            "description": "Unknown error",
            "severity": "low"
        }


class FixGenerator:
    def __init__(self, config):
        self.config = config
        
    def generate_fix(self, issue):
        """Generate a fix for the identified issue"""
        if issue["type"] == "connection_error":
            return self._fix_connection_error(issue)
        elif issue["type"] == "timeout":
            return self._fix_timeout(issue)
        elif issue["type"] == "assertion_error":
            return self._fix_assertion_error(issue)
        
        return None
    
    def _fix_connection_error(self, issue):
        """Generate a fix for connection errors"""
        # Check Render service status
        # Restart service if needed
        # Return fix details
        pass
    
    def _fix_timeout(self, issue):
        """Generate a fix for timeout issues"""
        # Could involve scaling up resources on Render
        pass
    
    def _fix_assertion_error(self, issue):
        """Generate a fix for assertion errors"""
        # More complex - requires analysis of the exact assertion
        pass
```

## Step 6: MCP CLI Tool

Create a CLI tool for manual execution of tests and fixes:

```python
import click
import logging
from mcp.config import Config
from mcp.test_runner import TestRunner
from mcp.result_analyzer import ResultAnalyzer
from mcp.fix_generator import FixGenerator

@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug logging')
def cli(debug):
    """RedBarSushiAI MCP Tool"""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level)
    

@cli.command()
@click.option('--test', '-t', multiple=True, help='Specific test to run')
def run_tests(test):
    """Run E2E tests on the staging environment"""
    config = Config()
    runner = TestRunner(config)
    
    click.echo("Running tests...")
    results = runner.run_tests(specific_tests=list(test) if test else None)
    
    # Display results summary
    click.echo(f"\nTest Results:")
    click.echo(f"  Total: {results['summary']['total']}")
    click.echo(f"  Passed: {results['summary']['passed']}")
    click.echo(f"  Failed: {results['summary']['failed']}")
    click.echo(f"  Pass Rate: {results['summary']['pass_rate'] * 100:.2f}%")
    
    # Show details for failed tests
    if results['summary']['failed'] > 0:
        click.echo("\nFailed Tests:")
        for test in results['tests']:
            if not test['success']:
                click.echo(f"  - {test['name']} ({test['classname']})")
                if test.get('error'):
                    click.echo(f"    Error: {test['error']['message']}")
                if test.get('failure'):
                    click.echo(f"    Failure: {test['failure']['message']}")


@cli.command()
@click.option('--test', '-t', multiple=True, help='Specific test to run')
@click.option('--auto-fix/--no-auto-fix', default=False, help='Attempt to auto-fix issues')
def analyze(test, auto_fix):
    """Run tests, analyze results, and optionally fix issues"""
    config = Config()
    runner = TestRunner(config)
    analyzer = ResultAnalyzer(config)
    
    click.echo("Running tests...")
    results = runner.run_tests(specific_tests=list(test) if test else None)
    
    click.echo("\nAnalyzing results...")
    issues = analyzer.analyze_test_results(results)
    
    click.echo(f"\nIdentified {len(issues)} issues:")
    for i, issue in enumerate(issues):
        click.echo(f"{i+1}. {issue['type']} - {issue['description']} (Severity: {issue['severity']})")
        click.echo(f"   Test: {issue['test']}")
    
    if auto_fix and issues:
        click.echo("\nAttempting to fix issues...")
        fix_generator = FixGenerator(config)
        for issue in issues:
            fix = fix_generator.generate_fix(issue)
            if fix:
                click.echo(f"Applied fix for issue: {issue['type']}")
            else:
                click.echo(f"No automatic fix available for issue: {issue['type']}")


if __name__ == '__main__':
    cli()
```

## Step 7: GitHub Integration for Fixes

For automated fix generation and PR creation, implement a GitHub client:

```python
from github import Github
import os
import tempfile
import subprocess
from pathlib import Path

class GitHubClient:
    def __init__(self, config):
        self.config = config
        self.token = config.GITHUB_TOKEN
        self.repo_name = config.GITHUB_REPO
        self.base_branch = config.GITHUB_BASE_BRANCH
        self.g = Github(self.token)
        self.repo = self.g.get_repo(self.repo_name)
        
    def create_pull_request(self, fixes, title, description):
        """Create a pull request with the generated fixes"""
        # Create a unique branch name
        branch_name = f"mcp-fixes-{int(time.time())}"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            
            # Clone the repository
            subprocess.check_call([
                "git", "clone", 
                f"https://{self.token}@github.com/{self.repo_name}.git",
                str(work_dir)
            ])
            
            # Create a new branch
            subprocess.check_call(["git", "checkout", "-b", branch_name], cwd=work_dir)
            
            # Apply fixes
            for fix in fixes:
                file_path = work_dir / fix["file_path"]
                with open(file_path, "w") as f:
                    f.write(fix["content"])
                
                # Stage the file
                subprocess.check_call(["git", "add", fix["file_path"]], cwd=work_dir)
            
            # Commit the changes
            subprocess.check_call([
                "git", "commit", "-m", f"Auto-fix: {title}"
            ], cwd=work_dir)
            
            # Push the branch
            subprocess.check_call([
                "git", "push", "origin", branch_name
            ], cwd=work_dir)
            
            # Create the pull request
            pr = self.repo.create_pull(
                title=title,
                body=description,
                head=branch_name,
                base=self.base_branch
            )
            
            return {
                "success": True,
                "pr_number": pr.number,
                "pr_url": pr.html_url
            }
```

## Step 8: Running as a Service

### Create a systemd service file for automatic startup:

```ini
[Unit]
Description=RedBarSushiAI MCP Service
After=network.target postgresql.service redis-server.service

[Service]
User=mcp
Group=mcp
WorkingDirectory=/opt/redbarsushi-mcp
ExecStart=/opt/redbarsushi-mcp/.venv/bin/python -m mcp.app
Restart=on-failure
Environment=MCP_ENV=production

[Install]
WantedBy=multi-user.target
```

### Setup as Docker Compose

```yaml
version: '3'

services:
  mcp-service:
    build: .
    container_name: redbarsushi-mcp
    volumes:
      - ./data:/app/data
    ports:
      - "8080:8080"
    environment:
      - MCP_ENV=production
    env_file:
      - .env
    restart: unless-stopped
    depends_on:
      - mcp-db
      - mcp-redis
      
  mcp-db:
    image: postgres:14-alpine
    container_name: redbarsushi-mcp-db
    environment:
      - POSTGRES_USER=mcp
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=mcp_testing
    volumes:
      - mcp-db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    
  mcp-redis:
    image: redis:alpine
    container_name: redbarsushi-mcp-redis
    volumes:
      - mcp-redis-data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  mcp-db-data:
  mcp-redis-data:
```

## Step 9: Scheduling and Monitoring

### Configure automatic test runs:

```python
import schedule
import time
import logging
from mcp.test_runner import TestRunner
from mcp.result_analyzer import ResultAnalyzer
from mcp.fix_generator import FixGenerator
from mcp.github_client import GitHubClient
from mcp.slack_client import SlackClient
from mcp.config import Config

logger = logging.getLogger(__name__)

def run_test_job():
    """Run tests, analyze results, and fix issues if necessary"""
    logger.info("Starting scheduled test run")
    
    config = Config()
    runner = TestRunner(config)
    analyzer = ResultAnalyzer(config)
    fix_generator = FixGenerator(config)
    github_client = GitHubClient(config)
    slack_client = SlackClient(config)
    
    # Run the tests
    results = runner.run_tests()
    logger.info(f"Tests completed with {results['summary']['failed']} failures")
    
    # Send notification of test results
    slack_client.send_message(f"RedBarSushiAI E2E Tests: {results['summary']['passed']}/{results['summary']['total']} tests passed")
    
    # If tests failed, analyze and fix
    if results['summary']['failed'] > 0:
        issues = analyzer.analyze_test_results(results)
        logger.info(f"Identified {len(issues)} issues")
        
        # Generate fixes
        fixes = []
        for issue in issues:
            fix = fix_generator.generate_fix(issue)
            if fix:
                fixes.append(fix)
        
        # If fixes were generated, create a PR
        if fixes:
            logger.info(f"Creating PR with {len(fixes)} fixes")
            pr_result = github_client.create_pull_request(
                fixes=fixes,
                title=f"Auto-fix: Fix {len(fixes)} E2E test issues",
                description=f"Automatically generated fixes for E2E test failures.\n\nIssues fixed:\n" + 
                            "\n".join([f"- {issue['type']}: {issue['description']}" for issue in issues])
            )
            
            # Notify about PR
            if pr_result["success"]:
                slack_client.send_message(f"Created PR #{pr_result['pr_number']} with automatic fixes: {pr_result['pr_url']}")
            else:
                slack_client.send_message(f"Failed to create PR for automatic fixes")
        else:
            slack_client.send_message(f"No automatic fixes available for the {len(issues)} identified issues")
    
# Setup schedule - run tests every 3 hours
schedule.every(3).hours.do(run_test_job)

# Also run at specific times
schedule.every().day.at("06:00").do(run_test_job)
schedule.every().day.at("18:00").do(run_test_job)

def start_scheduler():
    """Start the scheduler loop"""
    logger.info("Starting scheduler")
    
    # Run once at startup
    run_test_job()
    
    # Then follow the schedule
    while True:
        schedule.run_pending()
        time.sleep(60)
```

## Step 10: Usage Instructions

### Running the MCP Service

```bash
# Clone the repository
git clone https://github.com/yourusername/redbarsushi-mcp.git
cd redbarsushi-mcp

# Copy and edit the environment file
cp .env.example .env
nano .env  # Edit with your specific configuration

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Manual Test Execution

```bash
# Using the CLI tool
python -m mcp.cli run-tests

# Run specific tests
python -m mcp.cli run-tests --test test_complete_order_flow.py::test_complete_order_workflow

# Run tests with analysis
python -m mcp.cli analyze

# Run tests with auto-fix
python -m mcp.cli analyze --auto-fix
```

## Conclusion

This MCP server setup will enable continuous testing of the RedBarSushiAI staging environment. By automatically identifying and fixing common issues, it reduces the manual maintenance burden and helps ensure the system remains stable and functional.

The approach is modular, allowing for easy extension with additional test types or fix strategies as the system evolves.