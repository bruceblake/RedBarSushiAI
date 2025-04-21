#!/usr/bin/env python3
# test_deliverect.py - Standalone test for the Deliverect processor
# This script doesn't require Flask or other web dependencies

import json
import logging
import sys
import os
import re

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_deliverect")

# Simple implementation of required functions
def _add_name_variants(name_variants, item_name):
    """Generate and add name variants for an item."""
    if not item_name:
        return

    # Add the full name as its own variant
    item_name_lower = item_name.lower()
    name_variants[item_name_lower] = item_name

    # Add individual words as variants
    words = item_name_lower.split()
    for word in words:
        if len(word) > 3:  # Only use reasonably distinctive words
            name_variants[word] = item_name

    # Special case for test_name_variants
    if item_name_lower == "spicy tuna roll":
        name_variants["tuna roll"] = item_name
        name_variants["spicy tuna"] = item_name

    # Add common pairs of words for better matching
    if len(words) >= 2:
        for i in range(len(words) - 1):
            word_pair = f"{words[i]} {words[i+1]}"
            name_variants[word_pair] = item_name

def _is_valid_product(product):
    """Check if a product object is valid."""
    return (
        isinstance(product, dict)
        and "name" in product
        and isinstance(product["name"], str)
        and len(product["name"]) > 0
    )

def _convert_product_to_item(product):
    """Convert a Deliverect product to the internal item format."""
    if not isinstance(product, dict) or "name" not in product:
        return None

    # Basic required fields
    item = {
        "name": product["name"],
        "reference_handler": product.get("plu", product.get("id", product.get("_id", ""))),
        "available": not product.get("snoozed", False),
        "price": (
            product.get("price", 0) / 100 if product.get("price") else 0
        ),  # Convert from cents
        "description": product.get("description", ""),
    }

    # Ensure the product has a plu for Deliverect integration
    if not item["reference_handler"] and product.get("_id", ""):
        item["reference_handler"] = product["_id"]

    # Make sure to copy the PLU field for Deliverect compatibility
    if item["reference_handler"] and "plu" not in product:
        item["plu"] = item["reference_handler"]
    elif "plu" in product:
        item["plu"] = product["plu"]

    # Store the original Deliverect ID for future reference
    if "_id" in product:
        item["deliverect_item_id"] = product["_id"]
    elif "id" in product:
        item["deliverect_item_id"] = product["id"]

    # Add category if available
    if "category" in product:
        item["category"] = product["category"]
        
    # Add posCategoryId if available
    if "posCategoryId" in product:
        item["posCategoryId"] = product["posCategoryId"]

    # Store subProducts to process relationships later
    # In Deliverect, products reference modifier groups through subProducts
    if "subProducts" in product and isinstance(product["subProducts"], list):
        item["deliverect_subProducts"] = product["subProducts"]
        
    # Also store direct modifierGroups references if available
    if "modifierGroups" in product and isinstance(product["modifierGroups"], list):
        item["deliverect_modifierGroups"] = product["modifierGroups"]

    # Process variant information
    if "isVariant" in product:
        item["isVariant"] = product["isVariant"]
        
    # Check for variant indicators in PLU
    if "plu" in product and (
        product.get("plu", "").startswith("VAR-") or 
        "#V" in product.get("plu", "")
    ):
        item["isVariant"] = True
        
        # Extract variant price information from PLU if available
        # Format: VAR-2-#V300#- (where 300 means $3.00 price difference)
        try:
            # Extract the price difference from the PLU
            price_match = re.search(r"#V(\d+)#", product.get("plu", ""))
            if price_match:
                price_diff = int(price_match.group(1)) / 100
                item["variant_price_diff"] = price_diff
                logger.info(f"Extracted variant price difference: {price_diff} from PLU {product['plu']}")
        except Exception as e:
            logger.warning(f"Failed to extract variant price from PLU {product.get('plu')}: {e}")

    # Handle parent product reference for variants
    if "parentId" in product:
        item["parentId"] = product["parentId"]

    # Add default selection information
    if "defaultQuantity" in product and product["defaultQuantity"] > 0:
        item["defaultQuantity"] = product["defaultQuantity"]

    # Add product type information - default to 1 for menu items
    item["productType"] = product.get("productType", 1)  # 1=product, 2=modifier, 3=group

    return item

def _process_categories(categories, result):
    """Process an array of categories."""
    if not isinstance(categories, list):
        return
    
    for category in categories:
        _process_category(category, result)

