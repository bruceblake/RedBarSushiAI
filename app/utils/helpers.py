# app/utils/helpers.py
import logging
import time
import hashlib
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
    Returns a dictionary of common menu items with their prices and reference handlers.
    This centralizes the pricing information for common items.
    
    Returns:
        dict: Mapping of item names to price info
    """
    return {
        "veggie burger": {"price": 7.5, "reference_handler": "FB-VEG01"},
        "cheeseburger": {"price": 8.5, "reference_handler": "FB-CHSBGR"},
        "hamburger": {"price": 7.0, "reference_handler": "FB-HMBGR"},
        "french fries": {"price": 2.0, "reference_handler": "FB-FRFRY"},
        "curly fries": {"price": 2.0, "reference_handler": "FB-CRLFRY"},
        "seasoned fries": {"price": 2.5, "reference_handler": "FB-SESFRY"},
        "coca cola": {"price": 4.0, "reference_handler": "FB-COKE"},
        "diet coke": {"price": 4.0, "reference_handler": "FB-DIECOK"},
        "ginger beer": {"price": 4.0, "reference_handler": "FB-GINGBR"},
        "water": {"price": 2.0, "reference_handler": "FB-WATER"},
        "california roll": {"price": 9.5, "reference_handler": "FB-CALROL"},
        "spicy tuna roll": {"price": 11.0, "reference_handler": "FB-SPCTRL"},
        "philadelphia roll": {"price": 10.5, "reference_handler": "FB-PHIROL"},
        "salmon roll": {"price": 10.0, "reference_handler": "FB-SALROL"},
        "edamame": {"price": 4.0, "reference_handler": "FB-EDAMAM"},
        "miso soup": {"price": 3.5, "reference_handler": "FB-MISOSUP"}
    }

def generate_consistent_reference_id(item_name):
    """
    Generate a consistent reference ID based on item name.
    
    Args:
        item_name: The name of the item
        
    Returns:
        str: A consistent reference ID
    """
    return f"REF-{hashlib.md5(item_name.lower().encode()).hexdigest()[:8]}"