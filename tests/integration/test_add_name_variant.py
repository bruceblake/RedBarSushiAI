#!/usr/bin/env python3
"""
Script to add a name variant to the menu data
"""
import json
import os
from app.utils.menu_utils import load_menu_data, write_menu_file

def add_name_variant(variant, menu_item):
    """
    Add a new name variant to the menu data
    
    Args:
        variant: The variant name to add (e.g., "chicken burger")
        menu_item: The actual menu item name it should map to (e.g., "Hamburger")
    """
    # Load current menu data
    menu_data = load_menu_data(force_refresh=True)
    
    # Add the variant to name_variants
    if "name_variants" not in menu_data:
        menu_data["name_variants"] = {}
    
    menu_data["name_variants"][variant.lower()] = menu_item
    
    # Write back to file
    success = write_menu_file(menu_data)
    
    if success:
        print(f"Successfully added '{variant}' as a variant for '{menu_item}'")
    else:
        print(f"Failed to update menu data")
    
    return success

if __name__ == "__main__":
    # Add chicken burger as a variant for hamburger
    add_name_variant("chicken burger", "Hamburger")