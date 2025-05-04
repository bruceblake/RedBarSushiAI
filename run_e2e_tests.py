#!/usr/bin/env python
"""
This script runs end-to-end tests against the staging environment.
It handles setting up the necessary environment variables and retries.
"""
import os
import sys
import subprocess
import argparse
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("e2e_tests")

# Staging environment URL
STAGING_URL = "https://redbarsushiai-staging.onrender.com"

# Test categories and their corresponding test files
TEST_CATEGORIES = {
    "health": ["tests/e2e/test_health_check.py"],
    "voice_basic": ["tests/e2e/test_voice_endpoints.py"],
    "voice_flow": ["tests/e2e/test_voice_flow.py", "tests/e2e/test_voice_menu_handling.py"],
    "order_api": ["tests/e2e/test_api_requests.py"],
    "orders": ["tests/e2e/test_basic_order.py", "tests/e2e/test_complete_order_flow.py"], 
    "all": ["tests/e2e/"]
}

def run_test(category, max_retries=2, verbose=True):
    """Run a specific test category with retries."""
    if category not in TEST_CATEGORIES:
        logger.error(f"Unknown test category: {category}")
        return False
    
    test_files = TEST_CATEGORIES[category]
    test_paths = " ".join(test_files)
    
    # Set environment variables
    env = os.environ.copy()
    env["BASE_URL"] = STAGING_URL
    env["TEST_MODE"] = "staging"
    env["SKIP_DB_SETUP"] = "true"
    
    # Build the pytest command
    verbose_flag = "-v" if verbose else ""
    cmd = f"python -m pytest {test_paths} {verbose_flag}"
    
    logger.info(f"Running tests for category: {category}")
    logger.info(f"Command: {cmd}")
    
    # Run the tests with retries
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries + 1}")
            process = subprocess.run(
                cmd, 
                shell=True, 
                check=False, 
                env=env,
                capture_output=True,
                text=True
            )
            
            # Print the output
            if process.stdout:
                print(process.stdout)
            if process.stderr:
                print(process.stderr, file=sys.stderr)
            
            if process.returncode == 0:
                logger.info(f"Tests for {category} passed!")
                return True
            else:
                logger.warning(f"Tests for {category} failed with exit code {process.returncode}")
                if attempt < max_retries:
                    logger.info(f"Retrying in 5 seconds...")
                    time.sleep(5)
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in 5 seconds...")
                time.sleep(5)
    
    logger.error(f"All attempts failed for category: {category}")
    return False

def run_all_tests():
    """Run all test categories in a specific order."""
    results = {}
    
    # Run tests in a specific order, starting with the simplest
    test_order = ["health", "voice_basic", "voice_flow", "order_api", "orders"]
    
    for category in test_order:
        success = run_test(category)
        results[category] = success
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for category, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{category:15}: {status}")
        if not success:
            all_passed = False
    
    print("\n")
    if all_passed:
        print("All tests passed successfully!")
        return 0
    else:
        print("Some tests failed. Check the logs for details.")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run E2E tests against the staging environment")
    parser.add_argument("--category", "-c", help="Test category to run", default="all")
    args = parser.parse_args()
    
    if args.category == "all":
        sys.exit(run_all_tests())
    else:
        success = run_test(args.category)
        sys.exit(0 if success else 1)