import json
import pytest
from unittest import mock
from app.utils.menu_utils import load_menu_data

@pytest.mark.integration
def test_menu_update_with_deliverect_format(flask_client, deliverect_menu_json, mock_deliverect):
    """
    Test updating the menu with the Deliverect format.
    Verifies:
    1. The API accepts the standard Deliverect format
    2. The menu is properly processed and stored
    3. PLUs are preserved
    """
    # Send the Deliverect menu update request
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(deliverect_menu_json),
        content_type='application/json'
    )
    
    # Assert the response status and content
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'items' in response.json
    assert response.json['source'] == 'deliverect'
    
    # Get the menu to verify it was updated
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    assert 'items' in menu_data
    assert len(menu_data['items']) > 0
    
    # Verify specific items with their PLUs
    plu_map = {item['name']: item['plu'] for item in menu_data['items']}
    assert 'Delicious Steak Frites' in plu_map
    assert plu_map.get('Delicious Steak Frites') == 'STK-01'
    assert 'Classic Cheeseburger' in plu_map
    assert plu_map.get('Classic Cheeseburger') == 'BRG-01'
    
    # Verify prices are in cents
    price_map = {item['name']: item['price'] for item in menu_data['items']}
    assert price_map.get('Delicious Steak Frites') == 1500
    assert price_map.get('Classic Cheeseburger') == 1200

@pytest.mark.integration
def test_menu_update_with_async_format(flask_client, deliverect_async_menu_json, mock_deliverect):
    """
    Test updating the menu with the Deliverect async format.
    Verifies:
    1. The API accepts the async format with callback
    2. The callback URL is used to notify Deliverect
    """
    # Send the async menu update request
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(deliverect_async_menu_json),
        content_type='application/json'
    )
    
    # Assert the response status and content
    assert response.status_code == 200
    assert response.json['success'] is True
    
    # Verify the callback was made to Deliverect
    assert mock_deliverect.called
    # Check the URL and payload of the callback
    callback_url = deliverect_async_menu_json['body']['callback']
    mock_deliverect.assert_any_call(
        callback_url,
        json=mock.ANY
    )
    # Verify the status in the callback is "ONLINE"
    for call in mock_deliverect.call_args_list:
        if call[0][0] == callback_url:
            assert call[1]['json']['status'] == 'ONLINE'

@pytest.mark.integration
def test_menu_update_with_simple_format(flask_client, simple_menu_format):
    """
    Test updating the menu with the simple internal format.
    Verifies:
    1. The API accepts the simple format
    2. Items, modifiers, and modifierGroups are properly stored
    """
    # Send the simple menu update request
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    
    # Assert the response status and content
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['items'] == len(simple_menu_format['items'])
    assert response.json['modifiers'] == len(simple_menu_format['modifiers'])
    assert response.json['modifierGroups'] == len(simple_menu_format['modifierGroups'])
    
    # Get the menu to verify it was updated
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    assert 'items' in menu_data
    assert len(menu_data['items']) == len(simple_menu_format['items'])
    
    # Verify item names and PLUs
    item_names = [item['name'] for item in menu_data['items']]
    for item in simple_menu_format['items']:
        assert item['name'] in item_names
        
    # Verify modifiers
    assert 'modifiers' in menu_data
    assert len(menu_data['modifiers']) == len(simple_menu_format['modifiers'])
    
    # Verify modifier groups
    assert 'modifierGroups' in menu_data
    assert len(menu_data['modifierGroups']) == len(simple_menu_format['modifierGroups'])

@pytest.mark.integration
def test_menu_update_preserves_plus(flask_client, simple_menu_format):
    """
    Test that menu updates preserve PLUs and reference_handlers.
    Verifies:
    1. PLUs are preserved when updating items
    2. reference_handlers are preserved when updating items
    """
    # First update with the original menu
    flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    
    # Create an updated version with modified descriptions and prices, but missing PLUs
    updated_menu = {
        "items": [
            {
                "name": "Steak Frites",
                "description": "Updated description for steak",
                "price": 1600  # $16.00 in cents
                # No PLU or reference_handler
            },
            {
                "name": "Cheeseburger",
                "description": "Updated description for burger",
                "price": 1300  # $13.00 in cents
                # No PLU or reference_handler
            }
        ]
    }
    
    # Update with the modified menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(updated_menu),
        content_type='application/json'
    )
    
    # Assert the update was successful
    assert response.status_code == 200
    assert response.json['success'] is True
    
    # Get the menu to verify PLUs were preserved
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    
    # Find our updated items
    steak = next((i for i in menu_data['items'] if i['name'] == 'Steak Frites'), None)
    burger = next((i for i in menu_data['items'] if i['name'] == 'Cheeseburger'), None)
    
    # Verify PLUs and reference_handlers were preserved
    assert steak is not None
    assert 'plu' in steak
    assert steak['plu'] == 'STK-01'
    assert 'reference_handler' in steak
    assert steak['reference_handler'] == 'STK-01'
    
    assert burger is not None
    assert 'plu' in burger
    assert burger['plu'] == 'BRG-01'
    assert 'reference_handler' in burger
    assert burger['reference_handler'] == 'BRG-01'
    
    # Verify the descriptions and prices were updated
    assert steak['description'] == 'Updated description for steak'
    assert steak['price'] == 1600
    assert burger['description'] == 'Updated description for burger'
    assert burger['price'] == 1300

