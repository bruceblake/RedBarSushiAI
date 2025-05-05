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

# Define module-level variables that are needed by other modules
# This includes channel_status which starts as active (1)
channel_status = 1

# Define the __all__ list for proper exports
__all__ = [
    # Blueprint
    'order_bp',
    
    # Global variables
    'channel_status',
    
    # Status functions
    'check_order_status',
    'update_order_status',
    'get_status_text',
    'send_status_notification',
    
    # Order taking functions
    'take_order',
    'process_order',
    
    # Confirmation functions
    'confirm_order',
    'process_confirmation',
    
    # Checkout functions
    'checkout',
    'complete_order',
    
    # Modification functions
    'modify_order',
    
    # Contact functions
    'request_callback',
    
]

# After defining blueprints and variables, import all the submodules
# This ensures that all route decorators will be processed
from app.routes.order.utils import *
from app.routes.order.take_order import *
from app.routes.order.confirmation import *
from app.routes.order.modification import *
from app.routes.order.checkout import *
from app.routes.order.status import *
from app.routes.order.contact import *

# Update channel_status from status.py (if it defines a different value)
# This allows the status module to set a different initial value if needed
from app.routes.order.status import channel_status as status_channel_status
if status_channel_status != 1:  # Only update if different from default
    channel_status = status_channel_status