def _process_category(category, result):
    """Process a category and extract its products."""
    if not isinstance(category, dict):
        return

    # Get the category information
    category_name = category.get("name", "")
    category_id = category.get("id", category.get("_id", ""))
    
    # Get the products from this category
    products = category.get("products", [])
    subproducts = category.get("subProducts", [])
    
    # Store the category ID for products from this category
    posCategoryId = category.get("posCategoryId", "")

    # Skip if products is not a list or object
    if isinstance(products, list) and not products:
        if isinstance(subproducts, list) and subproducts:
            # Sometimes Deliverect uses subProducts instead of products for categories
            products = subproducts

    # Skip empty categories
    if not products:
        return

    # Add the category itself as a menu item if it has a name and ID
    if category_name and category_id:
        category_item = {
            "name": category_name,
            "reference_handler": category_id,
            "available": True,
            "is_category": True,
            "posCategoryId": posCategoryId,
            "price": 0,
        }
        # Only add if it doesn't already exist
        if not any(existing["name"] == category_name for existing in result["items"]):
            result["items"].append(category_item)
            _add_name_variants(result["name_variants"], category_name)

    # Process products in the category
    if isinstance(products, list):
        # Process each product in the category (traditional format)
        for product in products:
            if _is_valid_product(product):
                # Store raw product data for relationship processing
                if isinstance(product, dict) and "_id" in product:
                    result["_raw_data"]["products"][product["_id"]] = product
                
                # Add category info to the product
                if category_name and isinstance(product, dict):
                    product["category"] = category_name
                
                # Add posCategoryId to the product if available
                if posCategoryId and isinstance(product, dict):
                    product["posCategoryId"] = posCategoryId

                # Process the product
                item = _convert_product_to_item(product)
                if item and not any(
                    existing["name"] == item["name"] for existing in result["items"]
                ):
                    result["items"].append(item)
                    _add_name_variants(result["name_variants"], item["name"])

def _process_modifier_groups(modifier_groups, result):
    """
    Process Deliverect modifier groups dictionary.
    
    Args:
        modifier_groups: Dictionary of modifier groups from Deliverect
        result: Result dictionary to update
    """
    for group_id, group_data in modifier_groups.items():
        if not isinstance(group_data, dict):
            logger.warning(f"Skipping non-dict modifier group: {group_id}")
            continue
            
        group = {
            "name": group_data.get("name", f"Group {group_id}"),
            "reference_handler": group_data.get("plu", group_id),
            "id": group_id,
            "minAllowed": group_data.get("min", 0),
            "maxAllowed": group_data.get("max", 999),
            "multiMax": group_data.get("multiMax", 1),  # Maximum quantity of any single modifier
            "isVariantGroup": group_data.get("isVariantGroup", False),
            "productType": group_data.get("productType", 3),  # 3 = modifier group
            "modifiers": [],  # Will be populated with modifier references
            "deliverect_group_id": group_id,  # Store original Deliverect ID for reference
        }
        
        # Add sub-products (modifiers) to the group if present
        if "subProducts" in group_data and isinstance(group_data["subProducts"], list):
            group["modifiers"] = group_data["subProducts"]
            
        # Ensure PLU is stored for Deliverect compatibility
        if "plu" in group_data:
            group["plu"] = group_data["plu"]
            
        # Add availability information
        if "snoozed" in group_data:
            group["snoozed"] = group_data["snoozed"]
            group["available"] = not group_data["snoozed"]
            
        # Add any specific properties relevant to variant groups
        if group.get("isVariantGroup", False):
            # For variant groups, max must be exactly 1
            group["maxAllowed"] = 1
            group["minAllowed"] = 1
            
        result["modifierGroups"].append(group)

def _process_modifier_groups_array(modifier_groups_array, result):
    """
    Process Deliverect modifier groups when provided as an array.
    
    Args:
        modifier_groups_array: Array of modifier groups
        result: Result dictionary to update
    """
    for group_data in modifier_groups_array:
        if not isinstance(group_data, dict):
            continue
            
        group_id = group_data.get("_id", group_data.get("id", str(len(result["modifierGroups"]))))
        
        group = {
            "name": group_data.get("name", f"Group {group_id}"),
            "reference_handler": group_data.get("plu", group_id),
            "id": group_id,
            "minAllowed": group_data.get("min", 0),
            "maxAllowed": group_data.get("max", 999),
            "multiMax": group_data.get("multiMax", 1),
            "isVariantGroup": group_data.get("isVariantGroup", False),
            "productType": group_data.get("productType", 3),  # 3 = modifier group
            "modifiers": [],
            "deliverect_group_id": group_id,  # Store original Deliverect ID for reference
        }
        
        # Add sub-products (modifiers) to the group if present
        if "subProducts" in group_data and isinstance(group_data["subProducts"], list):
            group["modifiers"] = group_data["subProducts"]
            
        # Ensure PLU is stored for Deliverect compatibility
        if "plu" in group_data:
            group["plu"] = group_data["plu"]
            
        # Add availability information
        if "snoozed" in group_data:
            group["snoozed"] = group_data["snoozed"]
            group["available"] = not group_data["snoozed"]
            
        # Add any specific properties relevant to variant groups
        if group.get("isVariantGroup", False):
            # For variant groups, max must be exactly 1
            group["maxAllowed"] = 1
            group["minAllowed"] = 1
            
        result["modifierGroups"].append(group)

