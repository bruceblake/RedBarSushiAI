import os
import pytest
import json
import tempfile
from flask import Flask
from unittest import mock


@pytest.fixture
def app():
    """
    Create and configure a Flask app for testing.
    This fixture is consumed by the flask_client fixture.
    """
    # Import here to avoid circular imports
    from run import create_app

    # Create a test configuration dictionary
    test_config = {"TESTING": True}
    app = create_app(test_config=test_config)

    # Use temporary files for testing
    with tempfile.NamedTemporaryFile(suffix=".json") as temp_menu_file:
        # Create an empty menu file
        with open(temp_menu_file.name, "w") as f:
            json.dump({"items": [], "modifiers": [], "modifierGroups": []}, f)

        app.config["MENU_FILE_PATH"] = temp_menu_file.name
        yield app


@pytest.fixture
def flask_client(app):
    """
    A test client for the app.
    """
    return app.test_client()


@pytest.fixture
def mock_deliverect():
    """
    Mocks the requests calls to Deliverect API.
    """
    with mock.patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "success"}
        yield mock_post


@pytest.fixture
def deliverect_menu_json():
    """
    Creates a sample Deliverect menu JSON structure based on the glossary.
    """
    return {
        "menu": "Test Menu",
        "menuId": "67209bfb174a0e5384d4db61",
        "channelLinkId": "66b35566dc02e27b286fca60",
        "currency": "USD",
        "menuType": 0,  # DELIVERY_AND_PICKUP
        "availabilities": [
            {"dayOfWeek": 1, "startTime": "00:00", "endTime": "23:59"},
            {"dayOfWeek": 2, "startTime": "00:00", "endTime": "23:59"},
            {"dayOfWeek": 3, "startTime": "00:00", "endTime": "23:59"},
        ],
        "categories": [
            {
                "_id": "67209bfb174a0e5384d4db4f",
                "name": "Steak & Burgers",
                "description": "Premium steaks and burgers",
                "subProducts": ["66b35629a7eb47d479f1d339", "66b35629a7eb47d479f1d340"],
                "availabilities": [],
            },
            {
                "_id": "67209bfb174a0e5384d4db50",
                "name": "Sides",
                "description": "Tasty side dishes",
                "subProducts": ["66b35629a7eb47d479f1d309", "66b35629a7eb47d479f1d30b"],
                "availabilities": [],
            },
        ],
        "products": {
            "66b35629a7eb47d479f1d339": {
                "_id": "66b35629a7eb47d479f1d339",
                "name": "Delicious Steak Frites",
                "description": "Premium steak with crispy fries",
                "price": 1500,  # $15.00 in cents
                "plu": "STK-01",
                "productType": 1,
                "subProducts": ["66b35629a7eb47d479f1d33b", "66b35629a7eb47d479f1d2fb"],
                "snoozed": False,
                "deliveryTax": 9000,  # 9.0%
                "takeawayTax": 9000,
                "eatInTax": 9000,
                "isCombo": False,
            },
            "66b35629a7eb47d479f1d340": {
                "_id": "66b35629a7eb47d479f1d340",
                "name": "Classic Cheeseburger",
                "description": "Juicy beef patty with cheese",
                "price": 1200,  # $12.00 in cents
                "plu": "BRG-01",
                "productType": 1,
                "subProducts": ["66b35629a7eb47d479f1d33b"],
                "snoozed": False,
                "deliveryTax": 9000,
                "takeawayTax": 9000,
                "eatInTax": 9000,
                "isCombo": False,
            },
            "66b35629a7eb47d479f1d309": {
                "_id": "66b35629a7eb47d479f1d309",
                "name": "White Rice",
                "description": "Steamed white rice",
                "price": 450,  # $4.50 in cents
                "plu": "RICE-01",
                "productType": 1,
                "subProducts": [],
                "snoozed": False,
                "deliveryTax": 9000,
                "takeawayTax": 9000,
                "eatInTax": 9000,
                "isCombo": False,
            },
            "66b35629a7eb47d479f1d30b": {
                "_id": "66b35629a7eb47d479f1d30b",
                "name": "French Fries",
                "description": "Crispy golden fries",
                "price": 350,  # $3.50 in cents
                "plu": "FRY-01",
                "productType": 1,
                "subProducts": [],
                "snoozed": False,
                "deliveryTax": 9000,
                "takeawayTax": 9000,
                "eatInTax": 9000,
                "isCombo": False,
            },
        },
        "modifierGroups": {
            "66b35629a7eb47d479f1d33b": {
                "_id": "66b35629a7eb47d479f1d33b",
                "name": "Cooking instructions",
                "plu": "MOD-01",
                "productType": 3,
                "min": 1,
                "max": 3,
                "multiMax": 1,
                "subProducts": [
                    "66b35629a7eb47d479f1d2fd",
                    "66b35629a7eb47d479f1d2ff",
                    "66b35629a7eb47d479f1d33d",
                ],
                "snoozed": False,
            },
            "66b35629a7eb47d479f1d2fb": {
                "_id": "66b35629a7eb47d479f1d2fb",
                "name": "Add a side",
                "plu": "MOD-02",
                "productType": 3,
                "min": 0,
                "max": 2,
                "multiMax": 1,
                "subProducts": ["66b35629a7eb47d479f1d309", "66b35629a7eb47d479f1d30b"],
                "snoozed": False,
            },
        },
        "modifiers": {
            "66b35629a7eb47d479f1d2fd": {
                "_id": "66b35629a7eb47d479f1d2fd",
                "name": "Rare",
                "price": 0,
                "plu": "COOK-01",
                "productType": 2,
                "parentId": "66b35629a7eb47d479f1d33b",
                "snoozed": False,
            },
            "66b35629a7eb47d479f1d2ff": {
                "_id": "66b35629a7eb47d479f1d2ff",
                "name": "Medium Rare",
                "price": 0,
                "plu": "COOK-02",
                "productType": 2,
                "parentId": "66b35629a7eb47d479f1d33b",
                "snoozed": False,
            },
            "66b35629a7eb47d479f1d33d": {
                "_id": "66b35629a7eb47d479f1d33d",
                "name": "Well Done",
                "price": 0,
                "plu": "COOK-03",
                "productType": 2,
                "parentId": "66b35629a7eb47d479f1d33b",
                "snoozed": False,
            },
        },
        "snoozedProducts": {},
    }


