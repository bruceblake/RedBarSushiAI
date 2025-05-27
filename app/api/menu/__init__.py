"""
Menu API routes for RedBarSushiAI FastAPI application.

This module contains API routers for menu-related operations.
"""

from fastapi import APIRouter

# Import routers as they are created
from app.api.menu.categories import router as categories_router
from app.api.menu.items import router as items_router
from app.api.menu.modifiers import router as modifiers_router
from app.api.menu.variants import router as variants_router
from app.api.menu.search import router as search_router
# from app.api.menu.update import router as update_router

# Create main menu router
menu_router = APIRouter(tags=["Menu"])

# Include sub-routers as they are implemented
menu_router.include_router(categories_router)
menu_router.include_router(items_router)
menu_router.include_router(modifiers_router)
menu_router.include_router(variants_router)
menu_router.include_router(search_router)
# menu_router.include_router(update_router)

# Export the router
__all__ = ["menu_router"]