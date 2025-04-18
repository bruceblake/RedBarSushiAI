"""
Test the menu update endpoint with various input formats
"""

import json
import sys
import pytest
from pathlib import Path
from flask import Flask
from unittest.mock import patch

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent))

from app.routes.menu import menu_bp


# Create a test Flask app
@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(menu_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_menu_update_list_format(client):
    """Test the menu update endpoint with list format data."""
    # Create test data in the format that was failing
    test_data = [
        {
            "categories": [
                {
                    "id": "cat1",
                    "name": "Sushi",
                    "products": [
                        {
                            "id": "p1",
                            "name": "California Roll",
                            "price": 995,
                            "plu": "CAL-ROLL",
                            "description": "Crab, avocado and cucumber",
                            "available": True,
                        }
                    ],
                }
            ]
        }
    ]

    # Mock write_menu_file to avoid actual file writes during test
    with patch("app.routes.menu.write_menu_file") as mock_write, patch(
        "app.routes.menu.load_menu_data"
    ) as mock_load:

        # Configure mocks
        mock_write.return_value = True
        mock_load.return_value = {
            "items": [
                {
                    "name": "California Roll",
                    "price": 9.95,
                    "reference_handler": "CAL-ROLL",
                    "available": True,
                }
            ],
            "modifiers": [],
            "modifierGroups": [],
            "name_variants": {"california roll": "California Roll"},
        }

        # Send request to menu_update endpoint
        response = client.post(
            "/menu_update", data=json.dumps(test_data), content_type="application/json"
        )

        # Check response
        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["items"] == 2  # Category + item

        # Verify the correct calls were made - our enhanced implementation makes multiple calls
        assert (
            mock_write.call_count >= 1
        ), "write_menu_file should be called at least once"
        assert (
            mock_load.call_count >= 1
        ), "load_menu_data should be called at least once"
        # Verify that load_menu_data was called with force_refresh=True at least once
        mock_load.assert_any_call(force_refresh=True)


def test_menu_update_nested_format(client):
    """Test the menu update endpoint with nested menu format."""
    # Create test data with nested menu structure
    test_data = [
        {
            "menu": {
                "menuId": "menu123",
                "name": "Main Menu",
                "categories": [
                    {
                        "id": "cat1",
                        "name": "Burgers",
                        "products": [
                            {
                                "id": "p1",
                                "name": "Cheeseburger",
                                "price": 1295,
                                "plu": "CHEESE-BURG",
                                "description": "Beef patty with cheese",
                                "available": True,
                            }
                        ],
                    }
                ],
            }
        }
    ]

    # Mock write_menu_file to avoid actual file writes during test
    with patch("app.routes.menu.write_menu_file") as mock_write, patch(
        "app.routes.menu.load_menu_data"
    ) as mock_load:

        # Configure mocks
        mock_write.return_value = True
        mock_load.return_value = {
            "items": [
                {
                    "name": "Cheeseburger",
                    "price": 12.95,
                    "reference_handler": "CHEESE-BURG",
                    "available": True,
                }
            ],
            "modifiers": [],
            "modifierGroups": [],
            "name_variants": {"cheeseburger": "Cheeseburger"},
        }

        # Send request to menu_update endpoint
        response = client.post(
            "/menu_update", data=json.dumps(test_data), content_type="application/json"
        )

        # Check response
        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["items"] == 2  # Category + item

        # Verify the correct calls were made - our enhanced implementation makes multiple calls
        assert (
            mock_write.call_count >= 1
        ), "write_menu_file should be called at least once"
        assert (
            mock_load.call_count >= 1
        ), "load_menu_data should be called at least once"
        # Verify that load_menu_data was called with force_refresh=True at least once
        mock_load.assert_any_call(force_refresh=True)


def test_menu_update_complex_structure(client):
    """Test the menu update endpoint with complex nested structure."""
    # Create test data with deep structure
    test_data = [
        {
            "data": {
                "store": {
                    "menu": {
                        "sections": [
                            {
                                "name": "Appetizers",
                                "dishes": [
                                    {
                                        "id": "p1",
                                        "name": "Edamame",
                                        "price": 595,
                                        "plu": "EDAMAME",
                                        "description": "Steamed soybeans with sea salt",
                                        "available": True,
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        }
    ]

    # Mock write_menu_file to avoid actual file writes during test
    with patch("app.routes.menu.write_menu_file") as mock_write, patch(
        "app.routes.menu.load_menu_data"
    ) as mock_load:

        # Configure mocks
        mock_write.return_value = True
        mock_load.return_value = {
            "items": [
                {
                    "name": "Edamame",
                    "price": 5.95,
                    "reference_handler": "EDAMAME",
                    "available": True,
                }
            ],
            "modifiers": [],
            "modifierGroups": [],
            "name_variants": {"edamame": "Edamame"},
        }

        # Send request to menu_update endpoint
        response = client.post(
            "/menu_update", data=json.dumps(test_data), content_type="application/json"
        )

        # Check response
        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["items"] == 1

        # Verify the correct calls were made - our enhanced implementation makes multiple calls
        assert (
            mock_write.call_count >= 1
        ), "write_menu_file should be called at least once"
        assert (
            mock_load.call_count >= 1
        ), "load_menu_data should be called at least once"
        # Verify that load_menu_data was called with force_refresh=True at least once
        mock_load.assert_any_call(force_refresh=True)
