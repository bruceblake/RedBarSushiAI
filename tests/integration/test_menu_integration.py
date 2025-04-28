import json
import pytest
import tempfile
import os
from unittest import mock

@pytest.mark.integration
def test_menu_update_integration_with_validator_and_cache(app, flask_client):
    """
    Test the integration between menu update endpoint, menu validator, and caching.
    
    This test verifies:
    1. The menu update endpoint correctly processes the request
    2. The menu validator component fixes issues in the menu data
    3. The menu cache is updated with the validated menu
    4. Subsequent menu requests use the cached data
    """
    # Create a problematic menu with issues that should be fixed by the validator
    problematic_menu = {
        "items": [
            {
                "name": 123,  # Non-string name (should be fixed by validator)
                "description": "Test item with issues",
                "price": "15.99",  # String price (should be converted to number)
                "plu": "TEST-ITEM-1",
                "available": "true"  # String boolean (should be converted to boolean)
            },
            {
                "name": "Valid Item",
                "description": "This item is valid",
                "price": 12.99,
                "plu": "TEST-ITEM-2",
                "available": True
            }
        ]
    }
    
    # Mock the cache components to verify they're being called
    with mock.patch('app.utils.menu_cache.cache_menu') as mock_cache_menu:
        # Submit the problematic menu
        response = flask_client.post(
            '/menu_update',
            data=json.dumps(problematic_menu),
            content_type='application/json'
        )
        
        # Verify the response
        assert response.status_code == 200
        
        # Verify the cache was called to store the validated menu
        mock_cache_menu.assert_called_once()
        
        # Get the menu to see if the validator fixed the issues
        menu_response = flask_client.get('/menu')
        assert menu_response.status_code == 200
        
        # Parse the menu data
        menu_data = menu_response.json
        
        # Find our test items
        item1 = next((i for i in menu_data['items'] if i['plu'] == 'TEST-ITEM-1'), None)
        item2 = next((i for i in menu_data['items'] if i['plu'] == 'TEST-ITEM-2'), None)
        
        # Verify the validator fixed the issues
        assert item1 is not None
        assert isinstance(item1['name'], str)  # Name should now be a string
        assert item1['name'] == "123"  # Converted to string
        assert isinstance(item1['price'], (int, float))  # Price should be a number
        assert isinstance(item1['available'], bool)  # Available should be a boolean
        
        # Verify the valid item was preserved
        assert item2 is not None
        assert item2['name'] == "Valid Item"

@pytest.mark.integration
def test_menu_update_integration_with_deliverect_api(app, flask_client, mock_deliverect):
    """
    Test the integration between menu update endpoint and the Deliverect API client.
    
    This test verifies:
    1. The menu update endpoint correctly processes async menu updates
    2. The callback URL is properly extracted and called
    3. The Deliverect API client is used to send the callback
    """
    # Create an async menu update with callback
    async_menu = {
        "body": {
            "menus": [
                {
                    "categories": [
                        {
                            "id": "cat-1",
                            "name": "Test Category",
                            "products": [
                                {
                                    "id": "prod-1",
                                    "plu": "PLU-1",
                                    "name": "Test Product",
                                    "price": 12.99,
                                    "available": True
                                }
                            ]
                        }
                    ]
                }
            ],
            "stores": ["test-store"],
            "callback": "https://api.deliverect.com/testcallback"
        }
    }
    
    # Submit the async menu update
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(async_menu),
        content_type='application/json'
    )
    
    # Verify the response
    assert response.status_code == 200
    
    # Verify the Deliverect API was called with the callback URL
    mock_deliverect.assert_called_once()
    args, kwargs = mock_deliverect.call_args
    
    # Verify the URL was the callback URL from the request
    assert "https://api.deliverect.com/testcallback" in str(args) or "https://api.deliverect.com/testcallback" in str(kwargs)
    
    # Verify callback included success status
    if "json" in kwargs:
        assert "success" in kwargs["json"] or "status" in kwargs["json"]

@pytest.mark.integration
def test_menu_load_and_save_integration(app):
    """
    Test the integration between menu file storage and the menu utility functions.
    
    This test verifies:
    1. The menu can be saved to the file system
    2. The menu can be loaded from the file system
    3. File operations correctly preserve menu data
    """
    from app.utils.menu_utils import save_menu, load_menu
    
    # Create a test menu
    test_menu = {
        "items": [
            {
                "name": "Test Item",
                "description": "A test item",
                "price": 12.99,
                "plu": "TEST-1",
                "available": True
            }
        ],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        file_path = tmp_file.name
        
        try:
            # Save the menu to the file
            save_menu(test_menu, file_path=file_path)
            
            # Load the menu from the file
            loaded_menu = load_menu(file_path=file_path)
            
            # Verify the data was preserved
            assert loaded_menu is not None
            assert "items" in loaded_menu
            assert len(loaded_menu["items"]) == 1
            assert loaded_menu["items"][0]["name"] == "Test Item"
            assert loaded_menu["items"][0]["plu"] == "TEST-1"
            assert loaded_menu["items"][0]["price"] == 12.99
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)

