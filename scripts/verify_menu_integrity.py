#!/usr/bin/env python
"""
Menu Integrity Verification Tool

This script performs comprehensive validation of menu data, particularly focusing on:
1. Menu structure integrity (required fields, proper nesting)
2. Reference handler uniqueness and validity
3. Price consistency and validity
4. Availability rule validation

Usage:
    python scripts/verify_menu_integrity.py [file_path]

If file_path is not provided, uses standard menu file locations.
"""

import os
import sys
import json
import logging
import argparse
import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("menu-verifier")

# Allow importing app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

try:
    from app.config import MENU_FILE_PATH
except ImportError:
    logger.error("Failed to import required modules. Make sure you're running from the project root.")
    sys.exit(1)

def find_menu_file():
    """Find the menu file in standard locations."""
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

def verify_menu_integrity(file_path):
    """
    Verify the integrity of a menu file.
    
    Checks:
    1. JSON validity
    2. Required keys and structure
    3. Required fields for items
    4. Reference handler uniqueness
    5. Price validity
    6. Availability rule validity
    
    Args:
        file_path: Path to the menu file
        
    Returns:
        tuple: (is_valid, issues)
    """
    issues = []
    
    try:
        # Load the file
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON: {e}")
            return False, issues
            
        # Check top-level structure
        if not isinstance(data, dict):
            issues.append("Menu data is not a dictionary")
            return False, issues
            
        # Check required keys
        for key in ["items", "modifiers", "modifierGroups"]:
            if key not in data:
                issues.append(f"Missing required key: {key}")
        
        # Track reference handlers for uniqueness check
        reference_handlers = {}
        ids = {}
        
        # Validate items
        for i, item in enumerate(data.get("items", [])):
            item_issues = []
            
            # Check required fields
            for field in ["name", "reference_handler"]:
                if not item.get(field):
                    item_issues.append(f"Missing required field: {field}")
            
            # Check price validity
            if "price" not in item or item["price"] is None:
                item_issues.append("Missing price")
            elif not isinstance(item["price"], (int, float)) or item["price"] < 0:
                item_issues.append(f"Invalid price: {item.get('price')}")
                
            # Check reference handler uniqueness
            ref = item.get("reference_handler")
            if ref:
                if ref in reference_handlers:
                    item_issues.append(f"Duplicate reference_handler: {ref} (already used by {reference_handlers[ref]})")
                else:
                    reference_handlers[ref] = item.get("name", f"Item {i}")
            
            # Check ID uniqueness
            item_id = item.get("id") or item.get("_id")
            if item_id:
                if item_id in ids:
                    item_issues.append(f"Duplicate ID: {item_id} (already used by {ids[item_id]})")
                else:
                    ids[item_id] = item.get("name", f"Item {i}")
            
            # Check availability rules
            if "availabilities" in item:
                for j, avail in enumerate(item["availabilities"]):
                    if "dayOfWeek" not in avail:
                        item_issues.append(f"Availability rule {j} missing dayOfWeek")
                    elif not isinstance(avail["dayOfWeek"], int) or avail["dayOfWeek"] < 1 or avail["dayOfWeek"] > 7:
                        item_issues.append(f"Invalid dayOfWeek in availability rule {j}: {avail.get('dayOfWeek')}")
                        
                    # Check time format
                    for time_field in ["startTime", "endTime"]:
                        if time_field in avail:
                            time_str = avail[time_field]
                            try:
                                hours, minutes = map(int, time_str.split(":"))
                                if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                                    item_issues.append(f"Invalid {time_field} in availability rule {j}: {time_str}")
                            except (ValueError, AttributeError):
                                item_issues.append(f"Invalid {time_field} format in availability rule {j}: {time_str}")
            
            # If this item has issues, add them to the list
            if item_issues:
                issues.append(f"Item {i} ({item.get('name', 'unnamed')}): {', '.join(item_issues)}")
        
        # Validate modifier groups
        mod_group_ids = {}
        for i, group in enumerate(data.get("modifierGroups", [])):
            group_issues = []
            
            # Check required fields
            for field in ["id", "name"]:
                if not group.get(field):
                    group_issues.append(f"Missing required field: {field}")
            
            # Check min/max constraints
            if "min" in group and "max" in group:
                if group["min"] > group["max"]:
                    group_issues.append(f"Invalid min/max: {group.get('min')} > {group.get('max')}")
            
            # Check ID uniqueness
            group_id = group.get("id")
            if group_id:
                if group_id in mod_group_ids:
                    group_issues.append(f"Duplicate modifier group ID: {group_id} (already used by {mod_group_ids[group_id]})")
                else:
                    mod_group_ids[group_id] = group.get("name", f"Group {i}")
            
            # If this group has issues, add them to the list
            if group_issues:
                issues.append(f"Modifier Group {i} ({group.get('name', 'unnamed')}): {', '.join(group_issues)}")
        
        # Validate references to modifier groups
        for i, item in enumerate(data.get("items", [])):
            if "modifierGroups" in item:
                item_name = item.get("name", f"Item {i}")
                for group_id in item["modifierGroups"]:
                    if group_id not in mod_group_ids:
                        issues.append(f"Item {item_name} references non-existent modifier group: {group_id}")
        
        # Return validation result
        return len(issues) == 0, issues
    except Exception as e:
        issues.append(f"Error validating menu: {e}")
        return False, issues

def main():
    parser = argparse.ArgumentParser(description="Verify menu data integrity")
    parser.add_argument('file_path', nargs='?', help='Path to the menu file')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    # Find the menu file
    file_path = args.file_path
    if not file_path:
        file_path = find_menu_file()
        if not file_path:
            logger.error("Could not find menu file")
            sys.exit(1)
    
    logger.info(f"Verifying menu integrity: {file_path}")
    
    # Perform verification
    is_valid, issues = verify_menu_integrity(file_path)
    
    # Display results
    if args.json:
        result = {
            "valid": is_valid,
            "issues": issues,
            "file": file_path,
            "timestamp": datetime.datetime.now().isoformat()
        }
        print(json.dumps(result, indent=2))
    else:
        if is_valid:
            logger.info("✅ Menu integrity verified - no issues found")
        else:
            logger.error(f"❌ Menu integrity verification failed - found {len(issues)} issues:")
            for i, issue in enumerate(issues):
                logger.error(f"{i+1}. {issue}")
    
    # Set exit code based on validation result
    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()