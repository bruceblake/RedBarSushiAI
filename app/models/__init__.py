"""
Package for all database models.
Ensures that models are properly importable.
"""

# Import async models for the FastAPI application
from app.models.order_async import Order, OrderItem, OrderItemModifier, ContactRequest
from app.models.location import Location
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant

# Export all models
__all__ = [
    "Order", "OrderItem", "OrderItemModifier", "ContactRequest",
    "Location",
    "MenuCategory", "MenuItem", "MenuModifier", "MenuModifierGroup", "MenuNameVariant"
]
