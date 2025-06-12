# app/utils/deliverect/menu_async.py
"""
Menu processing module for the Deliverect API (async version).

This module provides async functions for processing menu data from Deliverect.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def process_deliverect_menu_async(menu_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a menu data payload from Deliverect into the internal menu format (async version).

    This function handles various formats of Deliverect menu data, including:
    - Lists of items with nested categories
    - Flattened lists of products
    - Menu data with modifiers and modifier groups

    Args:
        menu_data: Raw menu data from Deliverect API

    Returns:
        Processed menu data in internal format
    """
    logger.info("Processing Deliverect menu data")

    processed = {"items": [], "modifierGroups": [], "categories": []}

    # Create a mapping of category IDs to names for quick lookup
    category_map = {}

    # Extract categories
    if "categories" in menu_data:
        for category in menu_data["categories"]:
            cat_id = category.get("_id", "")
            cat_data = {
                "name": category.get("name", ""),
                "deliverect_category_id": cat_id,
                "description": category.get("description", ""),
                "sub_products": category.get(
                    "subProducts", []
                ),  # Order of products in category
            }
            processed["categories"].append(cat_data)
            category_map[cat_id] = category.get("name", "")

    # First pass: Process all modifiers
    modifier_map = {}
    if "modifiers" in menu_data:
        for modifier_id, modifier in menu_data["modifiers"].items():
            # Check if this is actually a modifier (productType = 2)
            if modifier.get("productType") == 2:
                modifier_map[modifier_id] = {
                    "name": modifier.get("name", ""),
                    "price_change": float(modifier.get("price", 0))
                    / 100,  # Convert cents to dollars
                    "plu": modifier.get("plu", ""),
                    "deliverect_modifier_id": modifier.get("_id", modifier_id),
                    "is_available": modifier.get("visible", True)
                    and not modifier.get("snoozed", False),
                }

    # Second pass: Process modifier groups
    modifier_group_map = {}
    if "modifierGroups" in menu_data:
        for group_id, group in menu_data["modifierGroups"].items():
            # Check if this is actually a modifier group (productType = 3)
            if group.get("productType") == 3:
                group_data = {
                    "name": group.get("name", ""),
                    "min_selection": group.get("min", 0),
                    "max_selection": group.get("max", 1),
                    "multi_max": group.get("multiMax", 1),
                    "deliverect_group_id": group.get("_id", group_id),
                    "plu": group.get("plu", ""),
                    "is_variant_group": group.get("isVariantGroup", False),
                    "modifiers": [],
                }

                # Add modifiers from subProducts
                for sub_product_id in group.get("subProducts", []):
                    if sub_product_id in modifier_map:
                        group_data["modifiers"].append(modifier_map[sub_product_id])

                modifier_group_map[group_id] = group_data
                processed["modifierGroups"].append(group_data)

    # Third pass: Process products
    if "products" in menu_data:
        for product_id, product in menu_data["products"].items():
            # Check if this is actually a product (productType = 1)
            if product.get("productType") != 1:
                continue

            # Skip if product is not visible or is snoozed
            if not product.get("visible", True) or product.get("snoozed", False):
                continue

            # Find which categories this product belongs to
            product_categories = []
            for cat in processed["categories"]:
                if product_id in cat["sub_products"]:
                    product_categories.append(
                        {"name": cat["name"], "id": cat["deliverect_category_id"]}
                    )

            # Use first category as primary category
            category_name = ""
            category_id = ""
            if product_categories:
                category_name = product_categories[0]["name"]
                category_id = product_categories[0]["id"]

            item_data = {
                "name": product.get("name", ""),
                "description": product.get("description", ""),
                "price": float(product.get("price", 0))
                / 100,  # Convert cents to dollars
                "plu": product.get("plu", ""),
                "reference_id": product.get(
                    "referenceId", ""
                ),  # Original PLU if different
                "deliverect_item_id": product.get("_id", product_id),
                "category_name": category_name,
                "category_id": category_id,
                "is_available": product.get("visible", True)
                and not product.get("snoozed", False),
                "is_combo": product.get("isCombo", False),
                "is_variant": product.get("isVariant", False),
                "image_url": product.get("imageUrl", ""),
                "delivery_tax": product.get("deliveryTax", 0)
                / 1000,  # Convert to percentage
                "takeaway_tax": product.get("takeawayTax", 0)
                / 1000,  # Convert to percentage
                "eat_in_tax": product.get("eatInTax", 0)
                / 1000,  # Convert to percentage
                "multi_max": product.get("multiMax"),  # Max quantity per order
                "modifier_groups": [],
            }

            # Add nutritional info if present
            if "calories" in product:
                item_data["calories"] = product.get("calories")
                item_data["calories_range_high"] = product.get("caloriesRangeHigh")

            # Process modifier groups for this product
            for mod_group_id in product.get("subProducts", []):
                if mod_group_id in modifier_group_map:
                    item_data["modifier_groups"].append(
                        modifier_group_map[mod_group_id]
                    )

            processed["items"].append(item_data)

    # Process snoozed products
    processed["snoozed_products"] = []
    if "snoozedProducts" in menu_data:
        for _, snooze_data in menu_data[
            "snoozedProducts"
        ].items():  # snooze_key renamed to _
            processed["snoozed_products"].append(
                {
                    "plu": snooze_data.get("plu", ""),
                    "name": snooze_data.get("name", ""),
                    "snooze_start": snooze_data.get("snoozeStart", ""),
                    "snooze_end": snooze_data.get("snoozeEnd", ""),
                }
            )

    logger.info(
        f"Processed {len(processed['items'])} items, "
        f"{len(processed['modifierGroups'])} modifier groups, "
        f"{len(processed['categories'])} categories"
    )

    return processed
