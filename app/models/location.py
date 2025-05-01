"""
Location model for storing location-specific data.
"""

import json
from datetime import datetime
from app import db
from app.models.base import TimestampMixin

class Location(db.Model, TimestampMixin):
    """
    Location model for multi-location support.
    Each location can have different settings and credentials.
    """
    __tablename__ = "location"
    
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(
        db.String(20), default="inactive"
    )  # registered, active, inactive
    webhook_base = db.Column(db.String(255), nullable=True)
    api_key = db.Column(db.String(255), nullable=True)
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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        return result
    
    @staticmethod
    def get_active_locations():
        """Get all active locations."""
        return Location.query.filter_by(status="active").all()
        
    @staticmethod
    def get_by_id(location_id):
        """Get location by ID with error handling."""
        try:
            return Location.query.filter_by(id=location_id).first()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error fetching location {location_id}: {e}")
            return None