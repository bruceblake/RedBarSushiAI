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
        
        # This is just a fallback dictionary used if menu loading fails
        fallback = {
            "veggie burger": {"price": 7.5, "reference_handler": "PLU-01"}, 
            "cheeseburger": {"price": 8.5, "reference_handler": "PLU-02"},
            "hamburger": {"price": 7.0, "reference_handler": "PLU-03"},
            "french fries": {"price": 2.0, "reference_handler": "P-FRS-S-#U#-"},
        }
        
        # Try to load actual prices from menu data
        if os.path.exists(MENU_FILE_PATH):
            with open(MENU_FILE_PATH, 'r') as f:
                menu_data = json.load(f)
                
            # Build a comprehensive price map from actual menu data
            result = {}
            for item in menu_data.get('items', []):
                item_name = item.get('name', '').lower()
                if item_name and 'price' in item:
                    result[item_name] = {
                        "price": item.get('price'),
                        "reference_handler": item.get('reference_handler', '')
                    }
            
            # Only return the built dictionary if it has items
            if result:
                logging.info(f"Loaded {len(result)} items from menu_data.json")
                return result
    except Exception as e:
        logging.error(f"Error loading menu data for common prices: {e}")
    
    # Return fallback prices if menu loading fails
    logging.warning("Using fallback prices instead of menu data")
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