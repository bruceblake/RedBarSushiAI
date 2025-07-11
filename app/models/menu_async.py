"""
SQLAlchemy async models for menu items, modifiers, and modifier groups.

These models are used to store menu data in a relational database.
The models use SQLAlchemy 2.0's async features with the async Base class.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, Table, Numeric
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship, backref
from sqlalchemy import text, event, inspect

from app.db_async import Base
from app.models.base_async import BaseModel

# Set up logger
logger = logging.getLogger(__name__)

# Safely import JSONB with fallback
try:
    from sqlalchemy.dialects.postgresql import JSONB
    logger.info("Imported JSONB directly from sqlalchemy.dialects.postgresql")
except ImportError:
    # If JSONB is not available, use our helper
    JSONB = Text
    logger.warning("Failed to import JSONB, using Text as fallback")

# Helper function to safely process properties
def sanitize_properties(props: Union[Dict[str, Any], str, None]) -> Union[Dict[str, Any], str]:
    """
    Sanitize properties to ensure they are JSON-serializable.
    Handles common serialization issues like datetime objects.
    
    Args:
        props: The properties object to sanitize (dict, string, or None)
        
    Returns:
        Either a dict (for JSONB) or a JSON string (for Text)
    """
    # If None, return empty dict/string based on dialect
    if props is None:
        return {}
        
    # If string, ensure it's valid JSON
    if isinstance(props, str):
        try:
            # Validate by parsing
            json.loads(props)
            return props
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON string in properties: {e}")
            return '{}'
    
    # For dictionaries, ensure all values are serializable
    if isinstance(props, dict):
        sanitized = {}
        for k, v in props.items():
            # Handle non-serializable types
            if isinstance(v, (datetime, datetime.date)):
                sanitized[k] = v.isoformat()
            elif hasattr(v, '__dict__'):  # Handle custom objects
                sanitized[k] = str(v)
            elif v is None or isinstance(v, (str, int, float, bool, list, dict)):
                sanitized[k] = v
            else:
                # For other types, convert to string
                sanitized[k] = str(v)
        return sanitized
    
    # For other types, convert to string representation
    return str(props)

# Association table for items to modifier groups
item_modifier_group = Table(
    'item_modifier_group',
    Base.metadata,
    Column('menu_item_id', Integer, ForeignKey('menu_items.id'), primary_key=True),
    Column('modifier_group_id', Integer, ForeignKey('modifier_groups.id'), primary_key=True)
)

# Association table for modifier groups to modifiers
group_modifier = Table(
    'group_modifier',
    Base.metadata,
    Column('modifier_group_id', Integer, ForeignKey('modifier_groups.id'), primary_key=True),
    Column('menu_modifier_id', Integer, ForeignKey('menu_modifiers.id'), primary_key=True)
)

class MenuNameVariant(BaseModel):
    """
    Model for menu item name variants.
    
    This model stores different ways an item might be referred to,
    allowing for natural language matching of menu items.
    """
    
    __tablename__ = 'menu_name_variants'
    
    variant_phrase = Column(String(255), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    target_plu = Column(String(255), nullable=False, index=True)
    score = Column(Float, default=1.0)
    properties = Column(MutableDict.as_mutable(JSONB), default=dict)
    
    def __repr__(self):
        return f"<MenuNameVariant {self.variant_phrase} -> {self.canonical_name} (PLU: {self.target_plu})>"
    
    def to_dict(self):
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Sanitize properties
        if hasattr(self, 'properties'):
            result['properties'] = sanitize_properties(self.properties)
            
        return result

class MenuCategory(BaseModel):
    """
    Model for menu categories.
    
    This model represents a category of menu items, such as "Appetizers" or "Sushi Rolls".
    """
    
    __tablename__ = 'menu_categories'
    
    deliverect_category_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location_id = Column(String(255), nullable=True, index=True)
    order_index = Column(Integer, default=0)
    parent_id = Column(Integer, ForeignKey('menu_categories.id'), nullable=True)
    properties = Column(MutableDict.as_mutable(JSONB), default=dict)
    
    # Relationships
    items = relationship("MenuItem", back_populates="category")
    sub_categories = relationship("MenuCategory", 
                                 backref=backref("parent", remote_side="MenuCategory.id"),
                                 cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MenuCategory {self.name}>"
    
    def to_dict(self):
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Don't access relationships to avoid lazy loading issues
        # Items and sub_categories can be added later if needed
        
        # Sanitize properties
        if hasattr(self, 'properties'):
            result['properties'] = sanitize_properties(self.properties)
            
        return result

class MenuModifierGroup(BaseModel):
    """
    Model for menu modifier groups.
    
    This model represents a group of modifiers, such as "Toppings" or "Spice Level".
    """
    
    __tablename__ = 'modifier_groups'
    
    deliverect_group_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    min_selection = Column(Integer, default=0)
    max_selection = Column(Integer, default=0)
    multiMax = Column(Integer, default=0)
    plu = Column(String(255), nullable=True, index=True)
    location_id = Column(String(255), nullable=True, index=True)
    is_variant_group = Column(Boolean, default=False)
    properties = Column(MutableDict.as_mutable(JSONB), default=dict)
    
    # Relationships
    modifiers = relationship(
        "MenuModifier",
        secondary=group_modifier,
        back_populates="groups"
    )
    items = relationship(
        "MenuItem", 
        secondary=item_modifier_group,
        back_populates="modifier_groups"
    )
    
    # The snoozed_until column (datetime when the item will be available again)
    snoozed_until = Column(DateTime, nullable=True)
    
    # Backward compatibility property
    @property
    def snooze_until(self):
        return self.snoozed_until
        
    @snooze_until.setter
    def snooze_until(self, value):
        self.snoozed_until = value
    
    def __repr__(self):
        return f"<MenuModifierGroup {self.name}>"
    
    def to_dict(self):
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Don't access relationships to avoid lazy loading issues
        # Modifiers can be added later if needed
        
        # Sanitize properties
        if hasattr(self, 'properties'):
            result['properties'] = sanitize_properties(self.properties)
            
        return result

class MenuModifier(BaseModel):
    """
    Model for menu modifiers.
    
    This model represents a modifier for a menu item, such as "Extra Wasabi" or "No Rice".
    """
    
    __tablename__ = 'menu_modifiers'
    
    deliverect_modifier_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    price_change = Column(Numeric(10, 2), default=0.0)
    plu = Column(String(255), nullable=True, index=True)
    location_id = Column(String(255), nullable=True, index=True)
    is_available = Column(Boolean, default=True)
    properties = Column(MutableDict.as_mutable(JSONB), default=dict)
    
    # Relationships
    groups = relationship(
        "MenuModifierGroup",
        secondary=group_modifier,
        back_populates="modifiers"
    )
    
    # The snoozed_until column (datetime when the item will be available again)
    snoozed_until = Column(DateTime, nullable=True)
    
    # Backward compatibility property
    @property
    def snooze_until(self):
        return self.snoozed_until
        
    @snooze_until.setter
    def snooze_until(self, value):
        self.snoozed_until = value
    
    def __repr__(self):
        return f"<MenuModifier {self.name}>"
    
    def to_dict(self):
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Convert Decimal price_change to float for JSON serialization and calculations
        if 'price_change' in result and result['price_change'] is not None:
            result['price_change'] = float(result['price_change'])
        
        # Sanitize properties
        if hasattr(self, 'properties'):
            result['properties'] = sanitize_properties(self.properties)
            
        return result

class MenuItem(BaseModel):
    """
    Model for menu items.
    
    This model represents a menu item, such as "California Roll" or "Miso Soup".
    """
    
    __tablename__ = 'menu_items'
    
    deliverect_item_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), default=0.0)
    plu = Column(String(255), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey('menu_categories.id'), nullable=True)
    location_id = Column(String(255), nullable=True, index=True)
    image_url = Column(String(1024), nullable=True)
    is_available = Column(Boolean, default=True)
    is_combo = Column(Boolean, default=False)
    is_variant = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    properties = Column(MutableDict.as_mutable(JSONB), default=dict)
    
    # Relationships
    category = relationship("MenuCategory", back_populates="items")
    modifier_groups = relationship(
        "MenuModifierGroup",
        secondary=item_modifier_group,
        back_populates="items"
    )
    
    # The snoozed_until column (datetime when the item will be available again)
    snoozed_until = Column(DateTime, nullable=True)
    
    # Backward compatibility property
    @property
    def snooze_until(self):
        return self.snoozed_until
        
    @snooze_until.setter
    def snooze_until(self, value):
        self.snoozed_until = value
    
    def __repr__(self):
        return f"<MenuItem {self.name}>"
    
    def to_dict(self):
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Convert Decimal price to float for JSON serialization and calculations
        if 'price' in result and result['price'] is not None:
            result['price'] = float(result['price'])
        
        # Don't access relationships to avoid lazy loading issues
        # Category name can be added later if needed
        
        # Sanitize properties
        if hasattr(self, 'properties'):
            result['properties'] = sanitize_properties(self.properties)
            
        return result