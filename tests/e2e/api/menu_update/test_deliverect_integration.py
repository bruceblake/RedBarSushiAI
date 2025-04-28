import pytest
import json
import os

@pytest.mark.e2e
def test_deliverect_webhook_structure(api_request):
    """
    Test the menu update endpoint with a payload structure that matches
    the Deliverect webhook format as described in the documentation.
    """
    # Create a payload based on the Deliverect format described in real_docs.md
    payload = {
        "body": {
            "menus": [
                {
                    "menu": "Test Menu",
                    "menuId": "67209bfb174a0e5384d4db61",
                    "channelLinkId": "66b35566dc02e27b286fca60", 
                    "currency": 1,
                    "menuType": 0,
                    "availabilities": [
                        {"dayOfWeek": 1, "startTime": "00:00", "endTime": "23:59"},
                        {"dayOfWeek": 2, "startTime": "00:00", "endTime": "23:59"},
                        {"dayOfWeek": 3, "startTime": "00:00", "endTime": "23:59"}
                    ],
                    "categories": [
                        {
                            "_id": "67209bfb174a0e5384d4db4f",
                            "name": "Steak & Burgers",
                            "posCategoryId": "STK",
                            "subProducts": [
                                "6721daafc33216a11b4e239d",
                                "6721daafc33216a11b4e23a2"
                            ],
                            "availabilities": []
                        },
                        {
                            "_id": "67209bfb174a0e5384d4db50",
                            "name": "Sides",
                            "posCategoryId": "SD",
                            "subProducts": [
                                "66b35629a7eb47d479f1d309",
                                "66b35629a7eb47d479f1d30b"
                            ],
                            "availabilities": []
                        }
                    ],
                    "products": {
                        "66b35629a7eb47d479f1d339": {
                            "_id": "66b35629a7eb47d479f1d339",
                            "name": "Delicious Steak Frites",
                            "description": "Basic Example Product with - Modifier groups...",
                            "price": 1500,
                            "plu": "STK-01", 
                            "productType": 1,
                            "imageUrl": "https://example.com/image.jpg",
                            "subProducts": [
                                "66b35629a7eb47d479f1d33b",
                                "66b35629a7eb47d479f1d2fb"
                            ],
                            "snoozed": False,
                            "deliveryTax": 9000,
                            "takeawayTax": 9000,
                            "eatInTax": 9000
                        },
                        "66b35629a7eb47d479f1d309": {
                            "_id": "66b35629a7eb47d479f1d309",
                            "name": "White Rice",
                            "description": "White coloured rice",
                            "price": 450,
                            "plu": "RICE-01",
                            "productType": 1,
                            "subProducts": [
                                "66b35629a7eb47d479f1d345"
                            ],
                            "snoozed": False,
                            "deliveryTax": 9000,
                            "takeawayTax": 9000,
                            "eatInTax": 9000
                        }
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
                                "66b35629a7eb47d479f1d33d"
                            ],
                            "snoozed": False
                        }
                    },
                    "modifiers": {
                        "66b35629a7eb47d479f1d2fd": {
                            "_id": "66b35629a7eb47d479f1d2fd",
                            "name": "Rare",
                            "price": 0,
                            "plu": "COOK-01",
                            "productType": 2,
                            "parentId": "66b35629a7eb47d479f1d33b",
                            "snoozed": False
                        },
                        "66b35629a7eb47d479f1d2ff": {
                            "_id": "66b35629a7eb47d479f1d2ff",
                            "name": "Medium Rare",
                            "price": 0,
                            "plu": "COOK-02",
                            "productType": 2,
                            "parentId": "66b35629a7eb47d479f1d33b",
                            "snoozed": False
                        }
                    },
                    "snoozedProducts": {}
                }
            ],
            "stores": ["66b35566dc02e27b286fca60"],
            "callback": "https://api.staging.deliverect.com/testchannel/menuStatus/test123"
        }
    }
    
    resp = api_request.post("/menu_update", data=payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert "items" in response_data
    assert response_data["source"] == "deliverect"
    
    # Verify the menu is updated correctly by retrieving it
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    
    # Verify PLUs are correctly preserved
    plus = [item.get("plu") for item in menu_data["items"]]
    assert "STK-01" in plus
    assert "RICE-01" in plus
    
    # Verify modifier PLUs are correctly preserved
    modifier_plus = [mod.get("plu") for mod in menu_data["modifiers"]]
    assert "COOK-01" in modifier_plus
    assert "COOK-02" in modifier_plus

@pytest.mark.e2e
def test_async_callback_functionality(api_request, mocker):
    """
    Test that the async callback functionality works.
    
    This test mocks the requests.post function to verify that the callback
    URL is called with the right parameters.
    """
    # Mock the requests.post function
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    
    # Create a payload with a callback URL
    payload = {
        "body": {
            "menus": [
                {
                    "menu": "Test Menu",
                    "categories": [
                        {
                            "_id": "cat1",
                            "name": "Test Category",
                            "subProducts": ["prod1"]
                        }
                    ],
                    "products": {
                        "prod1": {
                            "_id": "prod1",
                            "name": "Test Product",
                            "price": 1000,
                            "plu": "TEST-01",
                            "productType": 1
                        }
                    }
                }
            ],
            "stores": ["store1"],
            "callback": "https://api.staging.deliverect.com/testchannel/menuStatus/test456"
        }
    }
    
    resp = api_request.post("/menu_update", data=payload)
    assert resp.status == 200
    
    # Verify the callback was called
    mock_post.assert_called_once_with(
        "https://api.staging.deliverect.com/testchannel/menuStatus/test456",
        json={"status": "ONLINE", "comment": mocker.ANY}
    )

@pytest.mark.e2e
def test_menu_update_preserves_plus(api_request):
    """
    Test that the menu update endpoint preserves PLUs, which are
    critical for Deliverect integration.
    """
    # Create a menu with specific PLUs
    payload = {
        "items": [
            {
                "name": "Test Item 1",
                "description": "Description 1",
                "price": 10.0,
                "available": True,
                "plu": "SPECIFIC-PLU-1",
                "reference_handler": "SPECIFIC-PLU-1"
            },
            {
                "name": "Test Item 2",
                "description": "Description 2",
                "price": 20.0,
                "available": True,
                "plu": "SPECIFIC-PLU-2",
                "reference_handler": "SPECIFIC-PLU-2"
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=payload)
    assert resp.status == 200
    
    # Update the menu again with the same items but without PLUs
    updated_payload = {
        "items": [
            {
                "name": "Test Item 1",
                "description": "Updated Description 1",
                "price": 15.0,
                "available": True
                # No PLU or reference_handler
            },
            {
                "name": "Test Item 2",
                "description": "Updated Description 2",
                "price": 25.0,
                "available": True
                # No PLU or reference_handler
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=updated_payload)
    assert resp.status == 200
    
    # Get the menu and verify PLUs are preserved
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    
    # Find our test items
    item1 = next((i for i in menu_data["items"] if i["name"] == "Test Item 1"), None)
    item2 = next((i for i in menu_data["items"] if i["name"] == "Test Item 2"), None)
    
    assert item1 is not None
    assert item2 is not None
    
    # Verify PLUs are preserved
    assert item1.get("plu") == "SPECIFIC-PLU-1"
    assert item2.get("plu") == "SPECIFIC-PLU-2"
    
    # Verify other updates were applied
    assert item1.get("description") == "Updated Description 1"
    assert item1.get("price") == 15.0
    assert item2.get("description") == "Updated Description 2"
    assert item2.get("price") == 25.0

@pytest.mark.e2e
def test_snooze_unsnooze_with_deliverect_format(api_request):
    """
    Test the snooze/unsnooze endpoint with the Deliverect format.
    """
    # First create some items
    menu_payload = {
        "items": [
            {
                "name": "Test Snooze Item",
                "description": "Item to test snoozing",
                "price": 10.0,
                "available": True,
                "plu": "SNOOZE-TEST-1",
                "reference_handler": "SNOOZE-TEST-1"
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=menu_payload)
    assert resp.status == 200
    
    # Snooze the item using Deliverect format
    snooze_payload = {
        "accountId": "test-account",
        "locationId": "test-location",
        "channelLinkId": "test-channel-link",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {"plu": "SNOOZE-TEST-1", "snoozeStart": "2025-04-20T00:00:00Z", "snoozeEnd": "2025-04-21T00:00:00Z"}
                    ]
                }
            }
        ],
        "allSnoozedItems": [
            {"plu": "SNOOZE-TEST-1", "snoozeStart": "2025-04-20T00:00:00Z", "snoozeEnd": "2025-04-21T00:00:00Z"}
        ]
    }
    
    snooze_resp = api_request.post("/snoozeUnsnooze", data=snooze_payload)
    assert snooze_resp.status == 200
    
    # Get the menu and verify the item is snoozed
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    snooze_item = next((i for i in menu_data["items"] if i["plu"] == "SNOOZE-TEST-1"), None)
    
    assert snooze_item is not None
    assert snooze_item.get("snoozed") is True
    assert snooze_item.get("available") is False
    
    # Now unsnooze the item
    unsnooze_payload = {
        "accountId": "test-account",
        "locationId": "test-location",
        "channelLinkId": "test-channel-link",
        "operations": [
            {
                "action": "unsnooze",
                "data": {
                    "items": [
                        {"plu": "SNOOZE-TEST-1"}
                    ]
                }
            }
        ],
        "allSnoozedItems": [] # No items are snoozed anymore
    }
    
    unsnooze_resp = api_request.post("/snoozeUnsnooze", data=unsnooze_payload)
    assert unsnooze_resp.status == 200
    
    # Get the menu and verify the item is unsnoozed
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    snooze_item = next((i for i in menu_data["items"] if i["plu"] == "SNOOZE-TEST-1"), None)
    
    assert snooze_item is not None
    assert snooze_item.get("snoozed") is False
    assert snooze_item.get("available") is True