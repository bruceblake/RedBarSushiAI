"""
Menu name variants API routes for RedBarSushiAI FastAPI application.

This module provides API endpoints for managing menu name variants, which map
natural language phrases to canonical item names and PLUs.
"""

import logging
from fastapi import APIRouter

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# All functions related to menu name variants have been removed
# as they were flagged as unused by Vulture.
# This file might be empty or only contain the router instance if it's used elsewhere.
# For now, keeping the router instance in case app.api.menu.__init__.py imports it.
# If the router instance itself is not imported in app.api.menu.__init__.py,
# then this whole file could be deleted.
