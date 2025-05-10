# app/utils/helpers_async.py
import logging
import time
import asyncio

async def log_info_async(msg):
    """
    Async wrapper for logging.info
    
    Args:
        msg: Message to log
    """
    logging.info(msg)

async def commit_with_retry_async(session, max_retries=3):
    """
    Commit a database session with retries on failure (async version).

    Args:
        session: SQLAlchemy AsyncSession
        max_retries: Maximum number of retry attempts

    Returns:
        bool: True if commit succeeded, False otherwise
    """
    for attempt in range(max_retries):
        try:
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Commit attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retrying
    return False

async def get_common_prices_async():
    """
    Gets menu price information from the database (async version).
    No longer loads from JSON files - exclusively uses the database.

    Returns:
        dict: Mapping of item names to price info
    """
    try:
        # Import here to avoid circular imports
        # Need to use an async version of menu_db_store
        from app.utils.menu_db_store_async import menu_db_store_async

        # Get menu data from database
        menu_data = await menu_db_store_async.get_menu_data(force_refresh=True)

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
                "full_name": item.get("name", ""),  # Store original case
            }

            # Also store name fragments for fuzzy matching
            words = item_name.split()
            for word in words:
                if len(word) > 3 and word not in result:  # Only meaningful words
                    result[word] = {
                        "price": price,
                        "reference_handler": ref_handler,
                        "full_name": item.get("name", ""),  # Store original case
                    }

        # Only return the built dictionary if it has items
        if result:
            logging.info(
                f"[MENU-PRICES] Loaded {len(result)} price entries from database"
            )
            return result

        # If we got here, the database is empty
        logging.error("[MENU-PRICES] No menu items found in database")
        raise ValueError("No menu items found in database")

    except Exception as e:
        logging.error(f"[MENU-PRICES] Error loading prices: {e}")
        # Return an empty dictionary as fallback
        return {}