# app/utils/deliverect_async.py
"""
Deliverect API integration module (async version).

This package provides async functionality for integrating with the Deliverect API
for restaurant menu data synchronization and order management.
"""

# Authentication (import from synchronous module as it doesn't use db.Model)
from app.utils.deliverect.auth import (
    get_deliverect_access_token,
    get_deliverect_headers,
)

# Menu processing (import from synchronous module as it doesn't use db.Model)
from app.utils.deliverect.menu import (
    process_deliverect_menu,
)

# Order management (async versions)
from app.utils.deliverect.orders_async import (
    build_deliverect_order,  # Shared with synchronous module (pure function)
    send_order_to_deliverect_async,
    get_order_status_async,
    process_order_status_update_async,
    generate_order_id,  # Shared with synchronous module (pure function)
)

# Location management (these would need async versions if they use location model)
from app.utils.deliverect.locations import (
    register_new_location,
    update_location_status,
    get_location_webhook_urls,
)

# Make sure to maintain the same API as the original module
__all__ = [
    "get_deliverect_access_token",
    "get_deliverect_headers",
    "process_deliverect_menu",
    "build_deliverect_order",
    "send_order_to_deliverect_async",
    "get_order_status_async",
    "process_order_status_update_async",
    "generate_order_id",
    "register_new_location",
    "update_location_status",
    "get_location_webhook_urls",
]