#!/usr/bin/env python
"""
Menu Standardization Tool for Deliverect Integration

This script prepares a menu for Deliverect integration by:
1. Ensuring all items have consistent IDs and reference handlers
2. Standardizing price formats
3. Adding required fields to meet Deliverect requirements
4. Correcting invalid modifier group constraints

Usage:
  python scripts/standardize_menu.py [file_path] [--output OUTPUT]

If file_path is not provided, uses the default menu file.
"""

import os
import sys
import json
import logging
import argparse
import datetime
import hashlib
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("menu-standardizer")

# Allow importing app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

try:
    from app.config import MENU_FILE_PATH
    from app.utils.helpers import generate_consistent_reference_id
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

def standardize_menu(menu_data):
    """
    Standardize menu data for Deliverect integration.
    
    Args:
        menu_data: The menu data to standardize
        
    Returns:
        dict: Standardized menu data
    """
    # Create a copy to avoid modifying the original
    standardized = menu_data.copy()
    
    # Track used reference handlers to ensure uniqueness
    used_refs = set()
    used_ids = set()
    
    # Fix item IDs and reference handlers
    for item in standardized.get("items", []):
        # Ensure item has a name
        if not item.get("name"):
            logger.warning(f"Item without name found, skipping: {item}")
            continue
            
        item_name = item["name"]
        
        # Standardize ID format
        if not item.get("id"):
            if item.get("_id"):
                # Use _id if available
                item["id"] = item["_id"]
            else:
                # Generate consistent ID
                item["id"] = f"ITEM-{hashlib.md5(item_name.encode()).hexdigest()[:8]}"
        
        # Ensure ID is unique
        while item["id"] in used_ids:
            item["id"] = f"{item['id']}-{len(used_ids) % 100}"
        used_ids.add(item["id"])
        
        # Standardize reference handler format
        if not item.get("reference_handler"):
            # Generate reference handler from name
            item["reference_handler"] = generate_consistent_reference_id(item_name)
            
        # Ensure reference handler is unique
        while item["reference_handler"] in used_refs:
            item["reference_handler"] = f"{item['reference_handler']}-{len(used_refs) % 100}"
        used_refs.add(item["reference_handler"])
        
        # Ensure description exists
        if "description" not in item:
            item["description"] = ""
            
        # Ensure price is valid
        if not isinstance(item.get("price"), (int, float)) or item.get("price") is None:
            item["price"] = 0.0
            logger.warning(f"Fixed invalid price for {item_name}")
            
        # Add required fields for Deliverect
        item["available"] = not item.get("snoozed", False)
        if "category" not in item:
            item["category"] = "Uncategorized"
            
        # Add creation and modification timestamps if missing
        now = datetime.datetime.now().isoformat()
        if "createdAt" not in item:
            item["createdAt"] = now
        if "updatedAt" not in item:
            item["updatedAt"] = now
    
    # Fix modifier groups
    group_ids = set()
    for group in standardized.get("modifierGroups", []):
        # Ensure group has name and ID
        if not group.get("name"):
            logger.warning(f"Modifier group without name found, skipping: {group}")
            continue
            
        if not group.get("id"):
            group["id"] = f"MG-{hashlib.md5(group['name'].encode()).hexdigest()[:8]}"
            
        # Ensure ID is unique
        while group["id"] in group_ids:
            group["id"] = f"{group['id']}-{len(group_ids) % 100}"
        group_ids.add(group["id"])
        
        # Fix min/max constraints
        min_val = group.get("min", group.get("minAllowed", 0))
        max_val = group.get("max", group.get("maxAllowed", 999))
        
        # Ensure min <= max
        if min_val > max_val:
            logger.warning(f"Fixed invalid constraint min > max for group {group['name']}: {min_val} > {max_val}, setting min = max")
            min_val = max_val
            
        # Standardize constraint names
        group["min"] = min_val
        group["max"] = max_val
        group["minAllowed"] = min_val
        group["maxAllowed"] = max_val
    
    # Add version and last update information
    standardized["version"] = standardized.get("version", 1) + 1
    standardized["lastUpdate"] = datetime.datetime.now().isoformat()
    standardized["standardizedForDeliverect"] = True
    
    return standardized

