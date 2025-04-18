#!/usr/bin/env python3
"""
Script to fix product prices and reference handlers
"""
import json
from app.utils.menu_utils import write_menu_file


def fix_references():
    """Fix prices and reference handlers in the menu"""
    # Load the current menu data
    with open("menu_data.json", "r") as f:
        menu = json.load(f)

    # Update items with proper prices and clean up reference handlers
    for item in menu.get("items", []):
        name = item.get("name", "")
        reference = item.get("reference_handler", "")

        # Fix burger prices
        if "Burger" in name:
            if "Chicken" in name:
                item["price"] = 12.95
            elif "Cheese" in name:
                item["price"] = 11.95
            else:
                item["price"] = 10.95

        # Fix fries prices
        elif "Fries" in name:
            if "French" in name:
                item["price"] = 4.99
            elif "Curly" in name:
                item["price"] = 5.99
            elif "Seasoned" in name:
                item["price"] = 6.99

        # Fix drink prices
        elif "Cola" in name or "Coke" in name:
            item["price"] = 2.99
        elif "Ginger Beer" in name:
            item["price"] = 3.49

        # Fix poke bowl prices
        elif "Poke" in name:
            if "Mini" in name:
                item["price"] = 8.99
            elif "Large" in name:
                item["price"] = 12.99

        # Remove ### codes from reference handlers
        if "###" in reference:
            cleaned_ref = reference.split("###")[0]
            item["reference_handler"] = cleaned_ref
            print(f"Fixed reference for {name}: {reference} → {cleaned_ref}")

    # Also fix modifiers
    for mod in menu.get("modifiers", []):
        reference = mod.get("reference_handler", "")
        # Remove ### codes from reference handlers
        if "###" in reference:
            cleaned_ref = reference.split("###")[0]
            mod["reference_handler"] = cleaned_ref
            print(f"Fixed modifier reference: {reference} → {cleaned_ref}")

    # Write back to the file
    success = write_menu_file(menu)
    if success:
        print("Successfully updated menu with fixed prices and references")
    else:
        print("Failed to write updated menu")

    return menu


if __name__ == "__main__":
    fix_references()
