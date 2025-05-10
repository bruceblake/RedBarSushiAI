"""
Database models for menu items, modifiers, and modifier groups.
These models are used to store menu data in a relational database.
"""

import json
import logging
import os
from datetime import datetime
from app import db
from app.models.base import TimestampMixin
from sqlalchemy import event, inspect, Text
from sqlalchemy.ext.mutable import MutableDict

# Set up logger
logger = logging.getLogger(__name__)

# On Render, we know we're using PostgreSQL, so import JSONB directly
from sqlalchemy.dialects.postgresql import JSONB
logger.info("Imported JSONB directly from sqlalchemy.dialects.postgresql")

# Always use JSONB on Render
USE_JSONB = True

# Function to determine if we're using PostgreSQL
def is_postgresql():
    """
    Always returns True on Render environments, otherwise checks dialect.
    We know that Render always uses PostgreSQL.
    """
    # On Render, we're always using PostgreSQL
    if os.environ.get("RENDER") == "true":
        logger.info("Render environment detected, using PostgreSQL")
        return True
    
    try:
        # For local development, try to check dialect
        from app.config import settings
        if hasattr(settings, "DATABASE_URL") and settings.DATABASE_URL:
            if settings.DATABASE_URL.startswith('postgresql'):
                logger.info("PostgreSQL database URL detected")
                return True
        
        # If settings don't help, try to check engine dialect
        try:
            dialect = db.engine.dialect.name
            is_pg = dialect == 'postgresql'
            logger.info(f"Database dialect: {dialect}, using PostgreSQL: {is_pg}")
            return is_pg
        except Exception as inner_e:
            logger.warning(f"Could not determine database dialect from engine: {inner_e}")
            # Try connections
            if db.engine.driver and 'psycopg' in db.engine.driver:
                logger.info("PostgreSQL driver detected in engine")
                return True
    except Exception as e:
        logger.warning(f"Could not determine database dialect from settings: {e}")
    
    # Final fallback for non-Render environments
    logger.warning("Could not conclusively determine database type, defaulting to non-PostgreSQL")
    return False

# Create a JSONB property function
def get_jsonb_column():
    """Get the appropriate column type based on database dialect"""
    # On Render, always use JSONB
    if os.environ.get("RENDER") == "true":
        logger.info("Using PostgreSQL JSONB column for properties (Render environment)")
        return JSONB
    
    # For other environments, check database type
    if is_postgresql():
        logger.info("Using PostgreSQL JSONB column for properties")
        return JSONB
    else:
        logger.info("Using Text column for properties (non-PostgreSQL database)")
        return Text

def get_default_value():
    """Get an appropriate default value for the properties column"""
    # On Render or other PostgreSQL environments, use dict
    if os.environ.get("RENDER") == "true" or is_postgresql():
        return dict
    else:
        # For non-PostgreSQL, use a stringified empty dict
        return lambda: '{}'

# Menu models

class MenuCategory(db.Model, TimestampMixin):
    """Category for menu items."""
    
    __tablename__ = 'menu_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    deliverect_category_id = db.Column(db.String(255), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    
    # Use get_jsonb_column() instead of conditional statement
    properties = db.Column(
        MutableDict.as_mutable(get_jsonb_column()),
        default=get_default_value()
    )
    
    # Relationships
    items = db.relationship('MenuItem', backref='category', lazy='dynamic')
    

class MenuItem(db.Model, TimestampMixin):
    """Menu item model with PLU and availability tracking."""
    
    __tablename__ = 'menu_items'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('menu_categories.id'), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    plu = db.Column(db.String(50), nullable=False, unique=True, index=True)
    deliverect_item_id = db.Column(db.String(255), nullable=True, index=True)
    is_available = db.Column(db.Boolean, default=True)
    is_combo = db.Column(db.Boolean, default=False)
    is_variant = db.Column(db.Boolean, default=False)
    image_url = db.Column(db.String(255), nullable=True)
    snoozed_until = db.Column(db.DateTime, nullable=True)
    
    # Use get_jsonb_column() instead of conditional statement
    properties = db.Column(
        MutableDict.as_mutable(get_jsonb_column()),
        default=get_default_value()
    )
    
    # Relationships through association tables
    modifier_groups = db.relationship(
        'MenuModifierGroup',
        secondary='item_modifier_groups',
        backref=db.backref('items', lazy='dynamic')
    )
    