def convert_to_deliverect_format(menu_data):
    """
    Converts standard menu format to Deliverect-compatible format.
    
    Args:
        menu_data: Standardized menu data
        
    Returns:
        dict: Deliverect-compatible menu data
    """
    deliverect_menu = {
        "categories": []
    }
    
    # Group items by category
    categories = {}
    for item in menu_data.get("items", []):
        category = item.get("category", "Uncategorized")
        if category not in categories:
            categories[category] = {
                "id": f"CAT-{hashlib.md5(category.encode()).hexdigest()[:8]}",
                "name": category,
                "products": []
            }
        
        # Convert item to Deliverect product format
        product = {
            "id": item.get("id", f"ITEM-{hashlib.md5(item.get('name', '').encode()).hexdigest()[:8]}"),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "price": int(float(item.get("price", 0)) * 100),  # Convert to cents
            "plu": item.get("reference_handler", ""),
            "available": not item.get("snoozed", False),
            "imageUrl": item.get("imageUrl", "")
        }
        
        # Add modifierGroups if present
        if "modifierGroups" in item:
            product["modifierGroups"] = []
            for group_id in item["modifierGroups"]:
                group = next((g for g in menu_data.get("modifierGroups", []) if g.get("id") == group_id), None)
                if group:
                    product["modifierGroups"].append({
                        "id": group["id"],
                        "name": group.get("name", ""),
                        "minAmount": group.get("min", 0),
                        "maxAmount": group.get("max", 999),
                        "modifiers": [
                            {
                                "id": m.get("id", f"MOD-{hashlib.md5((m.get('name', '') + group['id']).encode()).hexdigest()[:8]}"),
                                "name": m.get("name", ""),
                                "price": int(float(m.get("price", 0)) * 100),  # Convert to cents
                                "plu": m.get("reference_handler", ""),
                                "available": not m.get("snoozed", False)
                            }
                            for m in group.get("modifiers", [])
                        ]
                    })
        
        categories[category]["products"].append(product)
    
    # Add all categories to the result
    for category_name, category_data in categories.items():
        deliverect_menu["categories"].append(category_data)
    
    return deliverect_menu

def main():
    parser = argparse.ArgumentParser(description="Standardize menu for Deliverect integration")
    parser.add_argument('file_path', nargs='?', help='Path to the menu file')
    parser.add_argument('--output', help='Output path for standardized menu (defaults to input path with _standardized suffix)')
    parser.add_argument('--deliverect', action='store_true', help='Also output Deliverect format')
    
    args = parser.parse_args()
    
    # Find menu file
    file_path = args.file_path
    if not file_path:
        file_path = find_menu_file()
        if not file_path:
            logger.error("Could not find menu file")
            sys.exit(1)
    
    # Set output path
    output_path = args.output
    if not output_path:
        base, ext = os.path.splitext(file_path)
        output_path = f"{base}_standardized{ext}"
    
    # Set deliverect output path
    deliverect_path = None
    if args.deliverect:
        base, ext = os.path.splitext(output_path)
        deliverect_path = f"{base}_deliverect{ext}"
    
    # Load menu data
    logger.info(f"Standardizing menu file: {file_path}")
    try:
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading menu file: {e}")
        sys.exit(1)
    
    # Standardize menu
    standardized_menu = standardize_menu(menu_data)
    
    # Save standardized menu
    try:
        with open(output_path, 'w') as f:
            json.dump(standardized_menu, f, indent=2)
        logger.info(f"Standardized menu saved to: {output_path}")
    except Exception as e:
        logger.error(f"Error saving standardized menu: {e}")
        sys.exit(1)
    
    # Convert to Deliverect format if requested
    if args.deliverect:
        deliverect_menu = convert_to_deliverect_format(standardized_menu)
        try:
            with open(deliverect_path, 'w') as f:
                json.dump(deliverect_menu, f, indent=2)
            logger.info(f"Deliverect format menu saved to: {deliverect_path}")
        except Exception as e:
            logger.error(f"Error saving Deliverect format menu: {e}")
            sys.exit(1)
    
    # Print summary
    logger.info(f"Menu standardization complete.")
    logger.info(f"Items: {len(standardized_menu.get('items', []))}")
    logger.info(f"Modifier groups: {len(standardized_menu.get('modifierGroups', []))}")
    
    # Validate the result
    from subprocess import run
    logger.info("Validating standardized menu...")
    result = run(["python", os.path.join(script_dir, "verify_menu_integrity.py"), output_path])
    if result.returncode == 0:
        logger.info("✅ Validation successful")
    else:
        logger.warning("⚠️ Validation found issues. Run verify_menu_integrity.py for details.")

if __name__ == "__main__":
    main()