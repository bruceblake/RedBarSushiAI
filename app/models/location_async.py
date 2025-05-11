"""
Location model for storing location-specific data.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship

from app.db_async import Base
from app.models.base_async import TimestampMixin

class Location(Base, TimestampMixin):
    """
    Location model for multi-location support.
    Each location can have different settings and credentials.
    """

    __tablename__ = "location"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default="inactive")  # registered, active, inactive
    webhook_base = Column(String(255), nullable=True)
    api_key = Column(String(255), nullable=True)
    # tax_rate removed temporarily to match existing schema

    def __repr__(self):
        return f"<Location {self.id} - {self.name} - {self.status}>"

    def to_dict(self):
        """Convert location to dictionary for API responses."""
        result = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "webhook_base": self.webhook_base,
            # tax_rate removed from response
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return result