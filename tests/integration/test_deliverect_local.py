#!/usr/bin/env python
"""
Local test script for Deliverect Menu Integration.

This script provides a convenient way to test the Deliverect integration
without having to deploy changes to the server. It will:

1. Read sample Deliverect menu data from a JSON file
2. Process it using the same code as the live server
3. Output diagnostics to help troubleshoot issues

Usage:
    python test_deliverect_local.py [input_file.json]

If no input file is specified, it will look for 'deliverect_sample.json'
in the current directory.
"""

import json
import sys
import os
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Make sure we can import from app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the actual processing functions
from app.utils.menu_utils import process_deliverect_menu, add_name_variants
from app.utils.menu_validator import validate_and_fix_menu_data

def main():
    # Get the input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'deliverect_sample.json'
    
    print(f"Processing {input_file}...")
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found")
        return 1
    
    try:
        # Read the input file
        with open(input_file, 'r') as f:
            try:
                menu_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in {input_file}: {e}")
                return 1
                
        # Print the structure of the input
        print("\n=== Input Structure ===")
        if isinstance(menu_data, dict):
            print(f"Dictionary with keys: {list(menu_data.keys())}")
            if "categories" in menu_data:
                categories = menu_data["categories"]
                print(f"- {len(categories)} categories")
                if categories and len(categories) > 0:
                    print(f"- First category has keys: {list(categories[0].keys())}")
                    if "products" in categories[0]:
                        products = categories[0]["products"]
                        print(f"  - {len(products)} products in first category")
                        if products and len(products) > 0:
                            print(f"  - First product has keys: {list(products[0].keys())}")
        elif isinstance(menu_data, list):
            print(f"List with {len(menu_data)} items")
            if menu_data and len(menu_data) > 0:
                if isinstance(menu_data[0], dict):
                    print(f"- First item has keys: {list(menu_data[0].keys())}")
        else:
            print(f"Unexpected type: {type(menu_data)}")

        # Now process the menu data
        print("\n=== Processing Menu Data ===")
        try:
            processed_menu = process_deliverect_menu(menu_data)
            print(f"Successfully processed menu data")
            print(f"- {len(processed_menu.get('items', []))} items")
            print(f"- {len(processed_menu.get('modifiers', []))} modifiers")
            print(f"- {len(processed_menu.get('modifierGroups', []))} modifier groups")
            print(f"- {len(processed_menu.get('name_variants', {}))} name variants")
            
            # Optional: Print some sample items
            items = processed_menu.get('items', [])
            if items:
                print("\n=== Sample Items ===")
                for i, item in enumerate(items[:5]):  # Print first 5 items
                    print(f"Item {i+1}: {item.get('name')} - {item.get('reference_handler')}")
                    
            # Optional: Validate the processed menu
            print("\n=== Validating Menu ===")
            try:
                validated_menu = validate_and_fix_menu_data(processed_menu)
                print("Menu validation successful")
                
                # Print out changes that were made
                if hasattr(validated_menu, "_fixes"):
                    print("\nFixes applied during validation:")
                    for fix in validated_menu._fixes:
                        print(f"- {fix}")
            except Exception as e:
                print(f"Menu validation error: {e}")
            
            # Save the processed menu to a file
            output_file = f"{os.path.splitext(input_file)[0]}_processed.json"
            with open(output_file, 'w') as f:
                json.dump(processed_menu, f, indent=2)
            print(f"\nProcessed menu saved to {output_file}")
            
            return 0
            
        except Exception as e:
            import traceback
            print(f"Error processing menu data: {e}")
            print(traceback.format_exc())
            return 1
            
    except Exception as e:
        import traceback
        print(f"Unexpected error: {e}")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())