"""
Package for all database models.
Ensures that models are properly importable.
"""

# Import models directly from their modules
from app.models.order import Order
from app.models.location import Location
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
