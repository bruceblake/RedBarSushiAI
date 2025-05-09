"""
Base model for SQLAlchemy async ORM models.

This module provides base classes and mixins for the SQLAlchemy ORM models
using the async SQLAlchemy API.
"""

import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Column, Integer, DateTime, func, inspect
from sqlalchemy.ext.declarative import declared_attr

from app.db_async import Base

class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps to a model.
    
    This mixin adds created_at and updated_at columns to a model,
    which are automatically set when a record is created or updated.
    """
    
    @declared_attr
    def created_at(cls):
        """Column to track when a record was created."""
        return Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
        
    @declared_attr
    def updated_at(cls):
        """Column to track when a record was last updated."""
        return Column(
            DateTime, 
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow, 
            nullable=False
        )

class BaseModel(Base, TimestampMixin):
    """
    Base class for all models in the application.
    
    This class provides common functionality for all models, including:
    - Primary key column
    - Timestamp tracking
    - Serialization to dictionary
    """
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        return {
            column.key: getattr(self, column.key)
            for column in inspect(self.__class__).columns
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """
        Create a model instance from a dictionary.
        
        Args:
            data: Dictionary containing model attributes
            
        Returns:
            BaseModel: A new model instance
        """
        return cls(**{
            k: v for k, v in data.items() 
            if k in inspect(cls).columns.keys()
        })