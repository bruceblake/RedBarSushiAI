# tests/e2e/conftest.py - Minimal version for endpoint testing
import os
import sys
import pytest

# Add the project root to the path if needed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up BASE_URL for all tests
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
print(f"Using BASE_URL: {BASE_URL}")

# Minimal fixture for app config
@pytest.fixture(scope="function")
def app():
    """Provide a dummy app object for testing against the staging environment."""
    class DummyApp:
        def __init__(self):
            self.config = {
                "TESTING": True,
                "MENU_BACKEND": "database"
            }
    return DummyApp()