@pytest.fixture
def deliverect_async_menu_json(deliverect_menu_json):
    """
    Creates a sample Deliverect async menu structure.
    """
    return {
        "body": {
            "menus": [deliverect_menu_json],
            "stores": ["66b35566dc02e27b286fca60"],
            "callback": "https://api.staging.deliverect.com/testchannel/menuStatus/test123",
        }
    }


@pytest.fixture
def deliverect_snooze_payload():
    """
    Creates a sample Deliverect snooze operation payload.
    """
    return {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {
                            "plu": "STK-01",
                            "snoozeStart": "2025-04-20T00:00:00.000000Z",
                            "snoozeEnd": "2025-04-21T00:00:00.000000Z",
                        }
                    ]
                },
            }
        ],
        "allSnoozedItems": [
            {
                "plu": "STK-01",
                "snoozeStart": "2025-04-20T00:00:00.000000Z",
                "snoozeEnd": "2025-04-21T00:00:00.000000Z",
            }
        ],
    }


@pytest.fixture
def deliverect_unsnooze_payload():
    """
    Creates a sample Deliverect unsnooze operation payload.
    """
    return {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [{"action": "unsnooze", "data": {"items": [{"plu": "STK-01"}]}}],
        "allSnoozedItems": [],
    }


@pytest.fixture
def simple_menu_format():
    """
    Creates a simple internal menu format with items, modifiers, and modifierGroups.
    """
    return {
        "items": [
            {
                "name": "Steak Frites",
                "description": "Juicy steak with crispy fries",
                "price": 1500,  # $15.00 in cents
                "plu": "STK-01",
                "reference_handler": "STK-01",
                "available": True,
                "snoozed": False,
                "category": "Main Dishes",
            },
            {
                "name": "Cheeseburger",
                "description": "Classic burger with cheese",
                "price": 1200,  # $12.00 in cents
                "plu": "BRG-01",
                "reference_handler": "BRG-01",
                "available": True,
                "snoozed": False,
                "category": "Main Dishes",
            },
            {
                "name": "French Fries",
                "description": "Crispy golden fries",
                "price": 350,  # $3.50 in cents
                "plu": "FRY-01",
                "reference_handler": "FRY-01",
                "available": True,
                "snoozed": False,
                "category": "Sides",
            },
        ],
        "modifiers": [
            {
                "name": "Rare",
                "price": 0,
                "plu": "COOK-01",
                "reference_handler": "COOK-01",
                "available": True,
                "snoozed": False,
                "group_id": "MOD-01",
            },
            {
                "name": "Medium Rare",
                "price": 0,
                "plu": "COOK-02",
                "reference_handler": "COOK-02",
                "available": True,
                "snoozed": False,
                "group_id": "MOD-01",
            },
            {
                "name": "Well Done",
                "price": 0,
                "plu": "COOK-03",
                "reference_handler": "COOK-03",
                "available": True,
                "snoozed": False,
                "group_id": "MOD-01",
            },
        ],
        "modifierGroups": [
            {
                "id": "MOD-01",
                "name": "Cooking Preference",
                "minAllowed": 1,
                "maxAllowed": 1,
                "multiMax": 1,
                "modifiers": ["COOK-01", "COOK-02", "COOK-03"],
            }
        ],
    }