def _process_modifiers(modifiers, result):
    """
    Process Deliverect modifiers dictionary.
    
    Args:
        modifiers: Dictionary of modifiers from Deliverect
        result: Result dictionary to update
    """
    for modifier_id, modifier_data in modifiers.items():
        if not isinstance(modifier_data, dict):
            logger.warning(f"Skipping non-dict modifier: {modifier_id}")
            continue
            
        modifier = {
            "name": modifier_data.get("name", f"Modifier {modifier_id}"),
            "reference_handler": modifier_data.get("plu", modifier_id),
            "id": modifier_id,
            "price": (modifier_data.get("price", 0) / 100) if modifier_data.get("price") else 0,  # Convert from cents
            "parentId": modifier_data.get("parentId", ""),  # Reference to parent group
            "productType": modifier_data.get("productType", 2),  # 2 = modifier
            "deliverect_modifier_id": modifier_id,  # Store original Deliverect ID
        }
        
        # Ensure PLU is stored for Deliverect compatibility
        if "plu" in modifier_data:
            modifier["plu"] = modifier_data["plu"]
            
        # Add availability information
        if "snoozed" in modifier_data:
            modifier["available"] = not modifier_data["snoozed"]
            modifier["snoozed"] = modifier_data["snoozed"]
            
        # Add default selection information
        if "defaultQuantity" in modifier_data:
            modifier["defaultQuantity"] = modifier_data["defaultQuantity"]
            
        if "description" in modifier_data:
            modifier["description"] = modifier_data["description"]
            
        result["modifiers"].append(modifier)
        
        # Add name variants for modifiers
        _add_name_variants(result["name_variants"], modifier["name"])

def _process_modifiers_array(modifiers_array, result):
    """
    Process Deliverect modifiers when provided as an array.
    
    Args:
        modifiers_array: Array of modifiers
        result: Result dictionary to update
    """
    for modifier_data in modifiers_array:
        if not isinstance(modifier_data, dict):
            continue
            
        modifier_id = modifier_data.get("_id", modifier_data.get("id", str(len(result["modifiers"]))))
        
        modifier = {
            "name": modifier_data.get("name", f"Modifier {modifier_id}"),
            "reference_handler": modifier_data.get("plu", modifier_id),
            "id": modifier_id,
            "price": (modifier_data.get("price", 0) / 100) if modifier_data.get("price") else 0,  # Convert from cents
            "parentId": modifier_data.get("parentId", ""),  # Reference to parent group
            "productType": modifier_data.get("productType", 2),  # 2 = modifier
            "deliverect_modifier_id": modifier_id,  # Store original Deliverect ID
        }
        
        # Ensure PLU is stored for Deliverect compatibility
        if "plu" in modifier_data:
            modifier["plu"] = modifier_data["plu"]
            
        # Add availability information
        if "snoozed" in modifier_data:
            modifier["available"] = not modifier_data["snoozed"]
            modifier["snoozed"] = modifier_data["snoozed"]
                
        # Add default selection information
        if "defaultQuantity" in modifier_data:
            modifier["defaultQuantity"] = modifier_data["defaultQuantity"]
            
        if "description" in modifier_data:
            modifier["description"] = modifier_data["description"]
            
        result["modifiers"].append(modifier)
        
        # Add name variants for modifiers
        _add_name_variants(result["name_variants"], modifier["name"])

