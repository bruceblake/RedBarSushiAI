"""
Database models for menu items, modifiers, and modifier groups.
These models are used to store menu data in a relational database.
"""

import json
import logging
from datetime import datetime
from app import db
from app.models.base import TimestampMixin
from sqlalchemy import event, inspect, Text
from sqlalchemy.ext.mutable import MutableDict

# Set up logger
logger = logging.getLogger(__name__)

# Safely import JSONB with fallback
try:
    from sqlalchemy.dialects.postgresql import JSONB
    logger.info("Imported JSONB directly from sqlalchemy.dialects.postgresql")
except ImportError:
    # If JSONB is not available, use our helper
    try:
        from app.utils.db_helpers import get_jsonb_type
        JSONB = get_jsonb_type()
        logger.info(f"Using JSONB from db_helpers: {JSONB.__name__}")
    except ImportError:
        # Ultimate fallback
        logger.warning("Failed to import JSONB, using Text as fallback")
        JSONB = Text

# Default to JSON text storage
USE_JSONB = False

# Function to determine if we're using PostgreSQL
def is_postgresql():
    try:
        # Try to determine if we're using PostgreSQL
        dialect = db.engine.dialect.name
        return dialect == 'postgresql'
    except Exception as e:
        logger.warning(f"Could not determine database dialect: {e}")
        return False

# Create a JSONB property function
def get_jsonb_column():
    """Get the appropriate column type based on database dialect"""
    if is_postgresql():
        logger.info("Using PostgreSQL JSONB for properties column")
        return MutableDict.as_mutable(JSONB)
    else:
        logger.info("Using Text for properties column (non-PostgreSQL database)")
        return Text

