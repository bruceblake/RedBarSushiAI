"""
Base model definitions and utility functions for database models.
This module provides the base classes and utilities for all models.

THIS FILE IS BEING MAINTAINED FOR COMPATIBILITY WITH LEGACY FLASK MODELS ONLY.
FOR NEW ASYNC MODELS, USE app/models/base_async.py INSTEAD.
"""

import json
import logging
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

# Configure logging
logger = logging.getLogger(__name__)

# Common utility functions
def to_dict(model):
    """Convert a SQLAlchemy model to a dictionary."""
    result = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)

        # Handle datetimes
        if isinstance(value, datetime):
            value = value.isoformat()

        # Handle JSON fields stored as strings
        if isinstance(value, str) and column.name.endswith("_json"):
            try:
                value = json.loads(value)
            except:
                pass

        result[column.name] = value
    return result

# Mixin classes - using direct SQLAlchemy imports
# instead of db.Column to avoid the db.Model dependency
class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# For backwards compatibility with existing code
try:
    # Import Flask-SQLAlchemy db if available, but catch the error if not
    from app import db
    
    # Forward reference for legacy models
    class Base:
        """
        Placeholder Base class to avoid breaking imports.
        THIS IS NOT A REAL BASE CLASS - it's a compatibility shim.
        
        New code should import Base from app.db_async instead.
        """
        pass
        
    # Register the class to avoid import errors in code that expects Base to be defined
    logger.warning("app.models.base.Base is deprecated - use app.db_async.Base for new models")
except ImportError:
    logger.info("Flask-SQLAlchemy db not available, Base class not defined")