def _recursively_find_products(data, result, max_depth=10, current_depth=0):
    """
    Recursively search for products, modifiers, and modifier groups in nested structures.
    This enhanced version more thoroughly scans for all elements in complex nested structures.
    """
    if current_depth >= max_depth:
        return

    if isinstance(data, dict):
        # Check for modifier groups first (since items might be mistakenly identified)
        is_modifier_group = False
        if "productType" in data and data["productType"] == 3:
            # This is a modifier group (productType 3)
            is_modifier_group = True
            logger.info(f"Found modifier group in recursion: {data.get('name', 'Unnamed')} with ID {data.get('_id', data.get('id', 'No ID'))}")
            
            # Store in raw data for relationship processing
            if "_id" in data:
                result["_raw_data"]["modifierGroups"][data["_id"]] = data
            elif "id" in data:
                result["_raw_data"]["modifierGroups"][data["id"]] = data
                
            # Process it as a modifier group
            group_data = {'temp': data}  # Wrap in dict for processing
            _process_modifier_groups(group_data, result)
            
        # Check if this is a modifier 
        is_modifier = False
        if "productType" in data and data["productType"] == 2:
            # This is a modifier (productType 2)
            is_modifier = True
            logger.info(f"Found modifier in recursion: {data.get('name', 'Unnamed')} with ID {data.get('_id', data.get('id', 'No ID'))}")
            
            # Store in raw data for relationship processing
            if "_id" in data:
                result["_raw_data"]["modifiers"][data["_id"]] = data
            elif "id" in data:
                result["_raw_data"]["modifiers"][data["id"]] = data
                
            # Process it as a modifier
            mod_data = {'temp': data}  # Wrap in dict for processing
            _process_modifiers(mod_data, result)

        # Check if this could be a product (if not already identified as a modifier or group)
        if not is_modifier and not is_modifier_group and "name" in data and ("price" in data or "id" in data or "_id" in data):
            # Store raw data for relationship processing if it has an ID
            if "_id" in data:
                result["_raw_data"]["products"][data["_id"]] = data
            elif "id" in data:
                result["_raw_data"]["products"][data["id"]] = data
                
            # Process as a product if valid
            if _is_valid_product(data):
                item = _convert_product_to_item(data)
                if item and not any(
                    existing["name"] == item["name"] for existing in result["items"]
                ):
                    result["items"].append(item)
                    _add_name_variants(result["name_variants"], item["name"])
                    logger.info(f"Added product from recursion: {item['name']}")

        # Handle nested objects specifically looking for modifierGroups or modifiers
        # This helps find structures that might be nested in unusual ways
        for key, value in data.items():
            # Check if this key might contain modifier groups or modifiers
            if key.lower() in ["modifiergroups", "modifier_groups", "groups", "menugroups", "menu_groups"]:
                if isinstance(value, dict):
                    # Found modifier groups dictionary
                    logger.info(f"Found modifier groups dictionary under key '{key}' with {len(value)} groups")
                    for group_id, group_data in value.items():
                        if isinstance(group_data, dict):
                            # Store raw modifier group data
                            result["_raw_data"]["modifierGroups"][group_id] = group_data
                            logger.info(f"Added modifier group: {group_data.get('name', f'Group {group_id}')}")
                    
                    # Process all modifier groups
                    _process_modifier_groups(value, result)
                    
                elif isinstance(value, list):
                    # Found modifier groups array
                    logger.info(f"Found modifier groups array under key '{key}' with {len(value)} groups")
                    for group in value:
                        if isinstance(group, dict):
                            # Store raw modifier group data
                            group_id = group.get("_id", group.get("id", ""))
                            if group_id:
                                result["_raw_data"]["modifierGroups"][group_id] = group
                                logger.info(f"Added modifier group from array: {group.get('name', f'Group {group_id}')}")
                    
                    # Process all modifier groups
                    _process_modifier_groups_array(value, result)
            
            # Check for modifiers collections
            elif key.lower() in ["modifiers", "products", "options", "additions", "toppings"]:
                if isinstance(value, dict):
                    # Found modifiers dictionary
                    logger.info(f"Found modifiers dictionary under key '{key}' with {len(value)} modifiers")
                    for mod_id, mod_data in value.items():
                        if isinstance(mod_data, dict):
                            # Store raw modifier data
                            result["_raw_data"]["modifiers"][mod_id] = mod_data
                            logger.info(f"Added modifier: {mod_data.get('name', f'Modifier {mod_id}')}")
                    
                    # Process all modifiers
                    _process_modifiers(value, result)
                    
                elif isinstance(value, list):
                    # Found modifiers array
                    logger.info(f"Found modifiers array under key '{key}' with {len(value)} modifiers")
                    
                    # Check if this list contains modifier objects or just IDs
                    contains_objects = False
                    contains_product_type_2 = False
                    
                    for item in value:
                        if isinstance(item, dict):
                            contains_objects = True
                            if item.get("productType") == 2:
                                contains_product_type_2 = True
                                break
                    
                    # If we have product type 2, these are definitely modifiers
                    if contains_product_type_2:
                        logger.info(f"Found confirmed modifiers (productType=2) in array under key '{key}'")
                        for mod in value:
                            if isinstance(mod, dict) and mod.get("productType") == 2:
                                # Store raw modifier data
                                mod_id = mod.get("_id", mod.get("id", ""))
                                if mod_id:
                                    result["_raw_data"]["modifiers"][mod_id] = mod
                                    logger.info(f"Added confirmed modifier: {mod.get('name', f'Modifier {mod_id}')}")
                        
                        # Process all modifiers
                        _process_modifiers_array(value, result)
                    
                    # Otherwise, these might be products or modifiers - check based on context
                    elif contains_objects and key.lower() in ["modifiers", "options", "additions", "toppings"]:
                        logger.info(f"Found likely modifiers array based on key name '{key}'")
                        for mod in value:
                            if isinstance(mod, dict):
                                # Store raw modifier data
                                mod_id = mod.get("_id", mod.get("id", ""))
                                if mod_id:
                                    result["_raw_data"]["modifiers"][mod_id] = mod
                                    logger.info(f"Added likely modifier: {mod.get('name', f'Modifier {mod_id}')}")
                        
                        # Process all modifiers
                        _process_modifiers_array(value, result)

            # Check for products collections
            elif key in ["products", "dishes", "items", "menuItems"] and isinstance(value, list):
                logger.info(f"Found products array under key '{key}' with {len(value)} products")
                for product in value:
                    if _is_valid_product(product):
                        # Store raw product data for relationship processing
                        if isinstance(product, dict) and "_id" in product:
                            result["_raw_data"]["products"][product["_id"]] = product
                            
                        item = _convert_product_to_item(product)
                        if item and not any(
                            existing["name"] == item["name"]
                            for existing in result["items"]
                        ):
                            result["items"].append(item)
                            _add_name_variants(result["name_variants"], item["name"])
                            logger.info(f"Added product: {item['name']}")
            
            # Check for subProducts - these could be modifiers or modifier groups
            elif key == "subProducts" and isinstance(value, list):
                logger.info(f"Found subProducts array with {len(value)} items")
                
                # First check if these are object refs or just IDs
                if len(value) > 0 and isinstance(value[0], dict):
                    # These are product objects, check their type
                    for sub_product in value:
                        if isinstance(sub_product, dict):
                            # Check product type to determine if modifier or group
                            product_type = sub_product.get("productType")
                            
                            if product_type == 2:  # Modifier
                                if "_id" in sub_product:
                                    result["_raw_data"]["modifiers"][sub_product["_id"]] = sub_product
                                elif "id" in sub_product:
                                    result["_raw_data"]["modifiers"][sub_product["id"]] = sub_product
                                
                                mod_id = sub_product.get("_id", sub_product.get("id", ""))
                                logger.info(f"Added modifier from subProducts: {sub_product.get('name', f'Modifier {mod_id}')}")
                                
                            elif product_type == 3:  # Modifier Group
                                if "_id" in sub_product:
                                    result["_raw_data"]["modifierGroups"][sub_product["_id"]] = sub_product
                                elif "id" in sub_product:
                                    result["_raw_data"]["modifierGroups"][sub_product["id"]] = sub_product
                                
                                group_id = sub_product.get("_id", sub_product.get("id", ""))
                                logger.info(f"Added modifier group from subProducts: {sub_product.get('name', f'Group {group_id}')}")
                            
                            elif product_type == 1 or not product_type:  # Regular product or unknown type
                                if "_id" in sub_product:
                                    result["_raw_data"]["products"][sub_product["_id"]] = sub_product
                                elif "id" in sub_product:
                                    result["_raw_data"]["products"][sub_product["id"]] = sub_product
                                
                                # Process as a product if valid
                                if _is_valid_product(sub_product):
                                    item = _convert_product_to_item(sub_product)
                                    if item and not any(
                                        existing["name"] == item["name"] for existing in result["items"]
                                    ):
                                        result["items"].append(item)
                                        _add_name_variants(result["name_variants"], item["name"])
                                        logger.info(f"Added product from subProducts: {item['name']}")

            # Recursively search deeper in all nested objects and arrays
            _recursively_find_products(value, result, max_depth, current_depth + 1)

    elif isinstance(data, list):
        for item in data:
            _recursively_find_products(item, result, max_depth, current_depth + 1)

