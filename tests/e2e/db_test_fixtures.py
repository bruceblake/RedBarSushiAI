"""
Database fixtures for E2E tests.
This module provides fixtures to ensure the e2e tests use the database for menu operations.
"""

import pytest
import os
import sys
import json
from contextlib import contextmanager

# The project root path should already be in sys.path from the root conftest.py
# Add a check to make sure we can import app modules
try:
    import app
except ImportError:
    # If app can't be imported, add the project root to the path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Now import the app modules
from app.utils.menu_migration import migrate_menu_to_database
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup


@pytest.fixture(scope="function")
def _app():
    """
    Create and configure a Flask app for testing.
    This is a placeholder - the real fixture is defined in conftest.py
    """
    # Import here to avoid circular imports
    try:
        from app import create_app
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        from app import create_app
    
    test_app = create_app(testing=True)
    test_app.config['TESTING'] = True
    
    yield test_app

@pytest.fixture(scope="function", autouse=True)
def setup_test_database(app):
    """
    Set up the test database with menu data for E2E tests.
    This ensures that E2E tests use the database instead of JSON files.
    """
    with app.app_context():
        # Create all tables
        from app import db
        db.create_all()
        
        # Store the original menu data for later restoration
        try:
            menu_file_path = os.environ.get("MENU_FILE_PATH", os.path.join(os.getcwd(), "menu_data.json"))
            if os.path.exists(menu_file_path):
                with open(menu_file_path, "r") as f:
                    original_menu_data = json.load(f)
            else:
                original_menu_data = {"items": [], "modifiers": [], "modifierGroups": []}
        except Exception:
            original_menu_data = {"items": [], "modifiers": [], "modifierGroups": []}
        
        # Migrate the menu data to the database
        migrate_menu_to_database(file_path=menu_file_path, force=True)
        
        # Force the app config to use the database
        if "MENU_BACKEND" not in app.config:
            app.config["MENU_BACKEND"] = "database"
        
        yield
        
        # Clean up database after test
        db.session.query(MenuModifierGroup).delete()
        db.session.query(MenuModifier).delete()
        db.session.query(MenuItem).delete()
        db.session.commit()
        
        # Restore the original menu data to the file
        with open(menu_file_path, "w") as f:
            json.dump(original_menu_data, f, indent=2)


@contextmanager
def use_database_for_menu():
    """
    Context manager to force the application to use the database for menu operations.
    This is useful for tests that need to verify database operations.
    """
    from flask import current_app
    
    # Store original settings
    original_menu_backend = current_app.config.get("MENU_BACKEND")
    
    try:
        # Force database usage
        current_app.config["MENU_BACKEND"] = "database"
        yield
    finally:
        # Restore original settings
        if original_menu_backend is not None:
            current_app.config["MENU_BACKEND"] = original_menu_backend
        else:
            current_app.config.pop("MENU_BACKEND", None)


# Register the fixtures for pytest
def pytest_configure(config):
    """Register markers with pytest."""
    config.addinivalue_line("markers", "use_db_menu: mark a test to use the database for menu operations")


def pytest_runtest_setup(item):
    """Setup hook to check for markers."""
    for marker in item.iter_markers(name="use_db_menu"):
        # This will be processed by setup_test_database fixture
        pass