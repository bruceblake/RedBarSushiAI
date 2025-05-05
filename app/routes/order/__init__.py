"""
Order routes for RedBarSushiAI.
This module provides the routes for order taking, modification, confirmation, and checkout.
"""

import logging
from flask import Blueprint

# Create order blueprint
order_bp = Blueprint("order", __name__)

# Configure logger
logger = logging.getLogger(__name__)
logger.info("Initializing order routes blueprint")

# Import all the order route modules
from app.routes.order.utils import *
from app.routes.order.take_order import *
from app.routes.order.confirmation import *
from app.routes.order.modification import *
from app.routes.order.fallbacks import *
from app.routes.order.checkout import *
from app.routes.order.status import *
from app.routes.order.contact import *

# Export the blueprint
__all__ = ['order_bp']