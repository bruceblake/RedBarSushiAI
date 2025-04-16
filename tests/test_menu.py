"""
test_menu.py - Tests for menu-related functionality
"""
import json
import os
import pytest
import time
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime, timedelta, timezone
from flask import Flask

from app.utils.menu_utils import (
    write_menu_file, 
    load_menu_data, 
    parse_utc_timestamp, 
    is_item_snoozed_timebased, 
    is_item_currently_available_by_schedule
)


def test_write_menu_file(app, tmp_path):
    """Test writing menu data to a file."""
    # Setup a temp path for the menu file
    test_file = tmp_path / "test_menu.json"
    test_data = {"items": [{"name": "Test Item", "price": 9.99}]}
    
    # Configure the app to use the temp file
    app.config['MENU_FILE_PATH'] = str(test_file)
    
    with app.app_context():
        # Test writing to the file
        write_menu_file(test_data)
        
        # Verify the file was written correctly
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data == test_data


def test_load_menu_data(app, setup_test_menu, mock_menu_data):
    """Test loading menu data from file."""
    with app.app_context():
        # Force reset the cache first
        from app.utils.menu_utils import _menu_cache, _last_refresh_time
        globals()['_menu_cache'] = None
        globals()['_last_refresh_time'] = 0
        
        # Setup the menu file with mock data
        menu_path = app.config['MENU_FILE_PATH']
        os.makedirs(os.path.dirname(menu_path), exist_ok=True)
        with open(menu_path, 'w') as f:
            json.dump(mock_menu_data, f)
        
        # Test loading from the file
        data = load_menu_data(force_refresh=True)
        
        # Verify the data contains items
        assert 'items' in data
        assert isinstance(data['items'], list)
        
        # Test that caching works
        start_time = time.time()
        cached_data = load_menu_data()
        assert time.time() - start_time < 0.01  # Should be very fast with caching
        
        # Force refresh and verify cache is updated
        refreshed_data = load_menu_data(force_refresh=True)
        assert refreshed_data is not None


def test_load_menu_data_file_not_found(app, tmp_path):
    """Test loading menu data when the file doesn't exist."""
    # Force reset the cache first
    from app.utils.menu_utils import _menu_cache, _last_refresh_time
    globals()['_menu_cache'] = None
    globals()['_last_refresh_time'] = 0
    
    # Create a non-existent path in the temp directory
    nonexistent_path = os.path.join(str(tmp_path), 'nonexistent_file.json')
    # Make sure the directory exists
    os.makedirs(os.path.dirname(nonexistent_path), exist_ok=True)
    app.config['MENU_FILE_PATH'] = nonexistent_path
    
    # Make sure the file doesn't exist
    if os.path.exists(nonexistent_path):
        os.remove(nonexistent_path)
    
    with app.app_context():
        # Test loading with missing file
        data = load_menu_data(force_refresh=True)
        
        # Should have an items key that's an empty list
        assert 'items' in data
        assert isinstance(data['items'], list)
        assert len(data['items']) == 0


def test_load_menu_data_invalid_json(app, tmp_path):
    """Test loading menu data with invalid JSON."""
    # Force reset the cache first
    from app.utils.menu_utils import _menu_cache, _last_refresh_time
    globals()['_menu_cache'] = None
    globals()['_last_refresh_time'] = 0
    
    # Setup a temp file with invalid JSON
    test_file = tmp_path / "invalid_menu.json"
    with open(test_file, 'w') as f:
        f.write("{not valid json")
    
    # Configure app to use the temp file
    app.config['MENU_FILE_PATH'] = str(test_file)
    
    with app.app_context():
        # Test loading with invalid JSON
        data = load_menu_data(force_refresh=True)
        
        # Should have items field with empty list
        assert 'items' in data
        assert isinstance(data['items'], list)
        assert len(data['items']) == 0


def test_parse_utc_timestamp():
    """Test parsing UTC timestamps."""
    # Test with valid timestamp with Z suffix
    ts1 = "2024-02-20T14:30:00Z"
    parsed1 = parse_utc_timestamp(ts1)
    assert parsed1.hour == 14
    assert parsed1.minute == 30
    assert parsed1.tzinfo is not None
    
    # Test with valid timestamp without Z suffix
    ts2 = "2024-02-20T14:30:00"
    parsed2 = parse_utc_timestamp(ts2)
    assert parsed2.hour == 14
    assert parsed2.minute == 30
    
    # Test with invalid timestamp
    assert parse_utc_timestamp("not a timestamp") is None
    
    # Test with empty string
    assert parse_utc_timestamp("") is None
    
    # Test with None
    assert parse_utc_timestamp(None) is None


def test_is_item_snoozed_timebased():
    """Test checking if an item is snoozed based on time."""
    now = datetime.now(timezone.utc)
    
    # Item with active snooze
    item1 = {
        "snoozeStart": (now - timedelta(hours=1)).isoformat(),
        "snoozeEnd": (now + timedelta(hours=1)).isoformat()
    }
    assert is_item_snoozed_timebased(item1) is True
    
    # Item with expired snooze
    item2 = {
        "snoozeStart": (now - timedelta(hours=2)).isoformat(),
        "snoozeEnd": (now - timedelta(hours=1)).isoformat()
    }
    assert is_item_snoozed_timebased(item2) is False
    
    # Item with future snooze
    item3 = {
        "snoozeStart": (now + timedelta(hours=1)).isoformat(),
        "snoozeEnd": (now + timedelta(hours=2)).isoformat()
    }
    assert is_item_snoozed_timebased(item3) is False
    
    # Item without snooze parameters
    item4 = {}
    assert is_item_snoozed_timebased(item4) is False
    
    # Item with invalid snooze parameters
    item5 = {
        "snoozeStart": "invalid",
        "snoozeEnd": "also invalid"
    }
    assert is_item_snoozed_timebased(item5) is False


def test_is_item_currently_available_by_schedule():
    """Test checking if an item is available based on schedule."""
    # Mock the datetime module
    with patch('app.utils.menu_utils.datetime') as mock_datetime:
        # Set up mock for Tuesday at noon (day 2)
        mock_now = datetime(2024, 2, 20, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Test item with no availabilities (should be available)
        item1 = {"availabilities": []}
        assert is_item_currently_available_by_schedule(item1) is True
        
        # Test item with matching availabilities for Tuesday (day 2)
        item2 = {
            "availabilities": [
                {"dayOfWeek": 2, "startTime": "11:00", "endTime": "14:00"}
            ]
        }
        assert is_item_currently_available_by_schedule(item2) is True
        
        # Test item with non-matching day (day 3 - Wednesday)
        item3 = {
            "availabilities": [
                {"dayOfWeek": 3, "startTime": "11:00", "endTime": "14:00"}
            ]
        }
        assert is_item_currently_available_by_schedule(item3) is False
        
        # Test item with non-matching time (too late)
        item4 = {
            "availabilities": [
                {"dayOfWeek": 2, "startTime": "14:00", "endTime": "18:00"}
            ]
        }
        assert is_item_currently_available_by_schedule(item4) is False
        
        # Test item with invalid time format
        item5 = {
            "availabilities": [
                {"dayOfWeek": 2, "startTime": "invalid", "endTime": "also invalid"}
            ]
        }
        assert is_item_currently_available_by_schedule(item5) is False


@patch('app.routes.menu.write_menu_file')
@patch('app.routes.menu.load_menu_data')
@patch('app.routes.menu.process_deliverect_menu')
def test_menu_update_endpoint(mock_process, mock_load, mock_write, client, app, setup_test_menu):
    """Test the menu update endpoint."""
    # Setup mocks
    processed_data = {"items": [{"name": "Test Item"}], "modifierGroups": [], "name_variants": {}}
    mock_process.return_value = processed_data
    mock_load.return_value = processed_data
    mock_write.return_value = True
    
    # Test with valid Deliverect data
    test_data = {"categories": [{"name": "Test Category", "products": [{"name": "Test Product"}]}]}
    response = client.post('/menu_update', json=test_data)
    
    # Check response
    assert response.status_code == 200
    assert response.json.get("success") is True
    
    # Check that process_deliverect_menu was called
    mock_process.assert_called_once_with(test_data)
    
    # Check that write_menu_file was called with processed data
    mock_write.assert_called_once_with(processed_data)


@patch('app.routes.menu.load_menu_data')
@patch('app.routes.menu.write_menu_file')
def test_snooze_unsnooze_endpoint(mock_write, mock_load, client, app, mock_menu_data):
    """Test the snooze/unsnooze endpoint."""
    # Setup mock data
    mock_load.return_value = mock_menu_data
    
    # Test with valid snooze operation
    data = {"operations": [{"item": "California Roll", "action": "snooze"}]}
    
    # Send request
    response = client.post('/snoozeUnsnooze', json=data)
    
    # Check response
    assert response.status_code == 200
    
    # Check that load_menu_data was called
    mock_load.assert_called_once()
    
    # Check that write_menu_file was called with updated data
    mock_write.assert_called_once()
    
    # Check that the item was snoozed in the data
    called_data = mock_write.call_args[0][0]
    california_roll = next((item for item in called_data.get("items", []) 
                            if item.get("name") == "California Roll"), None)
    assert california_roll is not None
    assert california_roll.get("snoozed") is True