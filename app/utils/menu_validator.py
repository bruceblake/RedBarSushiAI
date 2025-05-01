# app/utils/menu_validator.py
"""
Utility functions for validating and fixing menu data before it's saved.
This ensures consistent PLU and price handling throughout the application.
"""

import logging

logger = logging.getLogger(__name__)


def validate_and_fix_menu_data(menu_data):
    """
    Validates and fixes issues in menu data before it's saved.
    This function enforces strict validation for Deliverect integration.
    
    IMPORTANT: This validator uses DATABASE VALUES for validation when available. 
    For empty database scenarios (first-run), it will attempt to extract pricing 
    information from the source data itself, without using any hardcoded values:
    
    Empty DB Strategy:
    1. Use raw_price from original data if available
    2. Convert prices in cents format to dollars if detected
    3. For variants, find and use the base product price from the same data set
    4. Allow zero prices for variant containers (per Deliverect spec)
    5. Fail validation if no valid price source is available
    
    Supports the official Deliverect menu format including:
    - Menu structure with categories, products, modifiers, and modifierGroups
    - Required fields: menu, menuId, menuType, channelLinkId
    - Product fields: _id, plu, name, price, productType, taxes, availability
    - Modifier fields: _id, plu, name, price, productType
    - ModifierGroup fields: _id, min, max, multiMax, subProducts
    
    Handles various error conditions including:
    - String values in modifier groups and other data
    - Non-string values in name fields
    - Missing or invalid structure fields
    - Improperly formatted prices, references, IDs
    - Special case: First-time initialization with empty database

    Args:
        menu_data: Dict containing Deliverect-compatible menu data with items, modifiers, etc.

    Returns:
        dict: Fixed menu data compatible with the Deliverect format

    Raises:
        ValueError: If menu items are missing required fields or cannot be validated 
                   against the database, and no valid price data can be extracted 
                   from the source data itself.
    """
    # Make sure we have valid input data
    if menu_data is None:
        logger.warning("[MENU-FIX] Menu data is None, creating empty structure")
        menu_data = {}

    # Make sure we have the expected structure
    if not isinstance(menu_data, dict):
        # Check if it's a list of menu items (Deliverect can send this format)
        if isinstance(menu_data, list) and len(menu_data) > 0:
            # If first item is a dictionary with categories, use that
            if isinstance(menu_data[0], dict) and "categories" in menu_data[0]:
                logger.warning(
                    "[MENU-FIX] Menu data is a list with categories in first item, using first item"
                )
                menu_data = menu_data[0]
            # Otherwise, treat the list as menu items
            elif isinstance(menu_data[0], dict):
                logger.warning(
                    "[MENU-FIX] Menu data is a list, converting to dictionary structure"
                )
                # Filter out non-dictionary items
                valid_items = [item for item in menu_data if isinstance(item, dict)]
                temp_data = {
                    "items": valid_items,
                    "modifiers": [],
                    "modifierGroups": [],
                }
                menu_data = temp_data
            else:
                logger.warning(
                    "[MENU-FIX] Menu data is a list of non-dictionaries, creating empty structure"
                )
                menu_data = {}
        else:
            logger.warning(
                f"[MENU-FIX] Menu data is not a dictionary: {type(menu_data)}, creating empty structure"
            )
            menu_data = {}
    
    # Check for Deliverect format with data.menu structure
    if isinstance(menu_data, dict) and "data" in menu_data and isinstance(menu_data["data"], dict) and "menu" in menu_data["data"]:
        logger.info("[MENU-FORMAT] Detected Deliverect webhook menu format with data.menu structure")
        menu_data = menu_data["data"]["menu"]
    
    # Check for Deliverect async update format with body.menus structure
    elif isinstance(menu_data, dict) and "body" in menu_data and isinstance(menu_data["body"], dict) and "menus" in menu_data["body"]:
        logger.info("[MENU-FORMAT] Detected Deliverect async menu format with body.menus structure")
        # Use the first menu in the menus array
        if isinstance(menu_data["body"]["menus"], list) and len(menu_data["body"]["menus"]) > 0:
            menu_data = menu_data["body"]["menus"][0]
        else:
            logger.error("[MENU-FORMAT] Empty menus array in Deliverect async format")
            raise ValueError("Empty menus array in Deliverect async format")

    # Check for Deliverect categories format and convert to our internal format
    if "categories" in menu_data and isinstance(menu_data["categories"], list):
        logger.info("[MENU-FORMAT] Detected Deliverect categories format, converting to internal structure")
        
        # Create lists for our internal format
        all_items = []
        
        # Process each category and extract products
        for category in menu_data["categories"]:
            if not isinstance(category, dict):
                continue
                
            # Check for products list
            category_products = []
            
            # Try to find products using various field names that might be present
            if "products" in category and isinstance(category["products"], list):
                category_products = category["products"]
            elif "subProducts" in category and isinstance(category["subProducts"], list):
                # If subProducts contains IDs, we need to look them up in the main product list
                product_ids = category["subProducts"]
                
                # We may have a mapping of products by ID
                if "products" in menu_data and isinstance(menu_data["products"], dict):
                    category_products = [
                        menu_data["products"].get(product_id, {"id": product_id})
                        for product_id in product_ids
                        if isinstance(product_id, str)
                    ]
            
            # Add category info to each product and collect
            for product in category_products:
                if isinstance(product, dict):
                    # Add category information to the product
                    product["category_id"] = category.get("_id") or category.get("id", "")
                    product["category_name"] = category.get("name", "")
                    
                    # Mark item as a category if it appears to be one
                    if (product.get("productType") == 3 or 
                        "subProducts" in product or 
                        "subCategories" in product):
                        product["is_category"] = True
                        
                    # Add each product to our items list
                    all_items.append(product)
        
        # If we extracted products from categories, use them as our items
        if all_items:
            logger.info(f"[MENU-FORMAT] Extracted {len(all_items)} products from {len(menu_data['categories'])} categories")
            menu_data["items"] = all_items
    
    # Handle case where menu data has products but not items
    elif "products" in menu_data and isinstance(menu_data["products"], (list, dict)) and "items" not in menu_data:
        logger.info("[MENU-FORMAT] Converting products to items format")
        
        if isinstance(menu_data["products"], list):
            menu_data["items"] = menu_data["products"]
        elif isinstance(menu_data["products"], dict):
            # Convert dictionary of products to list
            menu_data["items"] = list(menu_data["products"].values())
    
    # Ensure required keys exist with proper types
    if "items" not in menu_data or not isinstance(menu_data["items"], list):
        logger.warning(
            f"[MENU-FIX] items is not a valid list: {type(menu_data.get('items', None))}"
        )
        menu_data["items"] = []
    else:
        # Filter out non-dictionary items
        valid_items = []
        for i, item in enumerate(menu_data["items"]):
            if isinstance(item, dict):
                valid_items.append(item)
            else:
                logger.warning(
                    f"[MENU-FIX] Removed non-dictionary item at index {i}: {type(item)}"
                )
        menu_data["items"] = valid_items

    # Process modifiers from Deliverect format if needed
    if isinstance(menu_data.get("modifiers"), dict):
        logger.info("[MENU-FORMAT] Converting Deliverect modifiers dictionary to list")
        menu_data["modifiers"] = list(menu_data["modifiers"].values())
    
    # Ensure modifiers list exists and is valid
    if "modifiers" not in menu_data or not isinstance(menu_data["modifiers"], list):
        logger.warning(
            f"[MENU-FIX] modifiers is not a valid list: {type(menu_data.get('modifiers', None))}"
        )
        menu_data["modifiers"] = []
    else:
        # Filter out non-dictionary modifiers
        valid_modifiers = []
        for i, mod in enumerate(menu_data["modifiers"]):
            if isinstance(mod, dict):
                # Convert Deliverect modifier properties to our expected format
                if "min" in mod and "minAllowed" not in mod:
                    mod["minAllowed"] = mod["min"]
                if "max" in mod and "maxAllowed" not in mod:
                    mod["maxAllowed"] = mod["max"]
                if "parentId" in mod and "group_id" not in mod:
                    mod["group_id"] = mod["parentId"]
                
                # Ensure PLU is set as reference_handler for consistency
                if "plu" in mod and not mod.get("reference_handler"):
                    mod["reference_handler"] = mod["plu"]
                    
                valid_modifiers.append(mod)
            else:
                logger.warning(
                    f"[MENU-FIX] Removed non-dictionary modifier at index {i}: {type(mod)}"
                )
        menu_data["modifiers"] = valid_modifiers
    
    # Process modifier groups from Deliverect format if needed
    if isinstance(menu_data.get("modifierGroups"), dict):
        logger.info("[MENU-FORMAT] Converting Deliverect modifierGroups dictionary to list")
        menu_data["modifierGroups"] = list(menu_data["modifierGroups"].values())
    
    # Ensure modifierGroups list exists and is valid
    if "modifierGroups" not in menu_data or not isinstance(
        menu_data["modifierGroups"], list
    ):
        logger.warning(
            f"[MENU-FIX] modifierGroups is not a valid list: {type(menu_data.get('modifierGroups', None))}"
        )
        menu_data["modifierGroups"] = []
    else:
        # Filter out non-dictionary modifier groups
        valid_groups = []
        for i, group in enumerate(menu_data["modifierGroups"]):
            if isinstance(group, dict):
                # Convert Deliverect modifier group properties to our expected format
                if "min" in group and "minAllowed" not in group:
                    group["minAllowed"] = group["min"]
                if "max" in group and "maxAllowed" not in group:
                    group["maxAllowed"] = group["max"]
                    
                # Handle subProducts array as modifiers list
                if "subProducts" in group and isinstance(group["subProducts"], list) and not group.get("modifiers"):
                    group["modifiers"] = group["subProducts"]
                    
                valid_groups.append(group)
            else:
                logger.warning(
                    f"[MENU-FIX] Removed non-dictionary modifier group at index {i}: {type(group)}"
                )
        menu_data["modifierGroups"] = valid_groups

    # AI agent will handle menu item matching - name_variants field is no longer needed
    if "name_variants" in menu_data:
        logger.info(
            "[MENU-FIX] Removing name_variants field - AI agent will handle matching"
        )
        menu_data.pop("name_variants", None)

    # Build map of existing items for reference
    existing_items = {}

    # Import here to avoid circular imports
    from app.utils.menu_db_store import menu_db_store
    
    # Process items
    fixed_item_count = 0
    items_missing_names = []

    # First pass - build map of existing items by name for reference preservation
    for item in menu_data.get("items", []):
        # Skip any non-dictionary items that might have slipped through
        if not isinstance(item, dict):
            logger.warning(f"[MENU-FIX] Skipping non-dictionary item: {type(item)}")
            continue

        if item.get("name"):
            # Ensure name is a string
            item_name = item.get("name", " ")
            if not isinstance(item_name, str):
                try:
                    item_name = str(item_name)
                    item["name"] = item_name  # Update the item with string name
                except:
                    item_name = " "

            item_name_lower = item_name.lower()
            existing_items[item_name_lower] = item

            # Also map by _id if present (handles different JSON formats)
            if item.get("_id"):
                existing_items[f"id:{item.get('_id')}"] = item
            if item.get("id"):
                existing_items[f"id:{item.get('id')}"] = item

    # Second pass - fix all issues with items
    for i, item in enumerate(menu_data.get("items", [])):
        # Skip any non-dictionary items that might have slipped through
        if not isinstance(item, dict):
            logger.warning(
                f"[MENU-FIX] Skipping non-dictionary item in second pass: {type(item)}"
            )
            continue

        # Track if we've fixed anything (for logging)
        item_fixed = False

        # Fix item ID
        item_id = item.get("id")
        if not item_id:
            # Check if _id exists but id doesn't (Deliverect format)
            if item.get("_id"):
                # Use _id as id for consistency
                item["id"] = item.get("_id")
                logger.info(f"[MENU-FIX] Converted _id to id for item index {i}")
                item_id = item["id"]
                item_fixed = True
            # Check if plu exists (Deliverect format often uses plu as primary reference)
            elif item.get("plu"):
                item["id"] = item.get("plu")
                logger.info(f"[MENU-FIX] Using plu as id for item index {i}: {item['id']}")
                item_id = item["id"]
                item_fixed = True
            else:
                # Generate a placeholder ID
                new_item_id = f"ITEM-{i:04d}"
                logger.warning(
                    f"[MENU-FIX] Item at index {i} is missing ID, setting to: {new_item_id}"
                )
                item["id"] = new_item_id
                item_id = new_item_id
                item_fixed = True

        # Fix item name (critical for functionality)
        item_name = item.get("name")

        # Ensure item_name is a string if it exists
        if item_name is not None and not isinstance(item_name, str):
            try:
                item_name = str(item_name)
                item["name"] = item_name
                logger.warning(
                    f"[MENU-FIX] Converting non-string name to string at index {i}: {type(item_name)}"
                )
                item_fixed = True
            except:
                item_name = None
                item["name"] = None

        # If name is missing or empty after conversion attempt, create a new one
        if not item_name:
            # Try to get name from reference_handler if available
            ref = item.get("reference_handler", "")
            if ref:
                item["name"] = f"Item-{ref[-8:]}"
            elif item_id:
                item["name"] = f"Item-{str(item_id)[-8:]}"
            else:
                item["name"] = f"Unnamed Item {i + 1}"
            logger.warning(
                f"[MENU-FIX] Fixed missing name for item at index {i}: '{item.get('name')}'"
            )
            item_fixed = True
            item_name = item["name"]  # Update the local variable

            # Track this item to verify it has a name after fixing
            items_missing_names.append(item)

        # At this point we have a string name
        item_name_lower = item_name.lower()

        # CRITICAL: For Deliverect integration, PLU must be preserved in reference_handler
        # Fix reference handler if missing
        if not item.get("reference_handler"):
            # HIGHEST PRIORITY: Use PLU directly if available (Deliverect format)
            if item.get("plu"):
                item["reference_handler"] = item.get("plu")
                logger.info(
                    f"[MENU-FIX] Using PLU as reference_handler for {item_name}: {item.get('plu')}"
                )
            # SECOND PRIORITY: Use item ID (Deliverect often has this as unique identifier)
            elif item.get("_id"):
                item["reference_handler"] = item.get("_id")
                logger.info(
                    f"[MENU-FIX] Using _id as reference_handler for {item_name}: {item.get('_id')}"
                )
            # THIRD PRIORITY: Check if item exists in the database
            elif item_name_lower in existing_items and existing_items[
                item_name_lower
            ].get("reference_handler"):
                # Preserve the existing reference handler
                item["reference_handler"] = existing_items[item_name_lower][
                    "reference_handler"
                ]
                logger.info(
                    f"[MENU-FIX] Preserved existing reference_handler for {item_name}"
                )
                # Also check if existing item had a PLU and copy it
                if existing_items[item_name_lower].get("plu"):
                    item["plu"] = existing_items[item_name_lower]["plu"]
                    logger.info(
                        f"[MENU-FIX] Preserved existing PLU for {item_name}: {item['plu']}"
                    )
            # Last resort: FAIL - we require valid reference handlers
            else:
                # STRICT DATABASE-ONLY MODE: No fallbacks allowed - we need real data
                error_msg = f"Item {item_name} has no PLU or reference_handler and no match in database"
                logger.error(f"[MENU-ERROR] {error_msg}")
                raise ValueError(error_msg)
            item_fixed = True

        # Ensure reference_handler is also stored as PLU for Deliverect integration
        if not item.get("plu") and item.get("reference_handler"):
            item["plu"] = item["reference_handler"]
            logger.info(
                f"[MENU-FIX] Setting PLU to match reference_handler for {item_name}: {item['plu']}"
            )
            item_fixed = True

        # Ensure price is valid - prioritize preserving existing prices
        price_invalid = False

        # Check if this is a category or variant product - these have special price handling
        is_category = False
        is_variant_product = False
        
        # Multiple ways to identify a category:
        # 1. explicit is_category flag
        if item.get("is_category") == True:
            is_category = True
        # 2. productType = 3 indicates a category or modifier group
        elif item.get("productType") == 3:
            is_category = True
        # 3. Has subProducts but no price - likely a category
        elif "subProducts" in item and isinstance(item.get("subProducts"), list) and len(item.get("subProducts")) > 0:
            is_category = True
        # 4. From the categories section with the same ID structure
        elif item.get("_id") and "categories" in menu_data and isinstance(menu_data["categories"], list):
            for category in menu_data["categories"]:
                if category.get("_id") == item.get("_id"):
                    is_category = True
                    break
        # 5. Name starts with category marker
        elif isinstance(item.get("name"), str) and item.get("name").startswith("[CATEGORY]"):
            is_category = True
        # 6. Use contextual information to identify categories based on patterns, not hardcoded values
        elif isinstance(item.get("name"), str):
            # Look for potential category naming patterns
            item_name_lower = item.get("name", "").lower()
            if (("categor" in item_name_lower) or
                ("section" in item_name_lower) or 
                ("group" in item_name_lower) or
                (len(menu_data.get("categories", [])) > 0 and 
                 any(category.get("name", "").lower() == item_name_lower for category in menu_data.get("categories", [])))
               ):
                is_category = True
        
        # Also check for variant products (per Deliverect docs)
        # Variant products can have zero price if they use subItems to define variants with prices
        if item.get("isVariant") == True:
            is_variant_product = True
            logger.info(f"[MENU-FIX] Item {item_name} identified as a variant product with isVariant flag")
        # Check if it has modifiers or subProducts with prices
        elif "subItems" in item and isinstance(item.get("subItems"), list) and len(item.get("subItems")) > 0:
            is_variant_product = True
            logger.info(f"[MENU-FIX] Item {item_name} identified as a variant product with subItems")
        # Check for variant group membership
        elif "isVariantGroup" in item and item.get("isVariantGroup") == True:
            is_variant_product = True
            logger.info(f"[MENU-FIX] Item {item_name} identified as a variant group")
        # Variant products in Deliverect often have zero price with variants as separate products
        elif item.get("price") == 0 and "subProducts" in item and isinstance(item.get("subProducts"), list) and len(item.get("subProducts")) > 0:
            is_variant_product = True
            logger.info(f"[MENU-FIX] Item {item_name} identified as variant container with subProducts and zero price")
        
        if is_category:
            # Mark explicitly as a category for future reference
            item["is_category"] = True
            
            # Categories don't need prices, so set a zero price and skip validation
            if "price" not in item or item["price"] is None:
                item["price"] = 0
                logger.info(f"[MENU-FIX] Item {item_name} identified as a category, setting zero price")
                item_fixed = True
                # Skip price validation for categories
                price_invalid = False
        elif is_variant_product:
            # Mark explicitly as a variant product for future reference
            item["is_variant"] = True
            
            # Variant parent products are allowed to have zero price - the variants themselves have prices
            if "price" not in item or item["price"] is None:
                item["price"] = 0
                logger.info(f"[MENU-FIX] Item {item_name} identified as a variant product, allowing zero price")
                item_fixed = True
                # Skip price validation for variant products
                price_invalid = False
            elif not isinstance(item["price"], (int, float)):
                try:
                    # Try to convert to float
                    item["price"] = float(item["price"])
                    logger.info(f"[MENU-FIX] Converted non-numeric price for variant {item_name} to {item['price']}")
                    item_fixed = True
                except (ValueError, TypeError):
                    # Set to zero for variant products
                    item["price"] = 0
                    logger.info(f"[MENU-FIX] Reset invalid price for variant {item_name} to zero")
                    item_fixed = True
            # We don't check if price is zero for variant products - this is valid per Deliverect docs
        else:
            # For regular items, check price validity comprehensively
            price_invalid = False
            
            # Check if price is missing
            if "price" not in item:
                price_invalid = True
                logger.info(f"[MENU-FIX] Item {item_name} is missing price field")
            # Check if price is None
            elif item["price"] is None:
                price_invalid = True
                logger.info(f"[MENU-FIX] Item {item_name} has None price")
            # Check if price is not a number
            elif not isinstance(item["price"], (int, float)):
                try:
                    # Try to convert to float
                    item["price"] = float(item["price"])
                    logger.info(f"[MENU-FIX] Converted non-numeric price for {item_name} to {item['price']}")
                except (ValueError, TypeError):
                    price_invalid = True
                    logger.info(f"[MENU-FIX] Item {item_name} has invalid non-numeric price: {item.get('price')}")
            # Check if price is negative or zero
            elif item["price"] <= 0:
                price_invalid = True
                logger.info(f"[MENU-FIX] Item {item_name} has non-positive price: {item['price']}")

            if price_invalid:
                # Following Deliverect docs: For variants with PLU formats containing ###, 
                # we need to handle price mapping from original PLU in referenceId
                
                # First check: Check if referenceId exists (highest priority per Deliverect docs)
                if "referenceId" in item and item.get("referenceId"):
                    reference_id = item.get("referenceId")
                    logger.info(f"[MENU-FIX] Found referenceId {reference_id} for {item_name}, looking for base product")
                    
                    # Try to find a matching item by referenceId as PLU in the current menu data
                    base_item = None
                    for other_item in menu_data.get("items", []):
                        if (other_item.get("plu") == reference_id or 
                            other_item.get("reference_handler") == reference_id or
                            other_item.get("reference_price_source") == reference_id):
                            if isinstance(other_item.get("price"), (int, float)) and other_item.get("price") > 0:
                                base_item = other_item
                                break
                    
                    if base_item:
                        item["price"] = base_item.get("price")
                        logger.info(f"[MENU-FIX] Set price for {item_name} from base product with referenceId {reference_id}: {item['price']}")
                        price_invalid = False
                
                # Second check: Handle PLUs with ### pattern (per Deliverect docs)
                elif item.get("plu") and "###" in item.get("plu"):
                    # Extract the base PLU (everything before the ###)
                    base_plu = item.get("plu").split("###")[0]
                    if base_plu:
                        logger.info(f"[MENU-FIX] Extracted base PLU {base_plu} from {item.get('plu')} for {item_name}")
                        
                        # Try to find a matching item by extracted base PLU
                        base_item = None
                        for other_item in menu_data.get("items", []):
                            if other_item.get("plu") == base_plu or other_item.get("reference_handler") == base_plu:
                                if isinstance(other_item.get("price"), (int, float)) and other_item.get("price") > 0:
                                    base_item = other_item
                                    break
                        
                        if base_item:
                            item["price"] = base_item.get("price")
                            logger.info(f"[MENU-FIX] Set price for {item_name} from base product with PLU {base_plu}: {item['price']}")
                            price_invalid = False
                
                # Third check: Similar for variants with base_plu already extracted
                elif "is_variant" in item and item.get("base_plu"):
                    base_plu = item.get("base_plu")
                    logger.info(f"[MENU-FIX] Using pre-extracted base PLU {base_plu} for {item_name}")
                    
                    # Try to find a matching item by PLU
                    base_item = None
                    for other_item in menu_data.get("items", []):
                        if other_item.get("plu") == base_plu or other_item.get("reference_handler") == base_plu:
                            if isinstance(other_item.get("price"), (int, float)) and other_item.get("price") > 0:
                                base_item = other_item
                                break
                    
                    if base_item:
                        item["price"] = base_item.get("price")
                        logger.info(f"[MENU-FIX] Set price for {item_name} from base product with PLU {base_plu}: {item['price']}")
                        price_invalid = False
                
                # Fourth check: Special case for original_plu with ### (similar to second check)
                elif "original_plu" in item and "###" in item.get("original_plu", ""):
                    # Look for the base PLU (before ###)
                    base_plu = item.get("original_plu").split("###")[0]
                    logger.info(f"[MENU-FIX] Looking for base product with original_plu base {base_plu} for {item_name}")
                    
                    # Check if we have a saved extracted base in PLU or reference_handler
                    extracted_base = item.get("plu") or item.get("reference_handler")
                    if not extracted_base:
                        extracted_base = base_plu
                    
                    # Try to find a matching item
                    for other_item in menu_data.get("items", []):
                        if (other_item.get("plu") == extracted_base or 
                            other_item.get("reference_handler") == extracted_base or
                            other_item.get("plu") == base_plu):
                            if isinstance(other_item.get("price"), (int, float)) and other_item.get("price") > 0:
                                item["price"] = other_item.get("price")
                                logger.info(f"[MENU-FIX] Set price for {item_name} from product with PLU {extracted_base}: {item['price']}")
                                price_invalid = False
                                break
                
                # Fifth check: preserving existing prices from the current menu
                if price_invalid and item_name_lower in existing_items and existing_items[item_name_lower].get("price"):
                    # Preserve the existing price
                    item["price"] = existing_items[item_name_lower]["price"]
                    logger.info(f"[MENU-FIX] Preserved existing price for {item_name}: {item['price']}")
                    price_invalid = False
                
                # Sixth check: database lookup - STRICT DATABASE-ONLY VALIDATION
                if price_invalid:
                    # Get menu data from database
                    menu_data_db = menu_db_store.get_menu_data(force_refresh=True)
                    
                    # Check if database contains items
                    if not menu_data_db.get("items"):
                        # Look first at the product definition (original JSON data) to see if we can use the price
                        # from the source data without using hardcoded values
                        original_price = None
                        
                        # Get raw price from the incoming menu data
                        if item.get("raw_price") is not None:
                            original_price = item.get("raw_price")
                            logger.info(f"[MENU-FIX] Empty DB: Using raw_price from original data for {item_name}: {original_price}")
                        # If price is in cents format from Deliverect, convert it
                        elif "price" in item and isinstance(item["price"], (int, float)) and item["price"] > 100:
                            # Price might be in cents format - normalize by dividing by 100
                            original_price = item["price"] / 100
                            logger.info(f"[MENU-FIX] Empty DB: Normalized cents price for {item_name}: {original_price}")
                            
                        if original_price is not None and original_price > 0:
                            item["price"] = original_price
                            price_invalid = False
                        # If this is a variant product, it's valid to have zero price
                        elif "isVariant" in item or item.get("is_variant"):
                            # For variant containers specifically, zero price is expected
                            item["price"] = 0
                            logger.info(f"[MENU-FIX] Empty DB: Setting zero price for variant container {item_name}")
                            price_invalid = False
                        # For items with PLU variants, we need to get price from the base product
                        elif item.get("plu") and "###" in item.get("plu", ""):
                            # Extract the base PLU from the PLU or use already extracted base_plu
                            base_plu = item.get("base_plu") if item.get("base_plu") else item.get("plu").split("###")[0]
                            
                            # Find the base product in the incoming menu data
                            base_product = None
                            for other_item in menu_data.get("items", []):
                                if (other_item.get("plu") == base_plu or 
                                    other_item.get("reference_handler") == base_plu or
                                    other_item.get("reference_price_source") == base_plu):
                                    base_product = other_item
                                    break
                                    
                            # If we found the base product and it has a price, use it
                            if base_product and "price" in base_product and isinstance(base_product["price"], (int, float)) and base_product["price"] > 0:
                                item["price"] = base_product["price"]
                                logger.info(f"[MENU-FIX] Empty DB: Using base product price for {item_name}: {item['price']}")
                                price_invalid = False
                            # If base product has a raw_price, use that instead
                            elif base_product and "raw_price" in base_product and isinstance(base_product["raw_price"], (int, float)) and base_product["raw_price"] > 0:
                                item["price"] = base_product["raw_price"]
                                logger.info(f"[MENU-FIX] Empty DB: Using base product raw_price for {item_name}: {item['price']}")
                                price_invalid = False
                       
                        # If still invalid, we cannot validate this item without a database
                        if price_invalid:
                            # For variant containers with variants that have prices, it's valid
                            if item.get("productType") == 3 or item.get("is_variant"):
                                item["price"] = 0
                                logger.info(f"[MENU-FIX] Empty DB: Setting zero price for variant/category {item_name}")
                                price_invalid = False
                            else:
                                # No valid source of price information with empty database - fail validation
                                error_msg = f"Item {item_name} has missing or invalid price and database is empty. No price source available."
                                logger.error(f"[MENU-ERROR] {error_msg}")
                                raise ValueError(error_msg)
                    
                    # Try to find matching item in database by name
                    db_item = None
                    for db_item_entry in menu_data_db.get("items", []):
                        db_item_name = db_item_entry.get("name", "").lower()
                        if db_item_name == item_name_lower or db_item_name in item_name_lower or item_name_lower in db_item_name:
                            db_item = db_item_entry
                            break
                    
                    # If not found by name, try by PLU/reference_handler
                    if not db_item and (item.get("plu") or item.get("reference_handler")):
                        for db_item_entry in menu_data_db.get("items", []):
                            if (db_item_entry.get("plu") == item.get("plu") or 
                                db_item_entry.get("reference_handler") == item.get("reference_handler")):
                                db_item = db_item_entry
                                break
                    
                    # If still not found and item has a PLU with special format, try to match by base PLU
                    if not db_item and item.get("plu") and ("#" in item.get("plu") or "-" in item.get("plu")):
                        plu = item.get("plu")
                        possible_base_plu = None
                        
                        # Extract possible base PLU from patterns based on Deliverect docs
                        if "###" in plu:
                            possible_base_plu = plu.split("###")[0]
                        elif "-" in plu:
                            parts = plu.split("-")
                            if len(parts) > 1:
                                possible_base_plu = "-".join(parts[:-1]) if len(parts) > 2 else parts[0]
                        
                        if possible_base_plu:
                            logger.info(f"[MENU-FIX] Extracted possible base PLU {possible_base_plu} from {plu} for database search")
                            for db_item_entry in menu_data_db.get("items", []):
                                if (db_item_entry.get("plu") == possible_base_plu or 
                                    db_item_entry.get("reference_handler") == possible_base_plu):
                                    db_item = db_item_entry
                                    break
                    
                    if db_item and isinstance(db_item.get("price"), (int, float)) and db_item.get("price") > 0:
                        item["price"] = db_item.get("price")
                        logger.info(f"[MENU-FIX] Set price for {item_name} using database match: {item['price']}")
                        price_invalid = False
                    else:
                        # Truly couldn't find a valid price - fail with error
                        error_msg = f"Item {item_name} has missing or invalid price and no matching price found in database"
                        logger.error(f"[MENU-ERROR] {error_msg}")
                        raise ValueError(error_msg)
                item_fixed = True

        # Ensure description exists (can be empty)
        if "description" not in item:
            item["description"] = ""
            item_fixed = True
        elif item["description"] is not None and not isinstance(
            item["description"], str
        ):
            try:
                item["description"] = str(item["description"])
            except:
                item["description"] = ""
            item_fixed = True

        # Ensure availability is properly initialized
        if "available" not in item:
            # Default to available unless explicitly snoozed
            item["available"] = not item.get("snoozed", False)
            item_fixed = True
        elif not isinstance(item["available"], bool):
            # Convert to boolean if not already
            item["available"] = bool(item["available"])
            item_fixed = True

        # Ensure snoozed is properly initialized
        if "snoozed" not in item:
            # Default to not snoozed unless explicitly unavailable
            item["snoozed"] = not item.get("available", True)
            item_fixed = True
        elif not isinstance(item["snoozed"], bool):
            # Convert to boolean if not already
            item["snoozed"] = bool(item["snoozed"])
            item_fixed = True

        # Track total fixes
        if item_fixed:
            fixed_item_count += 1

    # Process modifier groups
    fixed_modifier_group_count = 0
    fixed_modifier_count = 0
    seen_group_ids = set()

    # Ensure modifierGroups is a list before processing
    modifier_groups = menu_data.get("modifierGroups", [])
    if not isinstance(modifier_groups, list):
        logger.warning(
            f"[MENU-FIX] modifierGroups is not a list: {type(modifier_groups)}. Creating empty list."
        )
        menu_data["modifierGroups"] = []
        modifier_groups = []

    for i, group in enumerate(modifier_groups):
        # Ensure group is a dictionary
        if not isinstance(group, dict):
            logger.warning(
                f"[MENU-FIX] Skipping non-dictionary modifier group at index {i}: {type(group)}"
            )
            continue

        # Try to get group name, defaulting to an index-based name if missing
        group_name = group.get("name")
        if not group_name:
            group_name = f"Group {i+1}"
            group["name"] = group_name
            logger.warning(
                f"[MENU-FIX] Adding missing name for modifier group at index {i}"
            )
            fixed_modifier_group_count += 1
        elif not isinstance(group_name, str):
            try:
                group_name = str(group_name)
                group["name"] = group_name
                logger.warning(
                    f"[MENU-FIX] Converting non-string name for modifier group at index {i}"
                )
                fixed_modifier_group_count += 1
            except:
                group_name = f"Group {i+1}"
                group["name"] = group_name
                logger.warning(
                    f"[MENU-FIX] Replacing invalid name for modifier group at index {i}"
                )
                fixed_modifier_group_count += 1

        # Fix missing group ID
        group_id = group.get("id")
        if not group_id:
            # Generate a consistent ID based on name
            try:
                new_group_id = f"MG-{hashlib.md5(group_name.encode()).hexdigest()[:8]}"
            except:
                new_group_id = f"MG-{i:04d}"
            logger.warning(
                f"[MENU-FIX] Modifier group '{group_name}' is missing ID, setting to: {new_group_id}"
            )
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1
        elif not isinstance(group_id, str):
            try:
                group_id = str(group_id)
                group["id"] = group_id
                logger.warning(
                    f"[MENU-FIX] Converting non-string ID for modifier group '{group_name}'"
                )
                fixed_modifier_group_count += 1
            except:
                new_group_id = f"MG-{i:04d}"
                group["id"] = new_group_id
                group_id = new_group_id
                logger.warning(
                    f"[MENU-FIX] Replacing invalid ID for modifier group '{group_name}'"
                )
                fixed_modifier_group_count += 1

        # Handle duplicate group IDs
        if group_id in seen_group_ids:
            # Add a suffix to make it unique
            new_group_id = f"{group_id}-{len(seen_group_ids)}"
            logger.warning(
                f"[MENU-FIX] Duplicate modifier group ID {group_id}, changing to: {new_group_id}"
            )
            group["id"] = new_group_id
            group_id = new_group_id
            fixed_modifier_group_count += 1

        seen_group_ids.add(group_id)

        # Ensure min/max constraints are valid
        if "minAllowed" not in group or not isinstance(
            group["minAllowed"], (int, float)
        ):
            # STRICT DATABASE-ONLY VALIDATION - ABSOLUTELY NO FALLBACKS
            # Get menu data from database
            menu_data_db = menu_db_store.get_menu_data(force_refresh=True)
            db_group = None
            
            for db_grp in menu_data_db.get("modifierGroups", []):
                if db_grp.get("id") == group_id or db_grp.get("name") == group_name:
                    db_group = db_grp
                    break
            
            if db_group and isinstance(db_group.get("minAllowed"), (int, float)):
                group["minAllowed"] = db_group.get("minAllowed")
                logger.info(
                    f"[MENU-FIX] Set minAllowed for group '{group_name}' using database match: {group['minAllowed']}"
                )
            else:
                # ABSOLUTELY NO FALLBACKS - If the group doesn't exist in the database with valid parameters, it MUST fail
                error_msg = f"Modifier group '{group_name}' has invalid minAllowed and no matching value found in database"
                logger.error(f"[MENU-ERROR] {error_msg}")
                raise ValueError(error_msg)
            fixed_modifier_group_count += 1

        if "maxAllowed" not in group or not isinstance(
            group["maxAllowed"], (int, float)
        ):
            # STRICT DATABASE-ONLY VALIDATION - ABSOLUTELY NO FALLBACKS
            # Try to find matching group in database if not already fetched
            if 'db_group' not in locals() or db_group is None:
                menu_data_db = menu_db_store.get_menu_data(force_refresh=True)
                db_group = None
                
                for db_grp in menu_data_db.get("modifierGroups", []):
                    if db_grp.get("id") == group_id or db_grp.get("name") == group_name:
                        db_group = db_grp
                        break
            
            if db_group and isinstance(db_group.get("maxAllowed"), (int, float)):
                group["maxAllowed"] = db_group.get("maxAllowed")
                logger.info(
                    f"[MENU-FIX] Set maxAllowed for group '{group_name}' using database match: {group['maxAllowed']}"
                )
            else:
                # ABSOLUTELY NO FALLBACKS - If the group doesn't exist in the database with valid parameters, it MUST fail
                error_msg = f"Modifier group '{group_name}' has invalid maxAllowed and no matching value found in database"
                logger.error(f"[MENU-ERROR] {error_msg}")
                raise ValueError(error_msg)
            fixed_modifier_group_count += 1

        # Ensure multiMax constraint is valid (maximum quantity of any single modifier)
        if "multiMax" not in group or not isinstance(group["multiMax"], (int, float)):
            # STRICT DATABASE-ONLY VALIDATION - ABSOLUTELY NO FALLBACKS
            # Try to find matching group in database if not already fetched
            if 'db_group' not in locals() or db_group is None:
                menu_data_db = menu_db_store.get_menu_data(force_refresh=True)
                db_group = None
                
                for db_grp in menu_data_db.get("modifierGroups", []):
                    if db_grp.get("id") == group_id or db_grp.get("name") == group_name:
                        db_group = db_grp
                        break
            
            if db_group and isinstance(db_group.get("multiMax"), (int, float)):
                group["multiMax"] = db_group.get("multiMax")
                logger.info(
                    f"[MENU-FIX] Set multiMax for group '{group_name}' using database match: {group['multiMax']}"
                )
            else:
                # ABSOLUTELY NO FALLBACKS - If the group doesn't exist in the database with valid parameters, it MUST fail
                error_msg = f"Modifier group '{group_name}' has invalid multiMax and no matching value found in database"
                logger.error(f"[MENU-ERROR] {error_msg}")
                raise ValueError(error_msg)
            fixed_modifier_group_count += 1

        # Ensure isVariantGroup flag is a boolean
        if "isVariantGroup" in group and not isinstance(group["isVariantGroup"], bool):
            group["isVariantGroup"] = bool(group["isVariantGroup"])
            fixed_modifier_group_count += 1

        # Ensure modifiers is a list
        modifiers = group.get("modifiers", [])
        if not isinstance(modifiers, list):
            logger.warning(
                f"[MENU-FIX] modifiers in group {group_id} is not a list: {type(modifiers)}. Creating empty list."
            )
            group["modifiers"] = []
            modifiers = []
            fixed_modifier_group_count += 1
        else:
            # Clean up non-string or non-dict modifiers
            valid_modifiers = []
            for j, modifier in enumerate(modifiers):
                if isinstance(modifier, str):
                    valid_modifiers.append(modifier)
                elif isinstance(modifier, dict) and "id" in modifier:
                    valid_modifiers.append(modifier["id"])
                else:
                    logger.warning(
                        f"[MENU-FIX] Skipping invalid modifier at index {j} in group {group_id}"
                    )

            if len(valid_modifiers) != len(modifiers):
                logger.warning(
                    f"[MENU-FIX] Filtered {len(modifiers) - len(valid_modifiers)} invalid modifiers in group {group_id}"
                )
                group["modifiers"] = valid_modifiers
                fixed_modifier_group_count += 1

    # Process modifiers list
    modifiers = menu_data.get("modifiers", [])
    for i, modifier in enumerate(modifiers):
        # Ensure modifier is a dictionary
        if not isinstance(modifier, dict):
            logger.warning(
                f"[MENU-FIX] Skipping non-dictionary modifier at index {i}: {type(modifier)}"
            )
            continue

        # Track if we fixed anything
        mod_fixed = False

        # Try to get modifier name, defaulting if missing
        mod_name = modifier.get("name")
        if not mod_name:
            mod_name = f"Modifier {i+1}"
            modifier["name"] = mod_name
            logger.warning(f"[MENU-FIX] Adding missing name for modifier at index {i}")
            mod_fixed = True
        elif not isinstance(mod_name, str):
            try:
                mod_name = str(mod_name)
                modifier["name"] = mod_name
                logger.warning(
                    f"[MENU-FIX] Converting non-string name for modifier at index {i}"
                )
                mod_fixed = True
            except:
                mod_name = f"Modifier {i+1}"
                modifier["name"] = mod_name
                logger.warning(
                    f"[MENU-FIX] Replacing invalid name for modifier at index {i}"
                )
                mod_fixed = True

        # Fix missing modifier ID
        mod_id = modifier.get("id")
        if not mod_id:
            # Generate a consistent ID based on name
            try:
                new_mod_id = f"MOD-{hashlib.md5(mod_name.encode()).hexdigest()[:8]}"
            except:
                new_mod_id = f"MOD-{i:04d}"
            logger.warning(
                f"[MENU-FIX] Modifier '{mod_name}' is missing ID, setting to: {new_mod_id}"
            )
            modifier["id"] = new_mod_id
            mod_id = new_mod_id
            mod_fixed = True
        elif not isinstance(mod_id, str):
            try:
                mod_id = str(mod_id)
                modifier["id"] = mod_id
                logger.warning(
                    f"[MENU-FIX] Converting non-string ID for modifier '{mod_name}'"
                )
                mod_fixed = True
            except:
                new_mod_id = f"MOD-{i:04d}"
                modifier["id"] = new_mod_id
                mod_id = new_mod_id
                logger.warning(
                    f"[MENU-FIX] Replacing invalid ID for modifier '{mod_name}'"
                )
                mod_fixed = True

        # Fix reference handler if missing
        if not modifier.get("reference_handler"):
            if modifier.get("plu"):
                modifier["reference_handler"] = modifier.get("plu")
                logger.warning(
                    f"[MENU-FIX] Using PLU as reference_handler for modifier {mod_name}"
                )
            else:
                import re

                # Create a reference based on modifier name
                clean_name = re.sub(r"[^\w]", "", mod_name)
                if clean_name:
                    plu = f"MOD-{clean_name[:10]}"
                else:
                    # Use a hash-based ID if name has no alphanumeric chars
                    import hashlib

                    hash_obj = hashlib.md5(mod_name.encode())
                    plu = f"MOD-{hash_obj.hexdigest()[:8]}"

                logger.warning(
                    f"[MENU-FIX] Modifier {mod_name} is missing reference_handler, fixing to: {plu}"
                )
                modifier["reference_handler"] = plu
            mod_fixed = True

        # Ensure price is valid
        price_invalid = False

        # Check if price is missing
        if "price" not in modifier:
            price_invalid = True
        # Check if price is None
        elif modifier["price"] is None:
            price_invalid = True
        # Check if price is not a number
        elif not isinstance(modifier["price"], (int, float)):
            try:
                # Try to convert to float
                modifier["price"] = float(modifier["price"])
            except (ValueError, TypeError):
                price_invalid = True
        # Check if price is negative
        elif modifier["price"] < 0:
            price_invalid = True

        if price_invalid:
            # STRICT DATABASE-ONLY VALIDATION - ABSOLUTELY NO FALLBACKS
            # Get menu data from database
            menu_data_db = menu_db_store.get_menu_data(force_refresh=True)
            db_modifier = None
            
            for db_mod in menu_data_db.get("modifiers", []):
                db_mod_name = db_mod.get("name", "").lower()
                mod_name_lower = mod_name.lower()
                if db_mod_name == mod_name_lower or db_mod_name in mod_name_lower or mod_name_lower in db_mod_name:
                    db_modifier = db_mod
                    break
            
            if db_modifier and isinstance(db_modifier.get("price"), (int, float)):
                modifier["price"] = db_modifier.get("price")
                logger.info(
                    f"[MENU-FIX] Set price for modifier {mod_name} using database match: {modifier['price']}"
                )
            else:
                # ABSOLUTELY NO FALLBACKS - If the modifier doesn't exist in the database with a valid price, it MUST fail
                error_msg = f"Modifier {mod_name} has invalid price and no matching price found in database"
                logger.error(f"[MENU-ERROR] {error_msg}")
                raise ValueError(error_msg)
            mod_fixed = True

        # Ensure availability is properly initialized
        if "available" not in modifier:
            modifier["available"] = True
            mod_fixed = True
        elif not isinstance(modifier["available"], bool):
            modifier["available"] = bool(modifier["available"])
            mod_fixed = True

        # Track total fixes
        if mod_fixed:
            fixed_modifier_count += 1

    if (
        fixed_item_count > 0
        or fixed_modifier_group_count > 0
        or fixed_modifier_count > 0
    ):
        logger.info(
            f"[MENU-FIX] Fixed {fixed_item_count} items, {fixed_modifier_group_count} modifier groups, and {fixed_modifier_count} modifiers"
        )

    # Final validation: Ensure ALL items have names after fixing attempts
    items_still_missing_names = [
        item for item in menu_data.get("items", []) if not item.get("name")
    ]
    if items_still_missing_names:
        missing_count = len(items_still_missing_names)
        item_indices = [
            menu_data.get("items", []).index(item)
            for item in items_still_missing_names[:3]
        ]
        logger.error(
            f"[MENU-VALIDATION] {missing_count} items still missing names after fixing attempts. Problem indices: {item_indices}"
        )

        # Instead of silent fixing, raise an error
        error_msg = f"{len(items_still_missing_names)} items still missing names after fixing attempts"
        logger.error(f"[MENU-ERROR] {error_msg}")
        raise ValueError(error_msg)

    # Final validation: Check every item for empty string names
    empty_name_items = [
        item for item in menu_data.get("items", []) if item.get("name") == ""
    ]
    if empty_name_items:
        empty_count = len(empty_name_items)
        item_indices = [
            menu_data.get("items", []).index(item) for item in empty_name_items[:3]
        ]
        logger.error(
            f"[MENU-VALIDATION] {empty_count} items have empty string names. Problem indices: {item_indices}"
        )

        # Instead of silent fixing, raise an error
        error_msg = f"{len(empty_name_items)} items have empty string names"
        logger.error(f"[MENU-ERROR] {error_msg}")
        raise ValueError(error_msg)

    # Mark category items clearly to prevent them from being matched as orderable items
    category_count = 0
    for item in menu_data.get("items", []):
        if item.get("is_category", False):
            # Make sure this is correctly flagged as a category
            item["is_category"] = True

            # For extra clarity, add a prefix to category names if missing
            if not item["name"].startswith("[CATEGORY]"):
                item["name"] = f"[CATEGORY] {item['name']}"
                category_count += 1

    if category_count > 0:
        logger.info(
            f"[MENU-FIX] Marked {category_count} categories with [CATEGORY] prefix for clarity"
        )

    # Set fixes to log instead of adding as attribute, since in Python dictionaries
    # can't have arbitrary attributes set (menu_data is a dict, not an object)
    fixes = []
    if fixed_item_count > 0:
        fixes.append(f"Fixed {fixed_item_count} items")
        logger.info(f"[MENU-FIX] Fixed {fixed_item_count} items")
    if fixed_modifier_group_count > 0:
        fixes.append(f"Fixed {fixed_modifier_group_count} modifier groups")
        logger.info(f"[MENU-FIX] Fixed {fixed_modifier_group_count} modifier groups")
    if fixed_modifier_count > 0:
        fixes.append(f"Fixed {fixed_modifier_count} modifiers")
        logger.info(f"[MENU-FIX] Fixed {fixed_modifier_count} modifiers")

    return menu_data