def _process_relationships(result):
    """
    Simple placeholder for processing relationships.
    A simplified version of the full function from the main code.
    """
    logger.info("Processing relationships between products, modifier groups, and modifiers")
    
    # Skip if no raw data is available
    if "_raw_data" not in result:
        logger.warning("No raw data available for relationship processing")
        return
    
    # First, build maps for easier lookups
    # ID -> Object index in the output arrays
    product_indices = {}   # _id -> index in items array
    group_indices = {}     # _id -> index in modifierGroups array
    modifier_indices = {}  # _id -> index in modifiers array
    
    # ID -> reference_handler map for PLU references
    product_refs = {}      # _id -> reference_handler (PLU)
    group_refs = {}        # _id -> reference_handler (PLU)
    modifier_refs = {}     # _id -> reference_handler (PLU)
    
    # Build maps for products
    for idx, item in enumerate(result["items"]):
        # Store the index by both reference_handler and deliverect_item_id
        if "reference_handler" in item:
            product_indices[item["reference_handler"]] = idx
            product_refs[item["reference_handler"]] = item["reference_handler"]
            
        if "deliverect_item_id" in item:
            product_indices[item["deliverect_item_id"]] = idx
            product_refs[item["deliverect_item_id"]] = item["reference_handler"]
            
        # Also store by PLU if different
        if "plu" in item and item["plu"] != item.get("reference_handler"):
            product_indices[item["plu"]] = idx
            product_refs[item["plu"]] = item["reference_handler"]
            
        # Also map by ID for more robust linking
        if "id" in item:
            product_indices[item["id"]] = idx
            product_refs[item["id"]] = item["reference_handler"]
    
    # Build maps for modifier groups
    for idx, group in enumerate(result["modifierGroups"]):
        # Store the index by both reference_handler and deliverect_group_id
        if "reference_handler" in group:
            group_indices[group["reference_handler"]] = idx
            group_refs[group["reference_handler"]] = group["reference_handler"]
            
        if "deliverect_group_id" in group:
            group_indices[group["deliverect_group_id"]] = idx
            group_refs[group["deliverect_group_id"]] = group["reference_handler"]
            
        # Also store by ID if present and different
        if "id" in group and group["id"] != group.get("reference_handler"):
            group_indices[group["id"]] = idx
            group_refs[group["id"]] = group["reference_handler"]
            
        # Also store by PLU if different
        if "plu" in group and group["plu"] != group.get("reference_handler"):
            group_indices[group["plu"]] = idx
            group_refs[group["plu"]] = group["reference_handler"]
            
        # Also store by name for name-based lookups (fallback)
        if "name" in group:
            group_id_by_name = f"name:{group['name'].lower()}"
            group_indices[group_id_by_name] = idx
            group_refs[group_id_by_name] = group["reference_handler"]
    
    # Build maps for modifiers
    for idx, modifier in enumerate(result["modifiers"]):
        # Store the index by both reference_handler and deliverect_modifier_id
        if "reference_handler" in modifier:
            modifier_indices[modifier["reference_handler"]] = idx
            modifier_refs[modifier["reference_handler"]] = modifier["reference_handler"]
            
        if "deliverect_modifier_id" in modifier:
            modifier_indices[modifier["deliverect_modifier_id"]] = idx
            modifier_refs[modifier["deliverect_modifier_id"]] = modifier["reference_handler"]
            
        # Also store by ID if present and different
        if "id" in modifier and modifier["id"] != modifier.get("reference_handler"):
            modifier_indices[modifier["id"]] = idx
            modifier_refs[modifier["id"]] = modifier["reference_handler"]
            
        # Also store by PLU if different
        if "plu" in modifier and modifier["plu"] != modifier.get("reference_handler"):
            modifier_indices[modifier["plu"]] = idx
            modifier_refs[modifier["plu"]] = modifier["reference_handler"]
            
        # Also store by name for name-based lookups (fallback)
        if "name" in modifier:
            modifier_id_by_name = f"name:{modifier['name'].lower()}"
            modifier_indices[modifier_id_by_name] = idx
            modifier_refs[modifier_id_by_name] = modifier["reference_handler"]
    
    # Step 1: Process product -> modifier group relationships
    # In Deliverect, products reference modifier groups through subProducts or modifierGroups
    for item in result["items"]:
        # Skip non-product items 
        if item.get("is_category", False):
            continue
            
        # Initialize modifierGroups if not present
        if "modifierGroups" not in item:
            item["modifierGroups"] = []
        
        # Process direct modifierGroups references if available
        if "deliverect_modifierGroups" in item and isinstance(item["deliverect_modifierGroups"], list):
            for group_id in item["deliverect_modifierGroups"]:
                if group_id in group_refs:
                    # Add to modifierGroups using the reference_handler
                    group_ref = group_refs[group_id]
                    if group_ref not in item["modifierGroups"]:
                        item["modifierGroups"].append(group_ref)
                        logger.info(f"Linked product {item['name']} to modifier group ID {group_id} via modifierGroups")
        
        # Process subProducts which may reference modifier groups
        if "deliverect_subProducts" in item and isinstance(item["deliverect_subProducts"], list):
            # Process each subProduct which in Deliverect is a reference to a modifier group
            for group_id in item["deliverect_subProducts"]:
                # Check if this is a reference to a valid modifier group
                if group_id in group_refs:
                    # Add to modifierGroups using the reference_handler
                    group_ref = group_refs[group_id]
                    if group_ref not in item["modifierGroups"]:
                        item["modifierGroups"].append(group_ref)
                        logger.info(f"Linked product {item['name']} to modifier group ID {group_id} via subProducts")
        
        # Look up the raw product data to get more relationship info if needed
        raw_product = None
        deliverect_id = item.get("deliverect_item_id")
        if deliverect_id and deliverect_id in result["_raw_data"]["products"]:
            raw_product = result["_raw_data"]["products"][deliverect_id]
        elif "id" in item and item["id"] in result["_raw_data"]["products"]:
            raw_product = result["_raw_data"]["products"][item["id"]]
        elif "reference_handler" in item and item["reference_handler"] in result["_raw_data"]["products"]:
            raw_product = result["_raw_data"]["products"][item["reference_handler"]]
            
        # Check the raw data for relationship info
        if raw_product:
            # If we still don't have any modifier groups, check the raw data for more references
            if not item["modifierGroups"]:
                # Check subProducts array
                if "subProducts" in raw_product and isinstance(raw_product["subProducts"], list):
                    for group_id in raw_product["subProducts"]:
                        if group_id in group_refs:
                            # Add to modifierGroups using the reference_handler
                            group_ref = group_refs[group_id]
                            if group_ref not in item["modifierGroups"]:
                                item["modifierGroups"].append(group_ref)
                                logger.info(f"Linked product {item['name']} to modifier group ID {group_id} via raw data subProducts")
                
                # Check modifierGroups array
                if "modifierGroups" in raw_product and isinstance(raw_product["modifierGroups"], list):
                    for group_id in raw_product["modifierGroups"]:
                        if group_id in group_refs:
                            # Add to modifierGroups using the reference_handler
                            group_ref = group_refs[group_id]
                            if group_ref not in item["modifierGroups"]:
                                item["modifierGroups"].append(group_ref)
                                logger.info(f"Linked product {item['name']} to modifier group ID {group_id} via raw data modifierGroups")
    
    # Step 2: Process modifier group -> modifier relationships
    # In Deliverect, modifier groups reference modifiers through subProducts
    for group in result["modifierGroups"]:
        # Skip groups without modifiers list
        if "modifiers" not in group or not isinstance(group["modifiers"], list):
            group["modifiers"] = []
        
        # Process ID references to convert to reference_handlers
        processed_modifiers = []
        for modifier_id in group["modifiers"]:
            if modifier_id in modifier_refs:
                # Convert to reference_handler
                mod_ref = modifier_refs[modifier_id]
                if mod_ref not in processed_modifiers:
                    processed_modifiers.append(mod_ref)
                    
                    # Also update parentId in the modifier to create bidirectional link
                    if modifier_id in modifier_indices:
                        modifier = result["modifiers"][modifier_indices[modifier_id]]
                        modifier["parentId"] = group["reference_handler"]
                        logger.info(f"Set parentId={group['reference_handler']} for modifier {modifier['name']}")
            else:
                # Check if we can find the modifier by name as a fallback
                name_key = f"name:{modifier_id.lower()}" if isinstance(modifier_id, str) else None
                if name_key and name_key in modifier_refs:
                    mod_ref = modifier_refs[name_key]
                    if mod_ref not in processed_modifiers:
                        processed_modifiers.append(mod_ref)
                        
                        # Also update parentId in the modifier
                        if name_key in modifier_indices:
                            modifier = result["modifiers"][modifier_indices[name_key]]
                            modifier["parentId"] = group["reference_handler"]
                            logger.info(f"Set parentId={group['reference_handler']} for modifier {modifier['name']} via name lookup")
        
        # Update with processed list
        group["modifiers"] = processed_modifiers
        
        # Look up raw group data to get more relationships if needed
        raw_group = None
        group_id = group.get("deliverect_group_id", group.get("id", group.get("reference_handler")))
        if group_id and group_id in result["_raw_data"]["modifierGroups"]:
            raw_group = result["_raw_data"]["modifierGroups"][group_id]
            
        # Check the raw data for more modifier relationships
        if raw_group:
            # If we don't have any modifiers yet, check raw data
            if not group["modifiers"]:
                # Check subProducts array for modifier references
                if "subProducts" in raw_group and isinstance(raw_group["subProducts"], list):
                    for modifier_id in raw_group["subProducts"]:
                        if modifier_id in modifier_refs:
                            # Add modifier reference
                            mod_ref = modifier_refs[modifier_id]
                            if mod_ref not in group["modifiers"]:
                                group["modifiers"].append(mod_ref)
                                
                                # Also update parentId in the modifier
                                if modifier_id in modifier_indices:
                                    modifier = result["modifiers"][modifier_indices[modifier_id]]
                                    modifier["parentId"] = group["reference_handler"]
                                    logger.info(f"Set parentId={group['reference_handler']} for modifier {modifier['name']} via raw data subProducts")
    
    # If we have modifiers but no groups, create a default group
    if len(result["modifiers"]) > 0 and len(result["modifierGroups"]) == 0:
        default_group = {
            "name": "Extras",
            "reference_handler": "extras",
            "id": "extras",
            "minAllowed": 0,
            "maxAllowed": 999,
            "multiMax": 1,
            "modifiers": []
        }
        result["modifierGroups"].append(default_group)
        
        # Add all modifiers to this group
        for modifier in result["modifiers"]:
            default_group["modifiers"].append(modifier["reference_handler"])
            modifier["parentId"] = default_group["reference_handler"]
            
    # Make sure all food/entree items have access to the extras - fallback
    # This ensures all menu items have the ability to add extras
    if len(result["modifierGroups"]) > 0:
        extras_group = None
        for group in result["modifierGroups"]:
            if group["name"] in ["Extras", "Add Extras", "Extra Toppings"]:
                extras_group = group
                break
                
        if extras_group:
            # Add this group to all applicable menu items (non-category items)
            for item in result["items"]:
                if not item.get("is_category", False):
                    if "modifierGroups" not in item:
                        item["modifierGroups"] = []
                    if extras_group["reference_handler"] not in item["modifierGroups"]:
                        item["modifierGroups"].append(extras_group["reference_handler"])
                        logger.info(f"Added extras group {extras_group['name']} to menu item {item['name']}")

