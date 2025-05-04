"""
Database test fixtures for E2E tests.
"""
import os
import pytest
import json
import sys

# Add proper path to import app modules if needed
try:
    import app
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Check if we're running against a remote staging/production environment
TESTING_MODE = os.getenv("TEST_MODE", "local")
STAGING_TESTING = TESTING_MODE in ("staging", "production")
SKIP_DB_SETUP = os.getenv("SKIP_DB_SETUP", "false").lower() == "true"

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Fixture to set up a test database for E2E tests.
    
    When running against a remote environment (staging/production), this
    fixture does nothing as we don't want to modify the remote database.
    """
    if STAGING_TESTING or SKIP_DB_SETUP:
        # Skip database setup for remote testing
        yield
        return

    # For local testing, we'd normally set up a test database here
    # This is a no-op for remote testing
    print("Setting up test database for local testing")
    
    # We'd normally create tables, load test data, etc.
    # For now, just yield to continue with tests
    yield
    
    # We'd normally tear down the database here
    print("Tearing down test database")

@pytest.fixture(scope="session")
def use_database_for_menu():
    """
    Configure the application to use the database for menu storage.
    """
    # No actual configuration needed for remote testing
    os.environ["MENU_BACKEND"] = "database"
    
    yield

    # Reset environment if needed
    # This is generally not necessary for test cases, but included for completeness