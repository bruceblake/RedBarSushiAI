#!/usr/bin/env python
"""
Menu validation and repair tool.

This script performs comprehensive validation and repair of menu data files.
It can be run as a standalone script to check and fix menu files.

Usage:
  python scripts/fix_menu.py [file_path]

If file_path is not provided, it will try to find the menu file in the standard locations.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("menu-fixer")

# Add the parent directory to sys.path to allow importing app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

try:
    from app.utils.menu_validator import validate_and_fix_menu_data
    from app.utils.menu_utils import write_menu_file
    from app.config import MENU_FILE_PATH
except ImportError:
    logger.error("Failed to import required modules. Make sure you're running from the project root.")
    sys.exit(1)

def find_menu_file():
    """
    Find the menu file in standard locations.
    Returns the path to the menu file, or None if not found.
    """
    # Try standard locations
    potential_paths = [
        MENU_FILE_PATH,
        "menu_data.json",
        "redbar_menu_data.json",
        os.path.join(parent_dir, "menu_data.json"),
        os.path.join(parent_dir, "redbar_menu_data.json")
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            return path
    
    return None

def validate_menu_file(file_path):
    """
    Validate and fix a menu file.
    
    Args:
        file_path: Path to the menu file
        
    Returns:
        tuple: (success, message, fixed_data)
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}", None
            
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Check if file is empty
        if not content.strip():
            return False, f"File is empty: {file_path}", None
            
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}", None
        
        # Verify it's a dict
        if not isinstance(data, dict):
            return False, "Menu data is not a dictionary", None
            
        # Check required keys
        for key in ["items", "modifiers", "modifierGroups"]:
            if key not in data:
                logger.warning(f"Missing required key: {key}")
        
        # Verify items have required fields
        if "items" in data:
            items_missing_required = []
            for i, item in enumerate(data["items"]):
                missing = []
                if not item.get("name"):
                    missing.append("name")
                if not item.get("reference_handler"):
                    missing.append("reference_handler")
                if "price" not in item or item["price"] is None:
                    missing.append("price")
                if missing:
                    items_missing_required.append(f"Item {i} ({item.get('name', 'unnamed')}): missing {', '.join(missing)}")
                    
            if items_missing_required:
                logger.warning(f"Found {len(items_missing_required)} items with missing required fields")
                for msg in items_missing_required[:10]:  # Log first 10
                    logger.warning(msg)
        
        # Validate and fix
        fixed_data = validate_and_fix_menu_data(data)
        
        # Verify fixed data has all required fields
        validation_failed = False
        for i, item in enumerate(fixed_data.get("items", [])):
            if not item.get("name") or not item.get("reference_handler") or "price" not in item:
                logger.error(f"Validation failed to fix item {i}: {item}")
                validation_failed = True
                
        if validation_failed:
            return False, "Validation failed to fix all items", fixed_data
            
        return True, f"Successfully validated menu with {len(fixed_data.get('items', []))} items", fixed_data
    except Exception as e:
        return False, f"Error validating menu: {e}", None

def main():
    parser = argparse.ArgumentParser(description="Validate and fix a menu file")
    parser.add_argument('file_path', nargs='?', help='Path to the menu file')
    parser.add_argument('--fix', action='store_true', help='Fix issues and write back to file')
    parser.add_argument('--backup', action='store_true', help='Create a backup before fixing')
    
    args = parser.parse_args()
    
    # Find the menu file
    file_path = args.file_path
    if not file_path:
        file_path = find_menu_file()
        if not file_path:
            logger.error("Could not find menu file")
            sys.exit(1)
            
    logger.info(f"Validating menu file: {file_path}")
    
    # Validate
    success, message, fixed_data = validate_menu_file(file_path)
    
    if success:
        logger.info(f"Validation successful: {message}")
        
        # Display some stats
        if fixed_data:
            logger.info(f"Menu stats:")
            logger.info(f"  Items: {len(fixed_data.get('items', []))}")
            logger.info(f"  Modifier groups: {len(fixed_data.get('modifierGroups', []))}")
            logger.info(f"  Modifiers: {len(fixed_data.get('modifiers', []))}")
            
        # Fix if requested
        if args.fix and fixed_data:
            # Create backup
            if args.backup:
                import datetime
                backup_path = f"{file_path}.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to create backup: {e}")
            
            # Write fixed data
            try:
                with open(file_path, 'w') as f:
                    json.dump(fixed_data, f, indent=2)
                logger.info(f"Successfully wrote fixed menu to {file_path}")
            except Exception as e:
                logger.error(f"Failed to write fixed menu: {e}")
                sys.exit(1)
    else:
        logger.error(f"Validation failed: {message}")
        
        if args.fix and fixed_data:
            logger.info("Attempting to fix issues...")
            
            # Create backup
            if args.backup:
                import datetime
                backup_path = f"{file_path}.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to create backup: {e}")
            
            # Write fixed data
            try:
                with open(file_path, 'w') as f:
                    json.dump(fixed_data, f, indent=2)
                logger.info(f"Successfully wrote fixed menu to {file_path}")
            except Exception as e:
                logger.error(f"Failed to write fixed menu: {e}")
                sys.exit(1)
        else:
            sys.exit(1)
        
if __name__ == "__main__":
    main()