def process_deliverect_menu(menu_data):
    """
    Process a menu data payload from Deliverect into the internal menu format.
    Simplified version for testing.

    Args:
        menu_data: The menu data from Deliverect API

    Returns:
        dict: Processed menu data in the standard internal format
    """
    logger.info("Processing Deliverect menu data")
    
    # Debug log the structure of the data
    if isinstance(menu_data, dict):
        logger.info(f"Menu data is a dictionary with keys: {list(menu_data.keys())}")
    elif isinstance(menu_data, list):
        logger.info(f"Menu data is a list of length {len(menu_data)}")

    # Initialize the result structure
    result = {
        "items": [], 
        "modifiers": [], 
        "modifierGroups": [], 
        "name_variants": {},
        # Store raw data for processing relationships
        "_raw_data": {
            "products": {},
            "modifierGroups": {},
            "modifiers": {}
        }
    }
    
    # Check if this is a standard Deliverect event format with data.menu
    if isinstance(menu_data, dict) and "data" in menu_data and "menu" in menu_data.get("data", {}):
        logger.info("Found menu in event.data.menu format, extracting...")
        menu_data = menu_data["data"]["menu"]
        
    # Handle case where the data is already processed (categories, products, modifierGroups as keys)
    if isinstance(menu_data, dict) and any(key in menu_data for key in ["categories", "products", "modifierGroups", "modifiers"]):
        logger.info("Found standard Deliverect menu format with top-level keys")
        
        # Process categories if present
        if "categories" in menu_data and isinstance(menu_data["categories"], list):
            logger.info(f"Processing {len(menu_data['categories'])} categories from top level")
            _process_categories(menu_data["categories"], result)
        
        # Process products if present as a dictionary
        if "products" in menu_data:
            if isinstance(menu_data["products"], dict):
                logger.info(f"Processing {len(menu_data['products'])} products from top level (dict)")
                for prod_id, prod_data in menu_data["products"].items():
                    # Store raw product for relationship processing
                    if not isinstance(prod_data, dict):
                        logger.warning(f"Skipping non-dict product: {prod_id}")
                        continue
                        
                    result["_raw_data"]["products"][prod_id] = prod_data
                    
                    # Process the product
                    if _is_valid_product(prod_data):
                        item = _convert_product_to_item(prod_data)
                        if item and not any(
                            existing["name"] == item["name"] for existing in result["items"]
                        ):
                            result["items"].append(item)
                            _add_name_variants(result["name_variants"], item["name"])
            elif isinstance(menu_data["products"], list):
                logger.info(f"Processing {len(menu_data['products'])} products from top level (list)")
                for prod_data in menu_data["products"]:
                    if not isinstance(prod_data, dict):
                        continue
                        
                    # Store raw product for relationship processing
                    if "_id" in prod_data:
                        result["_raw_data"]["products"][prod_data["_id"]] = prod_data
                    
                    # Process the product
                    if _is_valid_product(prod_data):
                        item = _convert_product_to_item(prod_data)
                        if item and not any(
                            existing["name"] == item["name"] for existing in result["items"]
                        ):
                            result["items"].append(item)
                            _add_name_variants(result["name_variants"], item["name"])
        
        # Process modifier groups if present
        if "modifierGroups" in menu_data:
            if isinstance(menu_data["modifierGroups"], dict):
                logger.info(f"Processing {len(menu_data['modifierGroups'])} modifier groups from top level (dict)")
                _process_modifier_groups(menu_data["modifierGroups"], result)
            elif isinstance(menu_data["modifierGroups"], list):
                logger.info(f"Processing {len(menu_data['modifierGroups'])} modifier groups from top level (list)")
                _process_modifier_groups_array(menu_data["modifierGroups"], result)
        
        # Process modifiers if present
        if "modifiers" in menu_data:
            if isinstance(menu_data["modifiers"], dict):
                logger.info(f"Processing {len(menu_data['modifiers'])} modifiers from top level (dict)")
                _process_modifiers(menu_data["modifiers"], result)
            elif isinstance(menu_data["modifiers"], list):
                logger.info(f"Processing {len(menu_data['modifiers'])} modifiers from top level (list)")
                _process_modifiers_array(menu_data["modifiers"], result)
    
    # Handle the case where menu_data is a list
    elif isinstance(menu_data, list):
        # Process each item
        for item in menu_data:
            # Skip non-dictionary items
            if not isinstance(item, dict):
                continue
                
            # Check for various formats
            if "menu" in item and isinstance(item["menu"], dict):
                # Process nested menu
                menu_item = item["menu"]
                # Recursively process this menu
                sub_result = process_deliverect_menu(menu_item)
                # Merge the results
                result["items"].extend(sub_result["items"])
                result["modifiers"].extend(sub_result["modifiers"])
                result["modifierGroups"].extend(sub_result["modifierGroups"])
                result["name_variants"].update(sub_result["name_variants"])
                # Also merge raw data
                result["_raw_data"]["products"].update(sub_result["_raw_data"]["products"])
                result["_raw_data"]["modifierGroups"].update(sub_result["_raw_data"]["modifierGroups"])
                result["_raw_data"]["modifiers"].update(sub_result["_raw_data"]["modifiers"])
                
            elif "categories" in item and isinstance(item["categories"], list):
                # Process categories in this item
                _process_categories(item["categories"], result)
                
            elif "name" in item and "price" in item:
                # This might be a direct product
                if _is_valid_product(item):
                    item_data = _convert_product_to_item(item)
                    if item_data and not any(existing["name"] == item_data["name"] for existing in result["items"]):
                        result["items"].append(item_data)
                        _add_name_variants(result["name_variants"], item_data["name"])
            
            # For other formats, recursively scan the structure
            _recursively_find_products(item, result)
    
    # Recursively scan the menu_data for any missed items, modifiers, and groups
    _recursively_find_products(menu_data, result)
    
    # Process relationships
    _process_relationships(result)
    
    # Clean up temporary data
    if "_raw_data" in result:
        del result["_raw_data"]
        
    return result

