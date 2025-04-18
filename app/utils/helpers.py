# app/utils/helpers.py
import logging
import time
import hashlib
import os
import json


def log_info(msg):
    logging.info(msg)


def commit_with_retry(session, max_retries=3):
    """
    Commit a database session with retries on failure.

    Args:
        session: SQLAlchemy session
        max_retries: Maximum number of retry attempts

    Returns:
        bool: True if commit succeeded, False otherwise
    """
    for attempt in range(max_retries):
        try:
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logging.error(f"Commit attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retrying
    return False


def get_common_prices():
    """
    Loads actual prices directly from menu_data.json to ensure we always
    have the latest prices and reference handlers.

    Returns:
        dict: Mapping of item names to price info
    """
    try:
        from app.config import MENU_FILE_PATH

        # Core fallback items (only used if menu loading completely fails)
        fallback = {
            # Burgers
            "hamburger": {
                "price": 8.0,
                "reference_handler": "BRG-01",
                "full_name": "Hamburger",
            },
            "burger": {
                "price": 8.0,
                "reference_handler": "BRG-01",
                "full_name": "Hamburger",
            },
            "veggie burger": {
                "price": 7.5,
                "reference_handler": "BRG-02",
                "full_name": "Veggie Burger",
            },
            "cheeseburger": {
                "price": 8.5,
                "reference_handler": "BRG-03",
                "full_name": "Cheeseburger",
            },
            # Sides
            "french fries": {
                "price": 2.0,
                "reference_handler": "P-FRS-S",
                "full_name": "French Fries",
            },
            "fries": {
                "price": 2.0,
                "reference_handler": "P-FRS-S",
                "full_name": "French Fries",
            },
            "side": {
                "price": 3.5,
                "reference_handler": "SIDE-01",
                "full_name": "Side Dish",
            },
            "salad": {
                "price": 6.0,
                "reference_handler": "SLD-001",
                "full_name": "Garden Salad",
            },
            "rice": {
                "price": 2.5,
                "reference_handler": "SIDE-03",
                "full_name": "Steamed Rice",
            },
            "noodles": {
                "price": 4.0,
                "reference_handler": "SIDE-04",
                "full_name": "Noodles",
            },
            # Drinks
            "coca cola": {
                "price": 4.0,
                "reference_handler": "DRK-01",
                "full_name": "Coca Cola",
            },
            "coke": {
                "price": 4.0,
                "reference_handler": "DRK-01",
                "full_name": "Coca Cola",
            },
            "diet coke": {
                "price": 4.0,
                "reference_handler": "DRK-02",
                "full_name": "Diet Coke",
            },
            "drink": {
                "price": 2.0,
                "reference_handler": "DRK-GEN",
                "full_name": "Soft Drink",
            },
            "soda": {"price": 2.0, "reference_handler": "DRK-GEN", "full_name": "Soda"},
            "water": {
                "price": 0.0,
                "reference_handler": "DRK-WAT",
                "full_name": "Water",
            },
            # Extra categories for common items
            "chicken": {
                "price": 6.5,
                "reference_handler": "ENT-CHK",
                "full_name": "Chicken Entree",
            },
            "beef": {
                "price": 8.0,
                "reference_handler": "ENT-BEEF",
                "full_name": "Beef Entree",
            },
            "fish": {
                "price": 9.0,
                "reference_handler": "ENT-FISH",
                "full_name": "Fish Entree",
            },
            "sandwich": {
                "price": 6.5,
                "reference_handler": "SND-GEN",
                "full_name": "Sandwich",
            },
        }

        # Try multiple potential menu file paths - this is critical for production
        possible_paths = [
            MENU_FILE_PATH,
            os.path.join(os.path.dirname(MENU_FILE_PATH), "menu_data.json"),
            os.path.join(os.path.dirname(MENU_FILE_PATH), "redbar_menu_data.json"),
            os.path.join(
                os.path.dirname(os.path.dirname(MENU_FILE_PATH)), "menu_data.json"
            ),
            "/home/pegasus/mysite/RedBarSushiAI/menu_data.json",  # Hardcoded production path
            "/home/proxyie/MySoftware/RedBarSushiAI/menu_data.json",  # Test environment path
            os.path.join(os.getcwd(), "menu_data.json"),  # Current directory
        ]

        # Try each path until we find an existing file
        loaded_path = None
        for path in possible_paths:
            if os.path.exists(path):
                loaded_path = path
                break

        if loaded_path:
            logging.info(f"[MENU-LOAD] Loading menu from: {loaded_path}")
            try:
                with open(loaded_path, "r") as f:
                    file_content = f.read()

                    # Check for empty file
                    if not file_content.strip():
                        logging.error(f"[MENU-ERROR] Menu file {loaded_path} is empty")
                        return fallback

                    # Parse the JSON
                    menu_data = json.loads(file_content)

                    # Build a comprehensive price map from actual menu data
                    result = {}

                    # First check if the menu has a name_variants section
                    # This is the fastest path to get accurate mappings
                    name_variants = menu_data.get("name_variants", {})
                    if name_variants:
                        logging.info(
                            f"[MENU-LOAD] Using {len(name_variants)} name variants from menu data"
                        )

                        # Build a mapping from variants to items with prices
                        for variant_name, original_name in name_variants.items():
                            # Find the item with this name
                            for item in menu_data.get("items", []):
                                if item.get("name") == original_name:
                                    # Add to result with full details
                                    result[variant_name] = {
                                        "price": item.get("price", 0.0),
                                        "reference_handler": item.get(
                                            "reference_handler", ""
                                        ),
                                        "full_name": original_name,
                                    }
                                    break

                    # Process all items with valid names and prices (fallback or to supplement variants)
                    for item in menu_data.get("items", []):
                        item_name = item.get("name", "").lower()
                        if not item_name:
                            continue

                        # Ensure we have a valid price
                        price = item.get("price")
                        if not isinstance(price, (int, float)) or price is None:
                            price = 0.0

                        # Extract or generate reference handler
                        ref_handler = item.get("reference_handler", "")
                        if not ref_handler:
                            ref_handler = generate_consistent_reference_id(item_name)

                        # Store the item info by name for exact matching
                        result[item_name] = {
                            "price": price,
                            "reference_handler": ref_handler,
                            "full_name": item.get("name", ""),  # Store original case
                        }

                        # Also store name fragments for fuzzy matching if not already in variants
                        if (
                            not name_variants
                        ):  # Only do this if we don't have name_variants
                            words = item_name.split()
                            for word in words:
                                if (
                                    len(word) > 3 and word not in result
                                ):  # Only meaningful words
                                    result[word] = {
                                        "price": price,
                                        "reference_handler": ref_handler,
                                        "full_name": item.get(
                                            "name", ""
                                        ),  # Store original case
                                    }

                    # Only return the built dictionary if it has items
                    if result:
                        logging.info(
                            f"[MENU-PRICES] Loaded {len(result)} price entries from menu data at {loaded_path}"
                        )
                        return result

            except json.JSONDecodeError as e:
                logging.error(
                    f"[MENU-ERROR] Invalid JSON in menu file {loaded_path}: {e}"
                )
            except Exception as e:
                logging.error(
                    f"[MENU-ERROR] Error loading menu from {loaded_path}: {e}"
                )

        # We couldn't load from any path, log this clearly
        paths_str = "\n - ".join(possible_paths)
        logging.error(
            f"[MENU-ERROR] Could not find valid menu file in any of these locations:\n - {paths_str}"
        )
    except Exception as e:
        logging.error(f"[MENU-ERROR] Error loading menu data for prices: {e}")

    # Return fallback prices if menu loading fails
    logging.warning(
        "[MENU-FALLBACK] Using hardcoded fallback prices - menu data unavailable"
    )
    return fallback


def generate_consistent_reference_id(item_name):
    """
    Generate a consistent reference ID based on item name.

    Args:
        item_name: The name of the item

    Returns:
        str: A consistent reference ID
    """
    return f"REF-{hashlib.md5(item_name.lower().encode()).hexdigest()[:8]}"
