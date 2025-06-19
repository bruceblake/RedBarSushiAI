"""
Helper module for determining the appropriate JSON type based on the database dialect.
"""

import os
import logging
from sqlalchemy import Text
from app.config import settings

logger = logging.getLogger(__name__)

def get_json_type():
    """
    Determine the appropriate JSON column type based on the database dialect.
    
    Returns:
        SQLAlchemy column type for JSON data (JSONB for PostgreSQL, Text for others)
    """
    try:
        # Check if we're in a PostgreSQL environment
        database_url = settings.DATABASE_URL
        is_postgresql = False
        
        # Render environment explicitly uses PostgreSQL
        if os.environ.get("RENDER") == "true":
            is_postgresql = True
            logger.info("Detected Render environment, using PostgreSQL JSONB")
        
        # Check DATABASE_URL from settings
        elif database_url and (
            "postgresql+psycopg2" in database_url or
            database_url.startswith("postgresql://")
        ):
            is_postgresql = True
            logger.info(f"Detected PostgreSQL connection: {database_url[:20]}...")
        
        # If PostgreSQL, use JSONB
        if is_postgresql:
            try:
                from sqlalchemy.dialects.postgresql import JSONB
                logger.info("Using PostgreSQL JSONB type")
                return JSONB
            except ImportError:
                logger.warning("PostgreSQL JSONB import failed, falling back to Text")
                return Text
        else:
            logger.info("Using Text for JSON storage (non-PostgreSQL database)")
            return Text
    except Exception as e:
        logger.warning(f"Error detecting database dialect: {e}. Falling back to Text")
        return Text