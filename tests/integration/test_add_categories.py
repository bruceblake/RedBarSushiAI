#!/usr/bin/env python3
"""
Script to add categories to menu items based on their names
"""
import json
from app.utils.menu_utils import write_menu_file


def add_categories():
    """Add categories to menu items based on their names"""
    # Load the current menu data
    with open("menu_data.json", "r") as f:
        menu = json.load(f)

    # Category mappings based on keywords in item names
    category_mappings = {
        "burger": "Burgers",
        "steak": "Steak and Burgers",
        "chicken": "Chicken",
        "pizza": "Pizza",
        "poke": "Poke Bowls",
        "bowl": "Poke Bowls",
        "fries": "Sides",
        "rice": "Sides",
        "noodles": "Sides",
        "sate": "Chicken",
        "tenders": "Chicken",
        "coke": "Drinks",
        "cola": "Drinks",
        "diet": "Drinks",
        "ginger beer": "Drinks",
    }

    # Flag to track if we made changes
    changes_made = False

    # Update each item's category if needed
    for item in menu.get("items", []):
        # Skip items that already have a category
        if item.get("category"):
            continue

        # Try to match the item name to a category
        name = item.get("name", "").lower()
        for keyword, category in category_mappings.items():
            if keyword in name:
                item["category"] = category
                print(f"Added category '{category}' to '{item.get('name')}'")
                changes_made = True
                break

    # If the categories were updated, also update the name variants
    if changes_made:
        # Rebuild name variants with better item handling
        name_variants = {}

        for item in menu.get("items", []):
            name = item.get("name", "")
            if not name:
                continue

            # Add the main name (lowercase)
            name_lower = name.lower()
            name_variants[name_lower] = name

            # Add word-level variants
            words = name_lower.split()
            if len(words) > 1:
                # Add the first word if it's meaningful (4+ chars, not an article)
                if len(words[0]) >= 4 and words[0] not in ["with", "and", "the"]:
                    name_variants[words[0]] = name

                # Add the last word if it's meaningful
                if len(words[-1]) >= 4 and words[-1] not in ["with", "and", "the"]:
                    name_variants[words[-1]] = name

                # For burger items, make sure "burger" maps to them
                if "burger" in name_lower and name_lower != "burger":
                    name_variants["burger"] = name

            # Special handling for common items
            if "french fries" in name_lower:
                name_variants["fries"] = name
                name_variants["frys"] = name

            if "chicken burger" in name_lower:
                name_variants["chicken burger"] = name

        # Update the menu with new variants
        menu["name_variants"] = name_variants
        print(f"Updated name variants dictionary with {len(name_variants)} entries")

        # Write back to the file
        success = write_menu_file(menu)
        if success:
            print("Successfully updated menu with categories and name variants")
        else:
            print("Failed to write updated menu")
    else:
        print("No category changes needed")

    return menu


if __name__ == "__main__":
    add_categories()
