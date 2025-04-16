#!/usr/bin/env python
"""
Utility script to set up a testing environment for the restaurant AI agent.
This creates necessary test configurations and sample data.

Usage:
    python setup_test_env.py [--render-compatible] [--with-sample-data]
"""
import os
import sys
import json
import argparse
import shutil
from pathlib import Path
import subprocess

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def create_test_config(render_compatible=False):
    """
    Create a test configuration file that can be used for local or Render environments.
    
    Args:
        render_compatible: If True, use Render-compatible settings
    """
    config = {
        "TESTING": True,
        "FLASK_ENV": "testing",
        "LOG_LEVEL": "DEBUG",
        "OPENAI_API_KEY": "test_api_key_here",  # Replace with actual key for integration testing
        "DELIVERECT_CLIENT_ID": "test_client_id",
        "DELIVERECT_CLIENT_SECRET": "test_client_secret",
        "TWILIO_ACCOUNT_SID": "test_account_sid",
        "TWILIO_AUTH_TOKEN": "test_auth_token",
        "TWILIO_PHONE_NUMBER": "+15555555555",
    }
    
    # Add Render-specific config if needed
    if render_compatible:
        render_config = {
            "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/test_redbar",
            "REDIS_URL": "redis://localhost:6379/1"
        }
        config.update(render_config)
    else:
        # Local testing config
        config.update({
            "SQLALCHEMY_DATABASE_URI": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/1"
        })
    
    # Write the config file
    config_path = os.path.join(project_root, "test_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"Created test configuration at {config_path}")
    return config_path

def create_sample_data():
    """Create sample data files for testing."""
    # Create sample menu data
    menu_data = {
        "items": [
            {
                "name": "California Roll",
                "price": 7.95,
                "reference_handler": "cal-roll-1",
                "available": True,
                "category": "Rolls",
                "description": "Crab, avocado, and cucumber"
            },
            {
                "name": "Spicy Tuna Roll",
                "price": 8.95,
                "reference_handler": "spicy-tuna-1",
                "available": True,
                "category": "Rolls",
                "description": "Fresh tuna with spicy mayo"
            },
            {
                "name": "Edamame",
                "price": 5.95,
                "reference_handler": "edamame-1",
                "available": True,
                "category": "Appetizers",
                "description": "Steamed soybeans with sea salt"
            },
            {
                "name": "Salmon Nigiri",
                "price": 6.95,
                "reference_handler": "salmon-nigiri-1",
                "available": False,
                "category": "Nigiri",
                "description": "Fresh salmon over rice"
            }
        ],
        "modifiers": [
            {
                "name": "Extra Wasabi",
                "price": 0.50,
                "reference_handler": "mod-wasabi-1"
            },
            {
                "name": "Extra Ginger",
                "price": 0.50,
                "reference_handler": "mod-ginger-1"
            }
        ],
        "modifierGroups": [
            {
                "name": "Additions",
                "modifiers": ["mod-wasabi-1", "mod-ginger-1"]
            }
        ],
        "name_variants": {
            "california roll": "California Roll",
            "cali roll": "California Roll",
            "california": "California Roll",
            "spicy tuna": "Spicy Tuna Roll",
            "spicy tuna roll": "Spicy Tuna Roll",
            "edamame": "Edamame",
            "salmon": "Salmon Nigiri",
            "salmon nigiri": "Salmon Nigiri"
        }
    }
    
    # Write sample menu data
    menu_path = os.path.join(project_root, "test_menu_data.json")
    with open(menu_path, "w") as f:
        json.dump(menu_data, f, indent=4)
    print(f"Created sample menu data at {menu_path}")
    
    # Create test database directory if needed
    os.makedirs(os.path.join(project_root, "tests", "data"), exist_ok=True)
    
    return {"menu_path": menu_path}

def setup_postgresql_test_db():
    """Set up a PostgreSQL test database if needed."""
    try:
        subprocess.run(
            ["psql", "-c", "CREATE DATABASE test_redbar;"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print("Created PostgreSQL test database 'test_redbar'")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Failed to create PostgreSQL test database. Make sure PostgreSQL is installed and running.")
        return False

def main():
    """Main function to set up the test environment."""
    parser = argparse.ArgumentParser(description="Set up a testing environment for the restaurant AI agent")
    parser.add_argument("--render-compatible", action="store_true", help="Create a Render-compatible configuration")
    parser.add_argument("--with-sample-data", action="store_true", help="Create sample data files")
    parser.add_argument("--setup-postgres", action="store_true", help="Set up a PostgreSQL test database")
    
    args = parser.parse_args()
    
    # Create test configuration
    config_path = create_test_config(render_compatible=args.render_compatible)
    
    # Create sample data if requested
    if args.with_sample_data:
        data_paths = create_sample_data()
        # Copy sample menu to the correct location
        shutil.copy(data_paths["menu_path"], os.path.join(project_root, "tests", "test_menu_data.json"))
    
    # Set up PostgreSQL test database if requested
    if args.render_compatible and args.setup_postgres:
        setup_postgresql_test_db()
    
    print("\nTest environment setup complete.")
    print(f"\nTo run tests, use the following command:")
    print(f"  cd {project_root} && python -m pytest tests/")
    print("\nFor more specific tests:")
    print("  python -m pytest tests/test_ai_agent.py                   # Test AI agent functionality")
    print("  python -m pytest tests/simulation/test_customer_interaction.py  # Test customer interactions")
    print("  python -m pytest tests/load/test_concurrent_users.py      # Run load testing")

if __name__ == "__main__":
    main()