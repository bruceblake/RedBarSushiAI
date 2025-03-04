# app/utils/helpers.py
import logging
import time
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