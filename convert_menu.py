#!/usr/bin/env python3
"""
RedBarSushiAI Menu Conversion Tool

This script handles:
1. Converting Deliverect format menus to our internal format
2. Analyzing menu structure
3. Validating menu data
4. Testing menu loading

Usage:
  python convert_menu.py                  # Convert menu_data.json
  python convert_menu.py --analyze        # Analyze current menu without conversion
  python convert_menu.py --path=FILE.json # Convert a specific file
  python convert_menu.py --test-load      # Test loading the menu in the app format
"""
import json
import os
import sys
import logging
import argparse
from app.utils.menu_utils import (
    process_deliverect_menu, 
    MENU_FILE_PATH, 
    write_menu_file,
    load_menu_data
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s: %(message)s'
)
logger = logging.getLogger(__name__)

def convert_menu_file(file_path=MENU_FILE_PATH, force=False, output_path=None):
    """
    Converts a menu file from Deliverect format to our internal format.
    
    Args:
        file_path: Path to the menu file to convert
        force: Force conversion even if already in correct format
        output_path: Optional path to save the converted file (defaults to input path)
        
    Returns:
        bool: Success status
    """
    try:
        # Load the menu data file
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
            
        # Set output path (default to input path)
        if not output_path:
            output_path = file_path
            
        # Check format and process if needed
        if not force and "items" in menu_data and len(menu_data["items"]) > 0:
            logger.info(f"Menu already in correct format with {len(menu_data['items'])} items")
            return True
            
        # Convert from Deliverect format
        if "categories" in menu_data:
            logger.info(f"Converting Deliverect format with {len(menu_data.get('categories', []))} categories")
            
            # Process the menu
            processed_menu = process_deliverect_menu(menu_data)
            
            # Log stats
            logger.info(f"Conversion result: {len(processed_menu.get('items', []))} items, " + 
                        f"{len(processed_menu.get('modifiers', []))} modifiers, " +
                        f"{len(processed_menu.get('modifierGroups', []))} modifier groups")
            
            # Check for empty items
            if len(processed_menu.get('items', [])) == 0:
                logger.error("Processing resulted in 0 items - check input data!")
                return False
                
            # Write to output file
            logger.info(f"Saving processed menu to {output_path}")
            result = write_menu_file(processed_menu, output_path)
            
            if result:
                logger.info("Menu successfully converted and saved")
                return True
            else:
                logger.error(f"Failed to write converted menu to {output_path}")
                return False
        else:
            logger.error("Input file is not in Deliverect format (no 'categories' found)")
            return False
            
    except FileNotFoundError:
        logger.error(f"Menu file not found at {file_path}")
        return False
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {file_path}")
        return False
    except Exception as e:
        logger.error(f"Error converting menu: {e}")
        return False

def analyze_menu(file_path=MENU_FILE_PATH):
    """Analyze and print details about a menu file"""
    try:
        # Load the menu file
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        print(f"\n=== MENU ANALYSIS: {file_path} ===")
        
        # Determine format
        if "categories" in data:
            print("Format: Deliverect (with categories)")
            category_count = len(data.get("categories", []))
            print(f"Categories: {category_count}")
            
            # Count items
            item_count = 0
            for category in data.get("categories", []):
                item_count += len(category.get("products", []))
            print(f"Total products: {item_count}")
            
            # Modifier groups
            modifier_groups = data.get("modifierGroups", {})
            print(f"Modifier groups: {len(modifier_groups)}")
            
            # Modifiers
            modifiers = data.get("modifiers", {})
            print(f"Modifiers: {len(modifiers)}")
            
            # Sample categories
            if category_count > 0:
                print("\nTop categories:")
                for i, category in enumerate(data.get("categories", [])[:3]):
                    print(f"  - {category.get('name', '')} ({len(category.get('products', []))} products)")
                    
        elif "items" in data:
            print("Format: RedBarSushiAI Internal Format")
            item_count = len(data.get("items", []))
            print(f"Items: {item_count}")
            
            # Count available items
            available = sum(1 for item in data.get("items", []) 
                         if not item.get("snoozed", False) and item.get("available", True))
            print(f"Available items: {available}")
            
            # Modifier info
            print(f"Modifiers: {len(data.get('modifiers', []))}")
            print(f"Modifier groups: {len(data.get('modifierGroups', []))}")
            print(f"Name variants: {len(data.get('name_variants', {}))}")
            
            # Sample items
            if item_count > 0:
                print("\nSample items:")
                for i, item in enumerate(data.get("items", [])[:3]):
                    name = item.get("name", "[No name]")
                    ref = item.get("reference_handler", "[No ref]")
                    price = item.get("price", 0)
                    print(f"  - {name} (${price}) → {ref}")
        else:
            print("Format: Unknown (no categories or items found)")
            print("Top-level keys:", list(data.keys()))
            
        print("\nAnalysis complete.")
        return True
        
    except Exception as e:
        print(f"Error analyzing menu: {e}")
        return False

def test_menu_loading():
    """Test loading the menu through the app's normal loading mechanism"""
    try:
        print("\n=== TESTING MENU LOADING ===")
        
        # Force a refresh to test actual loading
        menu_data = load_menu_data(force_refresh=True)
        
        # Print results
        print(f"Menu loaded successfully from {MENU_FILE_PATH}")
        print(f"Items: {len(menu_data.get('items', []))}")
        print(f"Modifiers: {len(menu_data.get('modifiers', []))}")
        print(f"Modifier groups: {len(menu_data.get('modifierGroups', []))}")
        print(f"Name variants: {len(menu_data.get('name_variants', {}))}")
        
        # Check for available items
        available_items = [
            item for item in menu_data.get('items', [])
            if not item.get("snoozed", False) and item.get("available", True)
        ]
        print(f"Available (not snoozed) items: {len(available_items)}")
        
        # Print sample items
        if available_items:
            print("\nSample available items:")
            for item in available_items[:3]:
                print(f"  - {item.get('name')} (${item.get('price', 0):.2f})")
                
        if not available_items:
            print("\nWARNING: No available items found. The menu would show as unavailable.")
        else:
            print("\nMenu loading test PASSED.")
            
        return True
    except Exception as e:
        print(f"Error testing menu loading: {e}")
        return False

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="RedBarSushiAI Menu Conversion Tool")
    parser.add_argument("--path", help="Path to the menu file to convert")
    parser.add_argument("--output", help="Path to save the converted menu file")
    parser.add_argument("--force", action="store_true", help="Force conversion even if already in correct format")
    parser.add_argument("--analyze", action="store_true", help="Analyze menu structure without conversion")
    parser.add_argument("--test-load", action="store_true", help="Test loading the menu through the app")
    
    args = parser.parse_args()
    
    # Use provided path or default
    file_path = args.path if args.path else MENU_FILE_PATH
    
    # Show file path being used
    print(f"Using menu file: {file_path}")
    
    # Perform requested action
    if args.analyze:
        analyze_menu(file_path)
    elif args.test_load:
        test_menu_loading()
    else:
        # Default action is to convert
        success = convert_menu_file(file_path, args.force, args.output)
        if success:
            print("\nSUCCESS: Menu converted successfully!")
        else:
            print("\nFAILED: Menu conversion unsuccessful")
            sys.exit(1)