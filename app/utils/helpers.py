# app/utils/helpers.py
import logging
import time
from sqlalchemy.exc import OperationalError

def log_info(msg):
    logging.info(msg)

def commit_with_retry(session, max_retries=3):
    for attempt in range(max_retries):
        try:
            session.commit()
            return True
        except OperationalError as e:
            session.rollback()
            logging.error(f"Commit attempt {attempt+1} failed: {e}")
            time.sleep(1)
    return False
