"""
Database models for menu items, modifiers, and modifier groups.
These models are used to store menu data in a relational database.
"""

import json
from datetime import datetime
from app import db
from app.models.base import TimestampMixin
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict


class MenuItem(db.Model, TimestampMixin):
    """
    Menu item model that maps to a database table.
    Stores menu items with all their properties.
    """
    __tablename__ = "menu_items"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    reference_handler = db.Column(db.String(255), index=True, nullable=True)
    plu = db.Column(db.String(255), index=True, nullable=True)
    price = db.Column(db.Float, nullable=True, default=0.0)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(255), nullable=True)
    parent_id = db.Column(db.String(255), nullable=True)
    
    # Status flags
    available = db.Column(db.Boolean, default=True)
    snoozed = db.Column(db.Boolean, default=False)
    is_category = db.Column(db.Boolean, default=False)
    is_variant = db.Column(db.Boolean, default=False)
    
    # Snooze time settings
    snooze_start = db.Column(db.DateTime, nullable=True)
    snooze_end = db.Column(db.DateTime, nullable=True)
    snooze_until = db.Column(db.DateTime, nullable=True)
    
    # Metadata is now provided by TimestampMixin
    
    # Location tracking
    location_id = db.Column(db.String(36), nullable=True)
    
    # Store additional properties as JSON
    # Use JSONB if PostgreSQL, otherwise fallback to JSON text storage
    try:
        # For PostgreSQL
        properties = db.Column(MutableDict.as_mutable(JSONB), nullable=True, default=dict())
    except:
        # For SQLite or other databases without JSONB
        properties = db.Column(db.Text, nullable=True)
        
    # One-to-many relationship with modifier groups
    modifier_groups = db.relationship(
        'MenuModifierGroup',
        secondary='menu_item_modifiers',
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f"<MenuItem {self.name}>"
    
    def to_dict(self):
        """Convert the menu item to a dictionary for API responses and JSON serialization."""
        result = {
            "id": f"ITEM-{self.id:04d}" if self.id else None,
            "name": self.name,
            "reference_handler": self.reference_handler,
            "plu": self.plu,
            "price": self.price,
            "description": self.description,
            "category": self.category,
            "parentId": self.parent_id,
            "available": self.available,
            "snoozed": self.snoozed,
            "is_category": self.is_category,
            "is_variant": self.is_variant
        }
        
        # Add properties from JSON field
        if self.properties:
            if isinstance(self.properties, str):
                try:
                    props = json.loads(self.properties)
                    result.update(props)
                except:
                    pass
            else:
                # Already a dict
                result.update(self.properties)
                
        # Format dates if present
        if self.snooze_start:
            result["snoozeStart"] = self.snooze_start.isoformat()
        if self.snooze_end:
            result["snoozeEnd"] = self.snooze_end.isoformat()
        if self.snooze_until:
            result["snoozeUntil"] = self.snooze_until.isoformat()
            
        return result
        
    def save(self):
        """Save the menu item to the database."""
        db.session.add(self)
        db.session.commit()
        
    def delete(self):
        """Delete the menu item from the database."""
        db.session.delete(self)
        db.session.commit()
        
    @classmethod
    def from_dict(cls, data):
        """Create a new MenuItem from a dictionary."""
        # Extract base fields
        item = cls(
            name=data.get("name", ""),
            reference_handler=data.get("reference_handler", ""),
            plu=data.get("plu", ""),
            price=data.get("price", 0.0),
            description=data.get("description", ""),
            category=data.get("category", ""),
            parent_id=data.get("parentId", ""),
            available=data.get("available", True),
            snoozed=data.get("snoozed", False),
            is_category=data.get("is_category", False),
            is_variant=data.get("is_variant", False),
            location_id=data.get("location_id")
        )
        
        # Process date fields
        snooze_start = data.get("snoozeStart")
        if snooze_start:
            try:
                item.snooze_start = datetime.fromisoformat(snooze_start.replace("Z", "+00:00"))
            except:
                pass
        
        snooze_end = data.get("snoozeEnd")
        if snooze_end:
            try:
                item.snooze_end = datetime.fromisoformat(snooze_end.replace("Z", "+00:00"))
            except:
                pass
                
        snooze_until = data.get("snoozeUntil")
        if snooze_until:
            try:
                item.snooze_until = datetime.fromisoformat(snooze_until.replace("Z", "+00:00"))
            except:
                pass
                
        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in ['name', 'reference_handler', 'plu', 'price', 'description', 
                          'category', 'parentId', 'available', 'snoozed', 'is_category',
                          'is_variant', 'snoozeStart', 'snoozeEnd', 'snoozeUntil',
                          'location_id', 'id']:
                properties[key] = value
                
        # If we have PostgreSQL with JSONB
        try:
            if hasattr(cls, 'properties') and hasattr(getattr(cls, 'properties'), 'type') and hasattr(getattr(cls, 'properties').type, 'python_type') and getattr(cls, 'properties').type.python_type == dict:
                item.properties = properties
            else:
                # Fallback to JSON text for other databases
                item.properties = json.dumps(properties)
        except (AttributeError, TypeError):
            # If any attribute checks fail, just use JSON as fallback
            item.properties = json.dumps(properties)
            
        return item


class MenuModifier(db.Model, TimestampMixin):
    """
    Menu modifier model that maps to a database table.
    Stores modifiers that can be applied to menu items.
    """
    __tablename__ = "menu_modifiers"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    reference_handler = db.Column(db.String(255), index=True, nullable=True)
    price = db.Column(db.Float, nullable=True, default=0.0)
    
    # Status flags
    available = db.Column(db.Boolean, default=True)
    
    # Metadata is now provided by TimestampMixin
    
    # Location tracking
    location_id = db.Column(db.String(36), nullable=True)
    
    # Store additional properties as JSON
    try:
        # For PostgreSQL
        properties = db.Column(MutableDict.as_mutable(JSONB), nullable=True, default=dict())
    except:
        # For SQLite or other databases without JSONB
        properties = db.Column(db.Text, nullable=True)
        
    def __repr__(self):
        return f"<MenuModifier {self.name}>"
    
    def to_dict(self):
        """Convert the menu modifier to a dictionary for API responses and JSON serialization."""
        result = {
            "id": f"MOD-{self.id:04d}" if self.id else None,
            "name": self.name,
            "reference_handler": self.reference_handler,
            "price": self.price,
            "available": self.available
        }
        
        # Add properties from JSON field
        if self.properties:
            if isinstance(self.properties, str):
                try:
                    props = json.loads(self.properties)
                    result.update(props)
                except:
                    pass
            else:
                # Already a dict
                result.update(self.properties)
                
        return result
        
    def save(self):
        """Save the menu modifier to the database."""
        db.session.add(self)
        db.session.commit()
        
    def delete(self):
        """Delete the menu modifier from the database."""
        db.session.delete(self)
        db.session.commit()
        
    @classmethod
    def from_dict(cls, data):
        """Create a new MenuModifier from a dictionary."""
        # Extract base fields
        modifier = cls(
            name=data.get("name", ""),
            reference_handler=data.get("reference_handler", ""),
            price=data.get("price", 0.0),
            available=data.get("available", True),
            location_id=data.get("location_id")
        )
        
        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in ['name', 'reference_handler', 'price', 'available',
                          'location_id', 'id']:
                properties[key] = value
                
        # If we have PostgreSQL with JSONB
        try:
            if hasattr(cls, 'properties') and hasattr(getattr(cls, 'properties'), 'type') and hasattr(getattr(cls, 'properties').type, 'python_type') and getattr(cls, 'properties').type.python_type == dict:
                modifier.properties = properties
            else:
                # Fallback to JSON text for other databases
                modifier.properties = json.dumps(properties)
        except (AttributeError, TypeError):
            # If any attribute checks fail, just use JSON as fallback
            modifier.properties = json.dumps(properties)
            
        return modifier


class MenuModifierGroup(db.Model, TimestampMixin):
    """
    Menu modifier group model that maps to a database table.
    Stores groups of modifiers that can be applied to menu items.
    """
    __tablename__ = "menu_modifier_groups"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    reference_handler = db.Column(db.String(255), index=True, nullable=True)
    
    # Constraint values
    min_allowed = db.Column(db.Integer, default=0)
    max_allowed = db.Column(db.Integer, default=None)
    multi_max = db.Column(db.Integer, default=1)  # Max quantity per modifier
    
    # Flags
    is_variant_group = db.Column(db.Boolean, default=False)
    
    # Metadata is now provided by TimestampMixin
    
    # Location tracking
    location_id = db.Column(db.String(36), nullable=True)
    
    # Store additional properties as JSON
    try:
        # For PostgreSQL
        properties = db.Column(MutableDict.as_mutable(JSONB), nullable=True, default=dict())
    except:
        # For SQLite or other databases without JSONB
        properties = db.Column(db.Text, nullable=True)
        
    # Many-to-many relationship with modifiers
    modifiers = db.relationship(
        'MenuModifier',
        secondary='menu_modifier_group_items',
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f"<MenuModifierGroup {self.name}>"
    
    def to_dict(self):
        """Convert the menu modifier group to a dictionary for API responses and JSON serialization."""
        result = {
            "id": f"GROUP-{self.id:04d}" if self.id else None,
            "name": self.name,
            "reference_handler": self.reference_handler,
            "min": self.min_allowed,
            "max": self.max_allowed,
            "multiMax": self.multi_max,
            "isVariantGroup": self.is_variant_group,
            "subProducts": [mod.reference_handler for mod in self.modifiers]
        }
        
        # Add properties from JSON field
        if self.properties:
            if isinstance(self.properties, str):
                try:
                    props = json.loads(self.properties)
                    result.update(props)
                except:
                    pass
            else:
                # Already a dict
                result.update(self.properties)
                
        return result
        
    def save(self):
        """Save the menu modifier group to the database."""
        db.session.add(self)
        db.session.commit()
        
    def delete(self):
        """Delete the menu modifier group from the database."""
        db.session.delete(self)
        db.session.commit()
        
    @classmethod
    def from_dict(cls, data):
        """Create a new MenuModifierGroup from a dictionary."""
        # Extract base fields
        group = cls(
            name=data.get("name", ""),
            reference_handler=data.get("reference_handler", ""),
            min_allowed=data.get("min", 0),
            max_allowed=data.get("max"),
            multi_max=data.get("multiMax", 1),
            is_variant_group=data.get("isVariantGroup", False),
            location_id=data.get("location_id")
        )
        
        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in ['name', 'reference_handler', 'min', 'max', 'multiMax',
                          'isVariantGroup', 'location_id', 'id', 'subProducts']:
                properties[key] = value
                
        # If we have PostgreSQL with JSONB
        try:
            if hasattr(cls, 'properties') and hasattr(getattr(cls, 'properties'), 'type') and hasattr(getattr(cls, 'properties').type, 'python_type') and getattr(cls, 'properties').type.python_type == dict:
                group.properties = properties
            else:
                # Fallback to JSON text for other databases
                group.properties = json.dumps(properties)
        except (AttributeError, TypeError):
            # If any attribute checks fail, just use JSON as fallback
            group.properties = json.dumps(properties)
            
        return group


# Association tables for many-to-many relationships with explicit foreign keys
menu_item_modifiers = db.Table('menu_item_modifiers',
    db.Column('menu_item_id', db.Integer, db.ForeignKey('menu_items.id', ondelete='CASCADE'), primary_key=True),
    db.Column('menu_modifier_group_id', db.Integer, db.ForeignKey('menu_modifier_groups.id', ondelete='CASCADE'), primary_key=True)
)

menu_modifier_group_items = db.Table('menu_modifier_group_items',
    db.Column('menu_modifier_group_id', db.Integer, db.ForeignKey('menu_modifier_groups.id', ondelete='CASCADE'), primary_key=True),
    db.Column('menu_modifier_id', db.Integer, db.ForeignKey('menu_modifiers.id', ondelete='CASCADE'), primary_key=True)
)