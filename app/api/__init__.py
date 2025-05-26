"""
API module for RedBarSushiAI FastAPI application.

This module contains API routers for the different components of the application.
"""

import logging
from fastapi import APIRouter

# Set up logging
logger = logging.getLogger(__name__)

# Create main API router
api_router = APIRouter()

# Import order and menu routers
from app.api.order import order_router
from app.api.menu import menu_router

# Include core routers for orders and menu
api_router.include_router(order_router, prefix="/order")  # Order routes
api_router.include_router(menu_router, prefix="/menu")  # Menu routes

# Import and include Deliverect routers
try:
    from app.api.deliverect import router as deliverect_router
    from app.api.deliverect_menu import router as deliverect_menu_router
    from app.api.deliverect_webhooks import router as deliverect_webhooks_router
    
    # Mount Deliverect routers under /api/deliverect
    api_router.include_router(deliverect_router, prefix="/api/deliverect", tags=["Deliverect"])
    api_router.include_router(deliverect_menu_router, prefix="/api/deliverect", tags=["Deliverect Menu"])
    api_router.include_router(deliverect_webhooks_router, prefix="/api/deliverect", tags=["Deliverect Webhooks"])
    
    logger.info("Successfully registered Deliverect routers")
    logger.info("Deliverect registration endpoint: /api/deliverect/register")
    logger.info("Deliverect menu webhook: /api/deliverect/menu/update")
except ImportError as e:
    logger.error(f"Failed to import Deliverect routers: {str(e)}")

# Import voice routers from the structured module
try:
    from app.api.voice import http_twiml_router, testing_router
    
    # Mount TwiML HTTP endpoint router at /voice
    api_router.include_router(http_twiml_router, prefix="/voice", tags=["Voice (TwiML Webhooks)"])
    # This makes your TwiML endpoint:
    # POST https://<host>/voice/ and POST https://<host>/voice/webhook
    # Ensure Twilio console points to this exact URL.
    
    # Mount testing endpoints
    api_router.include_router(testing_router, prefix="/voice/test", tags=["Voice Testing"])
    
    # Import and mount ConversationRelay router if available
    try:
        from app.api.conversation_relay import conversation_relay_router
        api_router.include_router(conversation_relay_router, prefix="/api", tags=["ConversationRelay"])
        logger.info("Successfully registered ConversationRelay router")
        logger.critical("❗❗❗ ConversationRelay endpoint: /api/conversation-relay ❗❗❗")
    except ImportError as e:
        logger.error(f"ConversationRelay module import failed: {str(e)}")
    except Exception as e:
        logger.error(f"ConversationRelay module error: {type(e).__name__}: {str(e)}")
    
    logger.info("Successfully registered voice routers")
    logger.info("TwiML endpoints: /voice/ and /voice/webhook")
    logger.info("Voice testing endpoints: /voice/test/*")
    
except ImportError as e:
    logger.error(f"Failed to import structured voice module: {str(e)}")
    logger.critical("❗❗❗ VOICE MODULE NOT AVAILABLE - Please check the error above ❗❗❗")
    # Legacy voice_async module has been archived as part of OpenAI Realtime cleanup
    # Use ConversationRelay with VOICE_HANDLER=conversation_relay instead

# Always add Debug routes to inspect the routing
debug_router = APIRouter(tags=["Debug"])

@debug_router.get("/debug-routes")
async def debug_routes():
    """Debug endpoint to list all routes from api_router."""
    from fastapi.routing import APIRoute
    from starlette.routing import WebSocketRoute
    
    def get_route_info(route):
        if isinstance(route, APIRoute):
            return {
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if route.methods else [],
                "endpoint": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
            }
        elif isinstance(route, WebSocketRoute):
            return {
                "path": route.path,
                "name": route.name,
                "endpoint": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
            }
        return {
            "path": getattr(route, "path", "unknown"),
            "type": route.__class__.__name__
        }
    
    # Get routes from API router
    routes = []
    for route in api_router.routes:
        if hasattr(route, 'routes'):  # This is a sub-router
            prefix = getattr(route, 'prefix', '')
            for subroute in route.routes:
                route_info = get_route_info(subroute)
                route_info['path'] = prefix + route_info['path']
                routes.append(route_info)
        else:
            routes.append(get_route_info(route))
    
    return {
        "routes": routes,
        "count": len(routes)
    }

api_router.include_router(debug_router)

# Export the router
__all__ = ["api_router"]