#!/usr/bin/env python
"""
MCP Test Configuration for RedBarSushiAI

This module defines the configuration for running tests against the staging environment.
"""

import os

# Base URL for the staging environment
STAGING_URL = "https://redbarsushiai-staging.onrender.com"

# Test environment configuration
ENV_VARS = {
    "BASE_URL": STAGING_URL,
    "TEST_MODE": "staging",
    "SKIP_DB_SETUP": "true",  # Skip local database setup when testing against staging
}

# Twilio test configuration
TWILIO_TEST_CONFIG = {
    "from_number": "+15551234567",
    "to_number": "+15557654321",
    "account_sid": "AC12345678901234567890123456789012",
}

# Test categories
TEST_CATEGORIES = {
    "health": ["tests/e2e/test_health_check.py"],
    "voice_basic": ["tests/e2e/test_voice_endpoints.py"],
    "voice_flow": ["tests/e2e/test_voice_flow.py", "tests/e2e/test_voice_menu_handling.py"],
    "orders": ["tests/e2e/test_basic_order.py"],
    "complete_order_e2e": ["tests/e2e/test_complete_order_flow_e2e.py"],
    "deliverect": ["tests/integration/test_deliverect_api_integration.py"],
    "menu_sync": ["tests/integration/test_deliverect_menu_synchronization.py"],
    "mcp_integration": ["tests/integration/test_mcp_test_integration.py"],
    "all_integration": ["tests/integration/"],
    "all_e2e": ["tests/e2e/"],
    "all": ["tests/e2e/", "tests/integration/"]
}

def get_test_command(test_category="health", extra_args=""):
    """Generate a pytest command for the specified test category."""
    if test_category not in TEST_CATEGORIES:
        raise ValueError(f"Unknown test category: {test_category}")
    
    # Build environment variables string
    env_vars = " ".join([f"{k}={v}" for k, v in ENV_VARS.items()])
    
    # Build test paths string
    test_paths = " ".join(TEST_CATEGORIES[test_category])
    
    # Construct the full command
    command = f"{env_vars} python -m pytest {test_paths} {extra_args}"
    
    return command

def run_test(test_category="health", verbose=True, junit_report=False):
    """Run the specified test category."""
    extra_args = "-v" if verbose else ""
    if junit_report:
        extra_args += f" --junitxml=test-results/{test_category}.xml"
    
    command = get_test_command(test_category, extra_args)
    return os.system(command)

if __name__ == "__main__":
    # If run directly, run the health check tests
    run_test("health")