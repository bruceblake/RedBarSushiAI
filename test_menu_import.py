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
    with open('testing_data/test_deliverect_payload.json', 'r') as f:
        data = json.load(f)
    
    # Process the data
    processed = process_deliverect_menu(data)
    
    # Print stats
    print(f"Processed {len(processed.get('items', []))} items")
    print(f"Processed {len(processed.get('modifierGroups', []))} modifier groups")
    print(f"Generated {len(processed.get('name_variants', {}))} name variants")
    
    # Write to menu_data.json
    success = write_menu_file(processed)
    print(f"Write success: {success}")
    
    return processed

if __name__ == "__main__":
    test_menu_import()