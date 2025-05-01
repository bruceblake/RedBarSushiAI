"""
Base model definitions and utility functions for database models.
This module provides the base classes and utilities for all models.
"""

import json
from datetime import datetime
from app import db


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


# Mixin classes
class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
