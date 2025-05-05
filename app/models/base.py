"""
Base model definitions and utility functions for database models.
This module provides the base classes and utilities for all models.
"""

import json
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr
from app import db

# Create the base class for all models using Flask-SQLAlchemy's Model
class Base(db.Model):
    """Base model class for all models.
    
    This provides a common base for all models that can be used to create 
    tables with db.create_all() without explicitly passing an engine.
    """
    
    __abstract__ = True
    
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


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
