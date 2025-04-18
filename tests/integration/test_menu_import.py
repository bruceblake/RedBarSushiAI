#!/usr/bin/env python3
"""
Test script for menu import functionality
"""
import json
import os
import pytest
from app.utils.menu_utils import process_deliverect_menu, write_menu_file

def test_menu_import(monkeypatch):
    """Test importing menu from test Deliverect payload"""
    # Load test data from project root testing_data
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    test_file_path = os.path.join(root, 'testing_data', 'test_deliverect_payload.json')
    with open(test_file_path, 'r') as f:
        data = json.load(f)
    
    # Mock file writing to avoid file system changes during tests
    def mock_write_menu_file(menu_data, file_path=None):
        return True
        
    monkeypatch.setattr('app.utils.menu_utils.write_menu_file', mock_write_menu_file)
    
    # Process the data
    processed = process_deliverect_menu(data)
    
    # Verify the results
    assert 'items' in processed, "Processed result should contain 'items'"
    assert 'name_variants' in processed, "Processed result should contain 'name_variants'"
    assert len(processed['items']) > 0, "There should be at least one item in processed result"
    
    # Check that we have the expected items
    item_names = [item['name'] for item in processed['items']]
    assert 'California Roll' in item_names, "Menu should include California Roll"
    assert 'Spicy Tuna Roll' in item_names, "Menu should include Spicy Tuna Roll"
    assert 'Edamame' in item_names, "Menu should include Edamame"
    assert 'Salmon Nigiri' in item_names, "Menu should include Salmon Nigiri"
    
    # Check that availability is correctly processed
    available_items = [item for item in processed['items'] if item['available']]
    unavailable_items = [item for item in processed['items'] if not item['available']]
    
    # Print the available items for debugging purposes
    print(f"Available items: {[item['name'] for item in available_items]}")
    
    # The deliverect format results in 8 available items:
    # - Test Menu (top level), Add Extras, Appetizers, Sushi Rolls (category headers)
    # - Extra Wasabi, Extra Ginger, Edamame, Miso Soup, California Roll, Spicy Tuna Roll, Rainbow Roll
    assert len(available_items) >= 7, "Should have at least 7 available items"
    assert len(unavailable_items) >= 1, "Should have at least 1 unavailable item"
    
    # Check that specific items have correct availability
    salmon_nigiri = next((item for item in processed['items'] if item['name'] == 'Salmon Nigiri'), None)
    assert salmon_nigiri is not None, "Salmon Nigiri should be in the processed items"
    assert not salmon_nigiri['available'], "Salmon Nigiri should be unavailable"
    
    california_roll = next((item for item in processed['items'] if item['name'] == 'California Roll'), None)
    assert california_roll is not None, "California Roll should be in the processed items"
    assert california_roll['available'], "California Roll should be available"