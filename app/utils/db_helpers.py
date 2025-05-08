"""
Database helper utilities to ensure JSONB compatibility.
This module provides fallback handling when JSONB is not directly available.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)

def get_jsonb_type():
    """
    Get the JSONB type, providing fallbacks if necessary.
    
    This function tries multiple ways to import JSONB:
    1. From app.db (preferred)
    2. Directly from sqlalchemy.dialects.postgresql
    3. Falling back to Text if not available
    
    Returns:
        JSONB class or Text class as fallback
    """
    try:
        # Try to import from app.db first
        from app.db import JSONB
        logger.info("Using JSONB from app.db")
        return JSONB
    except (ImportError, AttributeError):
        # Try direct import from sqlalchemy
        try:
            from sqlalchemy.dialects.postgresql import JSONB
            logger.info("Using JSONB directly from sqlalchemy.dialects.postgresql")
            return JSONB
        except ImportError:
            # Ultimate fallback to Text
            from sqlalchemy import Text
            logger.warning("JSONB not available, falling back to Text type")
            return Text