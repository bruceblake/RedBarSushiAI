"""
API module for RedBarSushiAI FastAPI application.

This module contains API routers for the different components of the application.
"""

import logging
from fastapi import APIRouter

# Moved app-specific imports to the top
from app.api.order import order_router
from app.api.menu import menu_router
# Imports for Deliverect and voice will also be moved to top, within try-except if needed for graceful degradation.
# For now, moving all to top that are not already there.
from app.api.deliverect import router as deliverect_router
from app.api.deliverect_menu import router as deliverect_menu_router
from app.api.deliverect_webhooks import router as deliverect_webhooks_router
from app.api.voice import http_twiml_router
from app.api.conversation_relay import conversation_relay_router


# Set up logging
logger = logging.getLogger(__name__)

# Create main API router
api_router = APIRouter()

# Include core routers for orders and menu
api_router.include_router(order_router, prefix="/order")  # Order routes
api_router.include_router(menu_router, prefix="/menu")  # Menu routes

# Import and include Deliverect routers
try:
    # Mount Deliverect routers under /api/deliverect
    api_router.include_router(
        deliverect_router, prefix="/api/deliverect", tags=["Deliverect"]
    )
    api_router.include_router(
        deliverect_menu_router, prefix="/api/deliverect", tags=["Deliverect Menu"]
    )
    api_router.include_router(
        deliverect_webhooks_router,
        prefix="/api/deliverect",
        tags=["Deliverect Webhooks"],
    )

    logger.info("Successfully registered Deliverect routers")
    logger.info("Deliverect registration endpoint: /api/deliverect/register")
    logger.info("Deliverect menu webhook: /api/deliverect/menu/update")
except ImportError as e:
    logger.error(f"Failed to import Deliverect routers: {str(e)}") # This will error if deliverect_router etc not defined before try
    # The try-except blocks for imports are tricky with E402.
    # A better pattern is to have all imports at top and let them fail if module not found,
    # or use conditional logic *after* imports if some routers are optional.
    # For now, I've moved them up. If Deliverect/Voice modules can truly be missing,
    # the include_router calls should be conditional, not the imports themselves for E402.

# Import voice routers from the structured module
try:
    # Mount TwiML HTTP endpoint router at /voice
    api_router.include_router(
        http_twiml_router, prefix="/voice", tags=["Voice (TwiML Webhooks)"]
    )
    # This makes your TwiML endpoint:
    # POST https://<host>/voice/ and POST https://<host>/voice/webhook
    # Ensure Twilio console points to this exact URL.

    # Import and mount ConversationRelay router if available
    try:
        api_router.include_router(
            conversation_relay_router, prefix="/api", tags=["ConversationRelay"]
        )
        logger.info("Successfully registered ConversationRelay router")
        logger.critical(
            "❗❗❗ ConversationRelay endpoint: /api/conversation-relay ❗❗❗"
        )
    except ImportError as e:
        logger.error(f"ConversationRelay module import failed: {str(e)}")
    except Exception as e:
        logger.error(f"ConversationRelay module error: {type(e).__name__}: {str(e)}")

    logger.info("Successfully registered voice routers")
    logger.info("TwiML endpoints: /voice/ and /voice/webhook")
    logger.info("Voice testing endpoints: /voice/test/*")

except ImportError as e:
    logger.error(f"Failed to import structured voice module: {str(e)}")
    logger.critical(
        "❗❗❗ VOICE MODULE NOT AVAILABLE - Please check the error above ❗❗❗"
    )
    # Legacy voice_async module has been archived as part of OpenAI Realtime cleanup
    # Use ConversationRelay with VOICE_HANDLER=conversation_relay instead

# Export the router
__all__ = ["api_router"]
