# app/utils/deliverect/__init__.py
"""
Deliverect API integration module.

This package provides functionality for integrating with the Deliverect API
for restaurant menu data synchronization and order management.
"""

# Authentication
from app.utils.deliverect.auth import (
    get_deliverect_access_token,
    get_deliverect_headers,
)

# Menu processing
from app.utils.deliverect.menu_async import (
    process_deliverect_menu_async as process_deliverect_menu,
)

# Order management
from app.utils.deliverect.orders_async import (
    build_deliverect_order,
    send_order_to_deliverect_async as send_order_to_deliverect,
    get_order_status_async as get_order_status,
    process_order_status_update_async as process_order_status_update,
    generate_order_id,
)

# Location management
from app.utils.deliverect.locations_async import (
    register_new_location_async as register_new_location,
    update_location_status_async as update_location_status,
    get_location_webhook_urls_async as get_location_webhook_urls,
)

# Make sure to maintain the same API as the original module
__all__ = [
    "get_deliverect_access_token",
    "get_deliverect_headers",
    "process_deliverect_menu",
    "build_deliverect_order",
    "send_order_to_deliverect",
    "get_order_status",
    "process_order_status_update",
    "generate_order_id",
    "register_new_location",
    "update_location_status",
    "get_location_webhook_urls",
]