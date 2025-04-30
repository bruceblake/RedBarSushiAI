"""
Package for all database models.
Ensures that models are properly importable.
"""

# Import models to make them available when importing the package
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
from app.models import Order, Location