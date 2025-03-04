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
        from app.utils.menu_utils import _cached_data, _last_load_time
        globals()['_cached_data'] = None
        globals()['_last_load_time'] = 0
        
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


def test_load_menu_data_file_not_found(app):
    """Test loading menu data when the file doesn't exist."""
    # Force reset the cache first
    from app.utils.menu_utils import _cached_data, _last_load_time
    globals()['_cached_data'] = None
    globals()['_last_load_time'] = 0
    
    # Configure a non-existent file path
    nonexistent_path = os.path.join(app.root_path, 'nonexistent_file.json')
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
    from app.utils.menu_utils import _cached_data, _last_load_time
    globals()['_cached_data'] = None
    globals()['_last_load_time'] = 0
    
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
    # Mock the current day and time
    mock_now = datetime(2024, 2, 20, 12, 0, 0, tzinfo=timezone.utc)  # Tuesday at noon
    
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now
        
        # Test item with no availabilities (should be available)
        item1 = {"availabilities": []}
        assert is_item_currently_available_by_schedule(item1) is True
        
        # Test item with matching availabilities
        item2 = {
            "availabilities": [
                {"dayOfWeek": 2, "startTime": "11:00", "endTime": "14:00"}
            ]
        }
        assert is_item_currently_available_by_schedule(item2) is True
        
        # Test item with non-matching day
        item3 = {
            "availabilities": [
                {"dayOfWeek": 3, "startTime": "11:00", "endTime": "14:00"}
            ]
        }
        assert is_item_currently_available_by_schedule(item3) is False
        
        # Test item with non-matching time
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


@patch('flask.jsonify')
def test_menu_update_endpoint(mock_jsonify, client, app, setup_test_menu):
    """Test the menu update endpoint."""
    # Setup mock response
    mock_response = MagicMock()
    mock_jsonify.return_value = mock_response
    
    with app.app_context():
        with patch('app.routes.menu.write_menu_file') as mock_write:
            # Test with valid data
            new_menu = [
                {"name": "New Roll", "price": 12.99, "reference_handler": "new_roll_1"}
            ]
            
            response = client.post('/menu_update', json=new_menu)
            assert response.status_code in [200, 201]


def test_snooze_unsnooze_endpoint(client, app):
    """Test the snooze/unsnooze endpoint."""
    with app.app_context():
        with patch('app.routes.menu.load_menu_data') as mock_load, \
             patch('app.routes.menu.write_menu_file') as mock_write:
            
            # Setup mock data
            mock_data = {
                "items": [
                    {"name": "California Roll", "snoozed": False, "scheduleAvailable": True}
                ]
            }
            mock_load.return_value = mock_data
            
            # Test with valid data
            data = {"operations": [{"item": "California Roll", "action": "snooze"}]}
            
            response = client.post('/snoozeUnsnooze', json=data)
            assert response.status_code == 200