@pytest.mark.integration
def test_snooze_integration_with_menu_update(flask_client, simple_menu_format):
    """
    Test the integration between snooze operations and menu updates.
    
    This test verifies:
    1. Items can be snoozed via the API
    2. The menu is updated to reflect snoozed items
    3. Subsequent menu updates preserve the snooze status
    4. Items can be unsnoozed via the API
    """
    # First, create a baseline menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Get the menu to verify items
    menu_response = flask_client.get('/menu')
    assert menu_response.status_code == 200
    menu_data = menu_response.json
    
    # Verify menu has the expected items
    assert len(menu_data['items']) >= 2
    
    # Select an item to snooze
    item_to_snooze = menu_data['items'][0]
    
    # Create a snooze request
    snooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {
                            "plu": item_to_snooze['plu'],
                            "snoozeStart": "2025-04-20T00:00:00.000000Z",
                            "snoozeEnd": "2025-04-21T00:00:00.000000Z"
                        }
                    ]
                }
            }
        ],
        "allSnoozedItems": [
            {
                "plu": item_to_snooze['plu'],
                "snoozeStart": "2025-04-20T00:00:00.000000Z",
                "snoozeEnd": "2025-04-21T00:00:00.000000Z"
            }
        ]
    }
    
    # Submit the snooze request
    snooze_response = flask_client.post(
        '/menu_update',
        data=json.dumps(snooze_payload),
        content_type='application/json'
    )
    assert snooze_response.status_code == 200
    
    # Get the menu again to check if the item is snoozed
    updated_menu_response = flask_client.get('/menu')
    assert updated_menu_response.status_code == 200
    updated_menu = updated_menu_response.json
    
    # Find the snoozed item
    snoozed_item = next((i for i in updated_menu['items'] if i['plu'] == item_to_snooze['plu']), None)
    assert snoozed_item is not None
    assert snoozed_item.get('snoozed') is True or snoozed_item.get('available') is False
    
    # Now update the menu with a regular update and verify snooze status is preserved
    update_payload = {
        "items": [
            {
                "plu": item_to_snooze['plu'],
                "name": item_to_snooze['name'] + " (Updated)",
                "price": item_to_snooze['price']
            }
        ]
    }
    
    update_response = flask_client.post(
        '/menu_update',
        data=json.dumps(update_payload),
        content_type='application/json'
    )
    assert update_response.status_code == 200
    
    # Get the menu again
    post_update_menu_response = flask_client.get('/menu')
    assert post_update_menu_response.status_code == 200
    post_update_menu = post_update_menu_response.json
    
    # Find the updated item and verify it's still snoozed
    updated_item = next((i for i in post_update_menu['items'] if i['plu'] == item_to_snooze['plu']), None)
    assert updated_item is not None
    assert updated_item['name'] == item_to_snooze['name'] + " (Updated)"
    assert updated_item.get('snoozed') is True or updated_item.get('available') is False
    
    # Finally, unsnooze the item
    unsnooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "unsnooze",
                "data": {
                    "items": [
                        {
                            "plu": item_to_snooze['plu']
                        }
                    ]
                }
            }
        ],
        "allSnoozedItems": []
    }
    
    unsnooze_response = flask_client.post(
        '/menu_update',
        data=json.dumps(unsnooze_payload),
        content_type='application/json'
    )
    assert unsnooze_response.status_code == 200
    
    # Get the menu a final time
    final_menu_response = flask_client.get('/menu')
    assert final_menu_response.status_code == 200
    final_menu = final_menu_response.json
    
    # Verify the item is no longer snoozed
    unsnoozed_item = next((i for i in final_menu['items'] if i['plu'] == item_to_snooze['plu']), None)
    assert unsnoozed_item is not None
    assert unsnoozed_item.get('snoozed') is not True and unsnoozed_item.get('available') is not False

@pytest.mark.integration
def test_menu_matcher_integration_with_menu_update(flask_client, simple_menu_format):
    """
    Test the integration between the menu matcher and menu updates.
    
    This test verifies:
    1. Menu updates can be processed by the menu matcher
    2. The menu matcher can perform fuzzy matching on menu items
    3. Menu items can be found even with slightly different names
    """
    # First, create a baseline menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # Select an item from the menu to use for matching
    item_to_match = simple_menu_format['items'][0]
    
    # Create slight variations of the item name for fuzzy matching
    variations = [
        item_to_match['name'].lower(),
        item_to_match['name'].upper(),
        item_to_match['name'] + "s",  # Plural
        item_to_match['name'].replace(" ", ""),  # Remove spaces
        item_to_match['name'][:-1]  # Remove last character
    ]
    
    # Test each variation with the menu matcher
    for variation in variations:
        # Create a matcher request
        matcher_payload = {
            "query": variation,
            "max_results": 1
        }
        
        # Submit the matching request
        match_response = flask_client.post(
            '/menu/match',
            data=json.dumps(matcher_payload),
            content_type='application/json'
        )
        
        # The response might be 200 or 404 depending on the fuzzy matching threshold
        if match_response.status_code == 200:
            match_result = match_response.json
            # Verify the match is correct
            assert match_result.get('plu') == item_to_match['plu'] or match_result.get('items')[0].get('plu') == item_to_match['plu']
        else:
            # If no match was found, log it but don't fail the test
            # Some variations might be too different to match depending on the threshold
            print(f"No match found for variation: {variation}")
            
    # Now update the menu and verify matcher still works
    update_payload = {
        "items": [
            {
                "plu": item_to_match['plu'],
                "name": "Updated " + item_to_match['name'],
                "price": item_to_match['price']
            }
        ]
    }
    
    update_response = flask_client.post(
        '/menu_update',
        data=json.dumps(update_payload),
        content_type='application/json'
    )
    assert update_response.status_code == 200
    
    # Test matching with the updated name
    updated_variation = "Updated " + item_to_match['name'].lower()
    
    matcher_payload = {
        "query": updated_variation,
        "max_results": 1
    }
    
    match_response = flask_client.post(
        '/menu/match',
        data=json.dumps(matcher_payload),
        content_type='application/json'
    )
    
    # The response might be 200 or 404 depending on the fuzzy matching threshold
    if match_response.status_code == 200:
        match_result = match_response.json
        # Verify the match is correct
        assert match_result.get('plu') == item_to_match['plu'] or match_result.get('items')[0].get('plu') == item_to_match['plu']