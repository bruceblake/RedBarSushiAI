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
    Gets menu price information from the database.
    No longer loads from JSON files - exclusively uses the database.

    Returns:
        dict: Mapping of item names to price info
    """
    try:
        # Import here to avoid circular imports
        from app.utils.menu_db_store import menu_db_store
        
        # Get menu data from database
        menu_data = menu_db_store.get_menu_data(force_refresh=True)
        
        # Build a comprehensive price map from actual menu data
        result = {}
        
        # Process all items with valid names and prices
        for item in menu_data.get("items", []):
            item_name = item.get("name", "").lower()
            if not item_name:
                continue
                
            # Ensure we have a valid price
            price = item.get("price")
            if not isinstance(price, (int, float)) or price is None:
                # Don't set a default price - let the error propagate
                continue
                
            # Extract reference handler
            ref_handler = item.get("reference_handler", "")
            if not ref_handler:
                # Skip items without reference handlers - we need proper identification
                continue
                
            # Store the item info by name for exact matching
            result[item_name] = {
                "price": price,
                "reference_handler": ref_handler,
                "full_name": item.get("name", "")  # Store original case
            }

            # Also store name fragments for fuzzy matching
            words = item_name.split()
            for word in words:
                if len(word) > 3 and word not in result:  # Only meaningful words
                    result[word] = {
                        "price": price,
                        "reference_handler": ref_handler,
                        "full_name": item.get("name", "")  # Store original case
                    }
        
        # Only return the built dictionary if it has items
        if result:
            logging.info(f"[MENU-PRICES] Loaded {len(result)} price entries from database")
            return result
            
        # If we got here, the database is empty
        logging.error("[MENU-PRICES] No menu items found in database")
        raise ValueError("No menu items found in database")
            
    except Exception as e:
        logging.error(f"[MENU-ERROR] Error getting menu data from database: {e}")
        raise ValueError(f"Error loading menu data: {e}")


def generate_consistent_reference_id(item_name):
    """
    Generate a consistent reference ID based on item name.

    Args:
        item_name: The name of the item

    Returns:
        str: A consistent reference ID
    """
    return f"REF-{hashlib.md5(item_name.lower().encode()).hexdigest()[:8]}"