@pytest.mark.integration
def test_snooze_unsnooze_functionality(flask_client, deliverect_menu_json, deliverect_snooze_payload, deliverect_unsnooze_payload):
    """
    Test the snooze/unsnooze functionality for menu items.
    Verifies:
    1. Items can be snoozed with proper Deliverect format
    2. Snoozed items are marked as unavailable
    3. Items can be unsnoozed
    """
    # First update the menu
    flask_client.post(
        '/menu_update',
        data=json.dumps(deliverect_menu_json),
        content_type='application/json'
    )
    
    # Snooze an item
    snooze_response = flask_client.post(
        '/snoozeUnsnooze',
        data=json.dumps(deliverect_snooze_payload),
        content_type='application/json'
    )
    
    # Assert the snooze was successful
    assert snooze_response.status_code == 200
    assert snooze_response.json['status'] == 'success'
    
    # Get the menu to verify the item is snoozed
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    
    # Find the snoozed item
    steak = next((i for i in menu_data['items'] if i['plu'] == 'STK-01'), None)
    
    # Verify it's marked as snoozed and unavailable
    assert steak is not None
    assert steak['snoozed'] is True
    assert steak['available'] is False
    
    # Now unsnooze the item
    unsnooze_response = flask_client.post(
        '/snoozeUnsnooze',
        data=json.dumps(deliverect_unsnooze_payload),
        content_type='application/json'
    )
    
    # Assert the unsnooze was successful
    assert unsnooze_response.status_code == 200
    assert unsnooze_response.json['status'] == 'success'
    
    # Get the menu again to verify the item is unsnoozed
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    
    # Find the unsnoozed item
    steak = next((i for i in menu_data['items'] if i['plu'] == 'STK-01'), None)
    
    # Verify it's no longer snoozed and is available
    assert steak is not None
    assert steak['snoozed'] is False
    assert steak['available'] is True

@pytest.mark.integration
def test_menu_cache_clear(flask_client, simple_menu_format):
    """
    Test the menu cache clear functionality.
    Verifies:
    1. Menu can be loaded from cache
    2. Cache can be cleared
    3. Menu is reloaded after cache clear
    """
    # First update the menu
    flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    
    # Get the menu to populate the cache
    flask_client.get('/menu')
    
    # Clear the cache
    clear_response = flask_client.get('/clear_menu_cache')
    
    # Assert the cache clear was successful
    assert clear_response.status_code == 200
    assert clear_response.json['success'] is True
    assert 'message' in clear_response.json
    assert 'items loaded' in clear_response.json['message']
    
    # Get the menu again to verify it's still accessible
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    assert 'items' in menu_data
    assert len(menu_data['items']) > 0

@pytest.mark.integration
def test_partial_menu_update(flask_client, simple_menu_format):
    """
    Test partial menu updates.
    Verifies:
    1. Partial updates preserve existing items in other categories
    2. Updates only affect the specified items
    """
    # First update with the full menu
    flask_client.post(
        '/menu_update',
        data=json.dumps(simple_menu_format),
        content_type='application/json'
    )
    
    # Create a partial update with just one new item in a new category
    partial_update = {
        "items": [
            {
                "name": "Chocolate Cake",
                "description": "Rich chocolate cake",
                "price": 800,  # $8.00 in cents
                "plu": "DST-01",
                "reference_handler": "DST-01",
                "available": True,
                "snoozed": False,
                "category": "Desserts"
            }
        ]
    }
    
    # Apply the partial update
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(partial_update),
        content_type='application/json'
    )
    
    # Assert the update was successful
    assert response.status_code == 200
    assert response.json['success'] is True
    
    # Get the menu to verify both old and new items exist
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    
    # Get all item names
    item_names = [item['name'] for item in menu_data['items']]
    
    # Verify that both original and new items exist
    assert 'Steak Frites' in item_names
    assert 'Cheeseburger' in item_names
    assert 'French Fries' in item_names
    assert 'Chocolate Cake' in item_names

@pytest.mark.integration
def test_menu_validator_fixes_issues(flask_client):
    """
    Test that the menu validator fixes common issues.
    Verifies:
    1. Items with invalid fields are fixed
    2. Missing fields receive default values
    3. The resulting menu is valid
    """
    # Create a menu with various issues
    problematic_menu = {
        "items": [
            {
                "name": 12345,  # Number instead of string
                "description": ["This", "is", "a", "list"],  # List instead of string
                "price": "10.00",  # String instead of number
                "available": 1,  # Number instead of boolean
                "plu": "PROB-01"
            },
            {
                "name": "",  # Empty name
                "price": -5.00,  # Negative price
                "plu": "PROB-02"
            },
            {
                # Missing name
                "description": "Item with missing name",
                "price": 15.00,
                "plu": "PROB-03"
            }
        ]
    }
    
    # Try to update with the problematic menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(problematic_menu),
        content_type='application/json'
    )
    
    # These issues should be fixed, so the update should succeed
    assert response.status_code == 200
    assert response.json['success'] is True
    
    # Get the menu to verify the issues were fixed
    get_response = flask_client.get('/menu')
    assert get_response.status_code == 200
    
    menu_data = get_response.json
    
    # Find the first item (with number as name)
    item1 = next((i for i in menu_data['items'] if i['plu'] == 'PROB-01'), None)
    assert item1 is not None
    assert isinstance(item1['name'], str)  # Name should now be a string
    assert isinstance(item1['description'], str)  # Description should now be a string
    assert isinstance(item1['price'], (int, float))  # Price should be a number
    assert isinstance(item1['available'], bool)  # Available should be a boolean
    
    # Find the second item (with empty name)
    item2 = next((i for i in menu_data['items'] if i['plu'] == 'PROB-02'), None)
    assert item2 is not None
    assert item2['name'] != ""  # Name should not be empty anymore
    assert item2['price'] > 0  # Price should be positive now
    
    # Find the third item (with missing name)
    item3 = next((i for i in menu_data['items'] if i['plu'] == 'PROB-03'), None)
    assert item3 is not None
    assert item3['name'] != ""  # Name should be set to a default value
    assert 'description' in item3  # Description should be preserved