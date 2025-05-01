"""
Package for all database models.
Ensures that models are properly importable.
"""

# Import existing models from models.py for convenience
from app.models import Order, Location

# Import menu models from the menu module
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup