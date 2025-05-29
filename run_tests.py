#!/usr/bin/env python3
"""
Smart test runner that adapts to environment and runs appropriate tests.
Provides fast feedback for development and comprehensive testing for staging.
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path


class TestRunner:
    """Intelligent test runner."""
    
    def __init__(self):
        self.environment = os.getenv("FASTAPI_ENV", "development")
        self.project_root = Path(__file__).parent
        
    def setup_environment(self, env_type="mock"):
        """Setup test environment."""
        print(f"🔧 Setting up {env_type} test environment...")
        
        if env_type == "mock":
            # For local development testing
            os.environ["TESTING"] = "true"
            
            # Start mock services
            subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml",
                "up", "-d", "postgres-test", "redis-test"
            ])
            
            # Start mock server if needed
            if os.getenv("USE_MOCK_SERVICES", "true").lower() == "true":
                subprocess.run([
                    "docker-compose", "-f", "docker-compose.test.yml",
                    "up", "-d", "mock-server"
                ])
            
            # Wait for services to be ready
            print("⏳ Waiting for services to start...")
            time.sleep(5)
            
        elif env_type == "staging":
            # For Render staging environment
            # Environment variables are already set by Render
            print("📍 Using Render staging environment")
            
            # Verify we're in staging
            if os.getenv("FASTAPI_ENV") != "staging":
                print("⚠️  Warning: FASTAPI_ENV is not set to 'staging'")
                print("   Ensure you're running this on Render staging environment")
            
            # Ensure required credentials are set
            required_vars = [
                "DATABASE_URL",
                "REDIS_URL", 
                "OPENAI_API_KEY",
                "TWILIO_ACCOUNT_SID",
                "DELIVERECT_API_KEY"
            ]
            
            missing = [var for var in required_vars if not os.getenv(var)]
            if missing:
                print(f"❌ Missing environment variables: {missing}")
                print("   These should be set in your Render dashboard")
                sys.exit(1)
    
    def run_unit_tests(self, specific_file=None):
        """Run unit tests."""
        print("🧪 Running unit tests...")
        
        cmd = ["pytest", "tests/unit", "-v", "--tb=short"]
        if specific_file:
            cmd = ["pytest", f"tests/unit/{specific_file}", "-v"]
        
        return subprocess.run(cmd).returncode
    
    def run_integration_tests(self, specific_file=None):
        """Run integration tests."""
        print("🔗 Running integration tests...")
        
        cmd = ["pytest", "tests/integration", "-v"]
        if specific_file:
            cmd = ["pytest", f"tests/integration/{specific_file}", "-v"]
        
        return subprocess.run(cmd).returncode
    
    def run_e2e_tests(self, specific_file=None):
        """Run E2E tests."""
        print("🌐 Running E2E tests...")
        
        cmd = ["pytest", "tests/e2e", "-v", "-s"]
        if specific_file:
            cmd = ["pytest", f"tests/e2e/{specific_file}", "-v", "-s"]
        
        return subprocess.run(cmd).returncode
    
    def run_fast_tests(self):
        """Run only fast tests for quick feedback."""
        print("⚡ Running fast tests only...")
        
        cmd = [
            "pytest", "-m", "not slow", 
            "--tb=short", "-v",
            "-x"  # Stop on first failure
        ]
        
        return subprocess.run(cmd).returncode
    
    def run_with_coverage(self):
        """Run tests with coverage report."""
        print("📊 Running tests with coverage...")
        
        cmd = [
            "pytest",
            "tests/unit", "tests/integration",
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ]
        
        result = subprocess.run(cmd).returncode
        
        if result == 0:
            print("✅ Coverage report generated in htmlcov/")
            print("📱 Open htmlcov/index.html to view detailed coverage")
        
        return result
    
    def run_parallel(self, num_workers=None):
        """Run tests in parallel."""
        print(f"🚀 Running tests in parallel...")
        
        if num_workers is None:
            num_workers = "auto"
        
        cmd = [
            "pytest", "-n", str(num_workers),
            "--dist", "loadscope",
            "-v"
        ]
        
        return subprocess.run(cmd).returncode
    
    def watch_tests(self, path=None):
        """Watch for changes and run tests automatically."""
        print("👀 Watching for changes...")
        
        try:
            import pytest_watch
        except ImportError:
            print("❌ pytest-watch not installed. Run: pip install pytest-watch")
            return 1
        
        cmd = ["ptw"]
        if path:
            cmd.extend(["--", path])
        
        return subprocess.run(cmd).returncode
    
    def cleanup(self):
        """Cleanup test environment."""
        print("🧹 Cleaning up test environment...")
        
        subprocess.run([
            "docker-compose", "-f", "docker-compose.test.yml",
            "down", "-v"
        ])


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Smart test runner for RedBarSushiAI")
    
    parser.add_argument(
        "command",
        choices=["unit", "integration", "e2e", "all", "fast", "coverage", "parallel", "watch", "staging"],
        help="Test command to run"
    )
    
    parser.add_argument(
        "--file", "-f",
        help="Specific test file to run"
    )
    
    parser.add_argument(
        "--env", "-e",
        choices=["mock", "staging"],
        default="mock",
        help="Test environment (default: mock)"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        help="Number of parallel workers"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't cleanup after tests"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    try:
        # Setup environment
        runner.setup_environment(args.env)
        
        # Run appropriate tests
        if args.command == "unit":
            result = runner.run_unit_tests(args.file)
        elif args.command == "integration":
            result = runner.run_integration_tests(args.file)
        elif args.command == "e2e":
            result = runner.run_e2e_tests(args.file)
        elif args.command == "all":
            result = runner.run_unit_tests()
            if result == 0:
                result = runner.run_integration_tests()
            if result == 0:
                result = runner.run_e2e_tests()
        elif args.command == "fast":
            result = runner.run_fast_tests()
        elif args.command == "coverage":
            result = runner.run_with_coverage()
        elif args.command == "parallel":
            result = runner.run_parallel(args.workers)
        elif args.command == "watch":
            result = runner.watch_tests(args.file)
        elif args.command == "staging":
            runner.setup_environment("staging")
            result = runner.run_e2e_tests()
        
        if result == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
        
        return result
        
    finally:
        if not args.no_cleanup:
            runner.cleanup()


if __name__ == "__main__":
    sys.exit(main())