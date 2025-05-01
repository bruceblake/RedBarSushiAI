"""
Database utility functions for the application.
Provides helper functions for common database operations.
"""

import logging
from sqlalchemy import text
from app import db

logger = logging.getLogger(__name__)


def execute_query(query, params=None, fetch=True):
    """
    Execute a database query and return the results.

    Args:
        query: SQL query string
        params: Query parameters (optional)
        fetch: Whether to fetch results (optional, default True)

    Returns:
        Query results if fetch=True, None otherwise
    """
    try:
        with db.engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))

            if fetch:
                return result.fetchall()
            conn.commit()
            return None
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise
