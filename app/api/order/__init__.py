"""
Order API routes for RedBarSushiAI FastAPI application.

This module contains API routers for order-related operations.
"""

from fastapi import APIRouter

# Import routers
from app.api.order.status import router as status_router
from app.api.order.take_order import router as take_order_router
from app.api.order.modification import router as modification_router
# Additional imports will be added as modules are converted
# from app.api.order.checkout import router as checkout_router
# from app.api.order.confirmation import router as confirmation_router
# from app.api.order.contact import router as contact_router

# Create main order router
order_router = APIRouter(tags=["Orders"])

# Include sub-routers
order_router.include_router(status_router)
order_router.include_router(take_order_router)
order_router.include_router(modification_router)
# Additional includes will be added as modules are converted
# order_router.include_router(checkout_router)
# order_router.include_router(confirmation_router)
# order_router.include_router(contact_router)

# Export the router
__all__ = ["order_router"]