#!/usr/bin/env python3
"""
Script to convert the new Deliverect menu format to our internal format
"""
import json
from app.utils.menu_utils import write_menu_file


def extract_menu_items():
    """
    Extracts menu items from the JSON data in menu_data.json and creates a properly formatted menu
    """
    # Load the current menu data
    with open("menu_data.json", "r") as f:
        data = json.load(f)

    # Check if it's in the new format (with a single item containing everything)
    if len(data.get("items", [])) == 1 and "products" in data["items"][0]:
        raw_data = data["items"][0]
        categories = raw_data.get("categories", [])
        modifiers = raw_data.get("modifiers", {})
        modifier_groups = raw_data.get("modifierGroups", {})
        products = raw_data.get("products", {})

        print(f"Found {len(categories)} categories")
        print(f"Found {len(modifiers)} modifiers")
        print(f"Found {len(modifier_groups)} modifier groups")
        print(f"Found {len(products)} products")

        # Create the new menu format
        new_menu = {
            "items": [],
            "modifiers": [],
            "modifierGroups": [],
            "name_variants": {},
        }

        # Process all products first
        for product_id, product in products.items():
            # Find the category for this product
            category_name = ""
            for cat in categories:
                if product_id in cat.get("products", []) or product_id in cat.get(
                    "subProducts", []
                ):
                    category_name = cat.get("name", "")
                    break

            # Convert to our internal format
            item = {
                "id": product.get("_id", product_id),
                "name": product.get("name", ""),
                "price": product.get("price", 0),
                "reference_handler": product.get("plu", product.get("referenceId", "")),
                "description": product.get("description", ""),
                "imageUrl": product.get("imageUrl", ""),
                "snoozed": product.get("snoozed", False),
                "category": category_name,
                "available": not product.get("snoozed", False),
            }

            # Add any modifier groups
            if product.get("subProducts"):
                item["modifierGroups"] = product.get("subProducts", [])

            new_menu["items"].append(item)

            # Add to name variants
            name = product.get("name", "").lower()
            if name:
                new_menu["name_variants"][name] = product.get("name", "")

                # Add common word variants
                words = name.split()
                if len(words) > 1:
                    # Add first and last words as variants
                    if len(words[0]) >= 4 and words[0] not in ["with", "and", "the"]:
                        new_menu["name_variants"][words[0]] = product.get("name", "")
                    if len(words[-1]) >= 4 and words[-1] not in ["with", "and", "the"]:
                        new_menu["name_variants"][words[-1]] = product.get("name", "")

        # Process modifier groups
        for group_id, group in modifier_groups.items():
            mg = {
                "id": group.get("_id", group_id),
                "name": group.get("name", ""),
                "minAllowed": group.get("min", 0),
                "maxAllowed": group.get("max", 999),
                "multiMax": group.get("multiMax", 1),
                "modifiers": group.get("subProducts", []),
            }
            new_menu["modifierGroups"].append(mg)

        # Process modifiers
        for mod_id, mod in modifiers.items():
            modifier = {
                "id": mod.get("_id", mod_id),
                "name": mod.get("name", ""),
                "price": mod.get("price", 0),
                "available": not mod.get("snoozed", False),
                "reference_handler": mod.get("plu", ""),
            }
            new_menu["modifiers"].append(modifier)

        # Write the new menu
        success = write_menu_file(new_menu)
        if success:
            print(
                f"Successfully extracted and wrote {len(new_menu['items'])} items to menu_data.json"
            )
        else:
            print("Failed to write new menu data")

        return new_menu
    else:
        print("Menu data is not in the expected format")
        return None


if __name__ == "__main__":
    extract_menu_items()
