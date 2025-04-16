#!/usr/bin/env python3
"""
Test script for menu import functionality
"""
import json
import os
from app.utils.menu_utils import process_deliverect_menu, write_menu_file

def test_menu_import():
    """Test importing menu from test Deliverect payload"""
    # Load test data
    test_file_path = 'testing_data/test_deliverect_payload.json'
    if not os.path.exists(test_file_path):
        test_file_path = '../' + test_file_path
        
    with open(test_file_path, 'r') as f:
        data = json.load(f)
    
    # Process the data
    processed = process_deliverect_menu(data)
    
    # Print stats
    print(f"Processed {len(processed.get('items', []))} items")
    print(f"Processed {len(processed.get('modifierGroups', []))} modifier groups")
    print(f"Generated {len(processed.get('name_variants', {}))} name variants")
    
    # Write to a test-specific file not the main menu file
    test_menu_path = 'testing_data/test_menu_import_output.json'
    if not os.path.exists('testing_data'):
        os.makedirs('testing_data')
        
    success = write_menu_file(processed, file_path=test_menu_path)
    print(f"Write success: {success}")
    
    # Verify the results
    assert 'items' in processed, "Processed result should contain 'items'"
    assert 'name_variants' in processed, "Processed result should contain 'name_variants'"
    assert len(processed['items']) > 0, "There should be at least one item in processed result"
    assert success is True, "Menu file should be written successfully"

if __name__ == "__main__":
    test_menu_import()