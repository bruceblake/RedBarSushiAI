# app/utils/helpers.py
import logging
import time
import hashlib
import os
import json
from sqlalchemy.exc import OperationalError

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
            "hamburger": {"price": 8.0, "reference_handler": "BRG-01"},
            "veggie burger": {"price": 7.5, "reference_handler": "BRG-02"}, 
            "cheeseburger": {"price": 8.5, "reference_handler": "BRG-03"},
            "french fries": {"price": 2.0, "reference_handler": "P-FRS-S"},
            "coca cola": {"price": 4.0, "reference_handler": "DRK-01"},
            "diet coke": {"price": 4.0, "reference_handler": "DRK-02"},
        }
        
        # Try to load actual prices from menu data
        if os.path.exists(MENU_FILE_PATH):
            with open(MENU_FILE_PATH, 'r') as f:
                menu_data = json.load(f)
                
            # Build a comprehensive price map from actual menu data
            result = {}
            
            # Process all items with valid names and prices
            for item in menu_data.get('items', []):
                item_name = item.get('name', '').lower()
                if not item_name:
                    continue
                    
                # Ensure we have a valid price
                price = item.get('price')
                if not isinstance(price, (int, float)) or price is None:
                    price = 0.0
                    
                # Extract or generate reference handler
                ref_handler = item.get('reference_handler', '')
                if not ref_handler:
                    ref_handler = generate_consistent_reference_id(item_name)
                    
                # Store the item info by name for exact matching
                result[item_name] = {
                    "price": price,
                    "reference_handler": ref_handler
                }
                
                # Also store name fragments for fuzzy matching
                words = item_name.split()
                for word in words:
                    if len(word) > 3 and word not in result:  # Only meaningful words
                        result[word] = {
                            "price": price,
                            "reference_handler": ref_handler,
                            "full_name": item_name  # Store original name for reference
                        }
            
            # Only return the built dictionary if it has items
            if result:
                logging.info(f"[MENU-PRICES] Loaded {len(result)} price entries from menu data")
                return result
    except Exception as e:
        logging.error(f"[MENU-ERROR] Error loading menu data for prices: {e}")
    
    # Return fallback prices if menu loading fails
    logging.warning("[MENU-FALLBACK] Using hardcoded fallback prices - menu data unavailable")
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