# Function to get the appropriate default value
def get_default_value():
    """Get the appropriate default value based on database dialect"""
    if is_postgresql():
        return dict
    else:
        return lambda: '{}'


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
    snoozed_until = db.Column(db.DateTime, nullable=True)

    # Metadata is now provided by TimestampMixin

    # Location tracking
    location_id = db.Column(db.String(36), nullable=True)

    # Store additional properties as JSON
    properties = db.Column(
        get_jsonb_column(),
        nullable=True,
        default=get_default_value()
    )

    # One-to-many relationship with modifier groups
    modifier_groups = db.relationship(
        "MenuModifierGroup", secondary="menu_item_modifiers", lazy="dynamic"
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
            "is_variant": self.is_variant,
        }

        # Add properties from JSON field
        if self.properties:
            try:
                # Handle string or dict properties correctly
                if isinstance(self.properties, str):
                    props = json.loads(self.properties)
                    result.update(props)
                elif isinstance(self.properties, dict):
                    # Already a dict (JSONB)
                    result.update(self.properties)
                else:
                    # Log for debugging
                    logger.warning(f"Unhandled properties type: {type(self.properties)}")
            except Exception as e:
                logger.error(f"Error processing properties in to_dict: {e}")

        # Format dates if present
        if self.snooze_start:
            result["snoozeStart"] = self.snooze_start.isoformat()
        if self.snooze_end:
            result["snoozeEnd"] = self.snooze_end.isoformat()
        if self.snoozed_until:
            result["snoozeUntil"] = self.snoozed_until.isoformat()

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
            location_id=data.get("location_id"),
        )

        # Process date fields
        snooze_start = data.get("snoozeStart")
        if snooze_start:
            try:
                item.snooze_start = datetime.fromisoformat(
                    snooze_start.replace("Z", "+00:00")
                )
            except:
                pass

        snooze_end = data.get("snoozeEnd")
        if snooze_end:
            try:
                item.snooze_end = datetime.fromisoformat(
                    snooze_end.replace("Z", "+00:00")
                )
            except:
                pass

        snooze_until = data.get("snoozeUntil")
        if snooze_until:
            try:
                item.snoozed_until = datetime.fromisoformat(
                    snooze_until.replace("Z", "+00:00")
                )
            except:
                pass

        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in [
                "name",
                "reference_handler",
                "plu",
                "price",
                "description",
                "category",
                "parentId",
                "available",
                "snoozed",
                "is_category",
                "is_variant",
                "snoozeStart",
                "snoozeEnd",
                "snoozeUntil",
                "location_id",
                "id",
            ]:
                properties[key] = value

        # Set properties based on database dialect
        if is_postgresql():
            # Use dict directly for JSONB
            item.properties = properties
        else:
            # Use JSON string for text column
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
    snoozed_until = db.Column(db.DateTime, nullable=True)

    # Metadata is now provided by TimestampMixin

    # Location tracking
    location_id = db.Column(db.String(36), nullable=True)

    # Store additional properties as JSON
    properties = db.Column(
        get_jsonb_column(),
        nullable=True,
        default=get_default_value()
    )

    def __repr__(self):
        return f"<MenuModifier {self.name}>"

    def to_dict(self):
        """Convert the menu modifier to a dictionary for API responses and JSON serialization."""
        result = {
            "id": f"MOD-{self.id:04d}" if self.id else None,
            "name": self.name,
            "reference_handler": self.reference_handler,
            "price": self.price,
            "available": self.available,
        }
        
        # Format dates if present
        if self.snoozed_until:
            result["snoozeUntil"] = self.snoozed_until.isoformat()

        # Add properties from JSON field
        if self.properties:
            try:
                # Handle string or dict properties correctly
                if isinstance(self.properties, str):
                    props = json.loads(self.properties)
                    result.update(props)
                elif isinstance(self.properties, dict):
                    # Already a dict (JSONB)
                    result.update(self.properties)
                else:
                    # Log for debugging
                    logger.warning(f"Unhandled properties type: {type(self.properties)}")
            except Exception as e:
                logger.error(f"Error processing properties in to_dict: {e}")

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
            location_id=data.get("location_id"),
        )
        
        # Process date fields
        snooze_until = data.get("snoozeUntil")
        if snooze_until:
            try:
                modifier.snoozed_until = datetime.fromisoformat(
                    snooze_until.replace("Z", "+00:00")
                )
            except:
                pass

        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in [
                "name",
                "reference_handler",
                "price",
                "available",
                "location_id",
                "id",
                "snoozeUntil",
            ]:
                properties[key] = value

        # Set properties based on database dialect
        if is_postgresql():
            # Use dict directly for JSONB
            modifier.properties = properties
        else:
            # Use JSON string for text column
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
    properties = db.Column(
        get_jsonb_column(),
        nullable=True,
        default=get_default_value()
    )

    # Many-to-many relationship with modifiers
    modifiers = db.relationship(
        "MenuModifier", secondary="menu_modifier_group_items", lazy="dynamic"
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
            "subProducts": [mod.reference_handler for mod in self.modifiers],
        }

        # Add properties from JSON field
        if self.properties:
            try:
                # Handle string or dict properties correctly
                if isinstance(self.properties, str):
                    props = json.loads(self.properties)
                    result.update(props)
                elif isinstance(self.properties, dict):
                    # Already a dict (JSONB)
                    result.update(self.properties)
                else:
                    # Log for debugging
                    logger.warning(f"Unhandled properties type: {type(self.properties)}")
            except Exception as e:
                logger.error(f"Error processing properties in to_dict: {e}")

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
            location_id=data.get("location_id"),
        )

        # Store additional properties
        properties = {}
        # Copy all other fields that aren't in the model columns
        for key, value in data.items():
            if key not in [
                "name",
                "reference_handler",
                "min",
                "max",
                "multiMax",
                "isVariantGroup",
                "location_id",
                "id",
                "subProducts",
            ]:
                properties[key] = value

        # Set properties based on database dialect
        if is_postgresql():
            # Use dict directly for JSONB
            group.properties = properties
        else:
            # Use JSON string for text column
            group.properties = json.dumps(properties)

        return group


# Association tables for many-to-many relationships with explicit foreign keys
menu_item_modifiers = db.Table(
    "menu_item_modifiers",
    db.Column(
        "menu_item_id",
        db.Integer,
        db.ForeignKey("menu_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "menu_modifier_group_id",
        db.Integer,
        db.ForeignKey("menu_modifier_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

menu_modifier_group_items = db.Table(
    "menu_modifier_group_items",
    db.Column(
        "menu_modifier_group_id",
        db.Integer,
        db.ForeignKey("menu_modifier_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "menu_modifier_id",
        db.Integer,
        db.ForeignKey("menu_modifiers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
