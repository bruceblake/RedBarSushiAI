"""
Database module that exports the SQLAlchemy instance.

This module is used to avoid circular imports when accessing the db object
directly from other modules.

It provides safe access to SQLAlchemy objects through proxy functions that 
check for application context availability, making it robust for use in
various scenarios including testing.
"""

from app import db as _db
from flask import current_app, has_app_context
import logging
from typing import Optional, Any
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB

# Configure logging
logger = logging.getLogger(__name__)

# Re-export the SQLAlchemy types that don't require app context
Model = _db.Model
relationship = _db.relationship
Column = _db.Column
Integer = _db.Integer
String = _db.String
Boolean = _db.Boolean
Text = _db.Text
DateTime = _db.DateTime
Float = _db.Float
ForeignKey = _db.ForeignKey
Table = _db.Table
# Import JSONB directly from sqlalchemy.dialects.postgresql
JSONB = PostgresJSONB

# Re-export init_app function
init_app = _db.init_app

# Proxy the underlying db object
db = _db

def get_session():
    """
    Safely get the database session.
    
    This function checks for application context and handles exceptions
    to provide a more robust interface for accessing the session.
    
    Returns:
        SQLAlchemy session object or None if not available
    """
    try:
        if has_app_context():
            return _db.session
        else:
            logger.warning("Attempted to access db.session outside application context")
            return None
    except Exception as e:
        logger.error(f"Error accessing database session: {e}")
        return None

def get_engine():
    """
    Safely get the database engine.
    
    This function checks for application context and handles exceptions
    to provide a more robust interface for accessing the engine.
    
    Returns:
        SQLAlchemy engine object or None if not available
    """
    try:
        if has_app_context():
            return _db.engine
        else:
            logger.warning("Attempted to access db.engine outside application context")
            return None
    except Exception as e:
        logger.error(f"Error accessing database engine: {e}")
        return None

def session_scope():
    """
    Provide a transactional scope around a series of operations.
    
    This context manager ensures that the session is properly closed
    and committed/rolled back as needed.
    
    Yields:
        SQLAlchemy session object
    """
    session = get_session()
    if not session:
        logger.error("Cannot create session scope: No session available")
        return None
    
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Error in session scope: {e}")
        session.rollback()
        raise
    finally:
        session.close()

# Create descriptor classes for safe attribute access
class SessionDescriptor:
    """Descriptor for safely accessing the session property"""
    def __get__(self, obj, objtype=None):
        return get_session()

class EngineDescriptor:
    """Descriptor for safely accessing the engine property"""
    def __get__(self, obj, objtype=None):
        return get_engine()

# Create descriptor instances
session = SessionDescriptor()
engine = EngineDescriptor()

# Export all required attributes and methods
__all__ = [
    'db', 'init_app', 'session', 'engine', 'Model', 'relationship', 
    'Column', 'Integer', 'String', 'Boolean', 'Text', 'DateTime', 
    'Float', 'ForeignKey', 'Table', 'JSONB', 'get_session', 
    'get_engine', 'session_scope'
]