class MenuModifierGroup(db.Model, TimestampMixin):
    """Group of modifiers with selection constraints."""
    
    __tablename__ = 'menu_modifier_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    deliverect_group_id = db.Column(db.String(255), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    min_selection = db.Column(db.Integer, default=0)
    max_selection = db.Column(db.Integer, default=0)
    multiMax = db.Column(db.Integer, default=1)
    plu = db.Column(db.String(50), nullable=True)
    is_variant_group = db.Column(db.Boolean, default=False)
    
    # Use get_jsonb_column() instead of conditional statement
    properties = db.Column(
        MutableDict.as_mutable(get_jsonb_column()),
        default=get_default_value()
    )
    
    # Relationships through association tables
    modifiers = db.relationship(
        'MenuModifier',
        secondary='group_modifiers',
        backref=db.backref('groups', lazy='dynamic')
    )
    

class MenuModifier(db.Model, TimestampMixin):
    """Modifier for menu items with price impact."""
    
    __tablename__ = 'menu_modifiers'
    
    id = db.Column(db.Integer, primary_key=True)
    modifier_group_id = db.Column(db.Integer, db.ForeignKey('menu_modifier_groups.id'), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    price_change = db.Column(db.Numeric(10, 2), default=0.0)
    plu = db.Column(db.String(50), nullable=False, unique=True, index=True)
    deliverect_modifier_id = db.Column(db.String(255), nullable=True, index=True)
    is_available = db.Column(db.Boolean, default=True)
    snoozed_until = db.Column(db.DateTime, nullable=True)
    
    # Use get_jsonb_column() instead of conditional statement
    properties = db.Column(
        MutableDict.as_mutable(get_jsonb_column()),
        default=get_default_value()
    )
    

# Association table for items to modifier groups
class ItemModifierGroup(db.Model):
    """Association table linking menu items to modifier groups."""
    
    __tablename__ = 'item_modifier_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    modifier_group_id = db.Column(db.Integer, db.ForeignKey('menu_modifier_groups.id', ondelete='CASCADE'), nullable=False)
    

# Association table for groups to modifiers
class GroupModifier(db.Model):
    """Association table linking modifier groups to modifiers."""
    
    __tablename__ = 'group_modifiers'
    
    id = db.Column(db.Integer, primary_key=True)
    modifier_group_id = db.Column(db.Integer, db.ForeignKey('menu_modifier_groups.id', ondelete='CASCADE'), nullable=False)
    modifier_id = db.Column(db.Integer, db.ForeignKey('menu_modifiers.id', ondelete='CASCADE'), nullable=False)
    

class MenuNameVariant(db.Model, TimestampMixin):
    """
    Alternative names for menu items to help with fuzzy matching.
    
    This table stores alternative phrases that customers might use
    to refer to a menu item, helping with natural language matching.
    """
    
    __tablename__ = 'menu_name_variants'
    
    id = db.Column(db.Integer, primary_key=True)
    variant_phrase = db.Column(db.String(255), nullable=False, index=True)
    canonical_name = db.Column(db.String(255), nullable=False)
    target_plu = db.Column(db.String(50), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=True)
    
    # Make variant_phrase lowercase for case-insensitive matching
    @classmethod
    def __declare_last__(cls):
        @event.listens_for(cls, 'before_insert')
        def make_lowercase(mapper, connection, target):
            target.variant_phrase = target.variant_phrase.lower()
            
        @event.listens_for(cls, 'before_update')
        def update_lowercase(mapper, connection, target):
            target.variant_phrase = target.variant_phrase.lower()


# Helper methods for availability checking

def is_item_available(item):
    """Check if a menu item is available."""
    if not item:
        return False
    
    if not getattr(item, 'is_available', True):
        return False
    
    if getattr(item, 'snoozed_until', None):
        now = datetime.now()
        if item.snoozed_until > now:
            return False
    
    return True


def is_modifier_available(modifier):
    """Check if a modifier is available."""
    if not modifier:
        return False
    
    if not getattr(modifier, 'is_available', True):
        return False
    
    if getattr(modifier, 'snoozed_until', None):
        now = datetime.now()
        if modifier.snoozed_until > now:
            return False
    
    return True