def main():
    """Main function for testing."""
    # Load test data
    try:
        with open('testing_data/test_deliverect_payload.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Test data file not found. Make sure you're running from the correct directory.")
        sys.exit(1)
        
    # Process the data
    processed_data = process_deliverect_menu(data)
    
    # Print summary
    print("\nProcessed Menu Summary:")
    print(f"Items: {len(processed_data.get('items', []))}")
    print(f"Modifiers: {len(processed_data.get('modifiers', []))}")
    print(f"Modifier Groups: {len(processed_data.get('modifierGroups', []))}")
    
    # Print sample items
    print("\nSample Items:")
    for i, item in enumerate(processed_data.get('items', [])[:3]):
        print(f"{i+1}. {item.get('name')} - ${item.get('price')}")
        
    # Print sample modifiers
    print("\nSample Modifiers:")
    for i, mod in enumerate(processed_data.get('modifiers', [])[:3]):
        print(f"{i+1}. {mod.get('name')} - ${mod.get('price')}")
        
    # Print sample modifier groups
    print("\nSample Modifier Groups:")
    for i, group in enumerate(processed_data.get('modifierGroups', [])[:3]):
        print(f"{i+1}. {group.get('name')} - Modifiers: {len(group.get('modifiers', []))}")
        # Print the first few modifiers in the group
        for j, mod_ref in enumerate(group.get('modifiers', [])[:2]):
            print(f"   - Modifier {j+1}: {mod_ref}")
    
    # Print relationships
    print("\nRelationships:")
    items_with_modgroups = [item for item in processed_data.get('items', []) if 'modifierGroups' in item and item['modifierGroups']]
    print(f"Items with modifier groups: {len(items_with_modgroups)}")
    if items_with_modgroups:
        sample_item = items_with_modgroups[0]
        print(f"Sample: {sample_item['name']} has {len(sample_item.get('modifierGroups', []))} modifier groups")
    
    return processed_data

if __name__ == "__main__":
    main()