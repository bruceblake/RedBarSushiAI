"""
Main FastAPI application module for RedBarSushiAI.

This module contains the FastAPI application instance and serves as the entry point
for the application when running with ASGI servers like Uvicorn.
"""

import os
import logging
import sys
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

from app.config import settings

# Configure logging
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Configure environment variables
BASE_URL = os.environ.get("BASE_URL", "https://redbarsushiai.onrender.com")
os.environ["BASE_URL"] = BASE_URL  # Ensure it's set for other modules

# If running on Render, set the environment variable
if os.environ.get("RENDER_SERVICE_ID"):
    os.environ["RENDER"] = "true"
    logger.info("Running on Render platform")

# Configure headless mode for server environments
is_render = os.environ.get("RENDER") == "true"
force_headless = is_render or os.environ.get("FORCE_HEADLESS") == "true"

if force_headless or os.environ.get("X11_SETUP_SUCCESS") != "true":
    # Headless mode (recommended for production)
    os.environ["PYNPUT_HEADLESS"] = "1"
    os.environ["NO_X11"] = "1"
    os.environ["HEADLESS"] = "1"
    os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

    # Unset DISPLAY to prevent X11 connection attempts
    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]

    logger.info("Headless mode active (no X11 needed)")
else:
    # X11 mode - only for development with GUI components
    # This branch should not be used in production
    logger.warning("X11 mode active - not recommended for production")
    
    # Use the working display provided by the startup script
    if "DISPLAY" in os.environ and os.environ["DISPLAY"]:
        logger.info(f"Using provided X display: {os.environ['DISPLAY']}")
    else:
        # Default to no display
        logger.warning("No display set, using headless mode instead")
        os.environ["PYNPUT_HEADLESS"] = "1"
        os.environ["NO_X11"] = "1"
        os.environ["HEADLESS"] = "1"
        os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

# Enhanced logging setup
try:
    from app.utils.enhanced_logging import initialize_logging
    log_dir = initialize_logging()
    logger.info(f"Enhanced logging system initialized, logs directory: {log_dir}")
except ImportError:
    # Fall back to basic logging if enhanced logging isn't available
    logger.warning("Enhanced logging system not available, using basic logging instead")

# Create the FastAPI application
app = FastAPI(
    title="RedBarSushi AI",
    description="AI-powered voice ordering system for Red Bar Sushi",
    version="1.0.0",
)

# Mount static files directory
from fastapi.staticfiles import StaticFiles
import os

# Check if static directory exists, create it if not
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    logger.info(f"Created static directory: {static_dir}")

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")
logger.info(f"Mounted static files directory: {static_dir}")

# Create a dedicated logger for our WebSocket test
ws_test_logger = logging.getLogger("app.main_ws_test")
ws_test_logger.setLevel(logging.DEBUG)  # Force debug level
if not ws_test_logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    ws_test_logger.addHandler(ch)
    ws_test_logger.propagate = False
    
ws_test_logger.critical("🔄 WebSocket test logger initialized")

# Add an endpoint to access the WebSocket test page
@app.get("/ws-test-page")
async def websocket_test_page():
    """Redirect to the WebSocket test page in the static directory."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/websocket-test.html")

# Add a simple test WebSocket endpoint directly on the app
@app.websocket("/ws-test/{client_id}")
async def websocket_test_endpoint(websocket: WebSocket, client_id: str):
    # Log detailed connection information including query parameters and headers
    query_params = dict(websocket.query_params)
    headers = dict(websocket.headers)
    
    # Extract custom parameters from either query params or headers
    debug_param = query_params.get("debug", headers.get("debug", "false"))
    client_param = query_params.get("client", headers.get("client", "unknown"))
    time_param = query_params.get("time", headers.get("time", "0"))
    
    # Log all connection details
    ws_test_logger.critical(f"❗❗❗ /ws-test: WebSocket Connection ATTEMPTED for client_id: {client_id} ❗❗❗")
    ws_test_logger.critical(f"❗❗❗ Query Parameters: {query_params} ❗❗❗")
    ws_test_logger.critical(f"❗❗❗ Headers: {headers} ❗❗❗")
    ws_test_logger.critical(f"❗❗❗ Custom Parameters: debug={debug_param}, client={client_param}, time={time_param} ❗❗❗")
    
    print(f"!!! PRINT DEBUG: /ws-test: ATTEMPTING ACCEPT for {client_id} !!!", flush=True)
    print(f"!!! PRINT DEBUG: Debug Params: debug={debug_param}, client={client_param}, time={time_param} !!!", flush=True)
    
    try:
        # Try to accept the WebSocket connection
        await websocket.accept()
        ws_test_logger.critical(f"🟢 /ws-test: WebSocket Connection ACCEPTED for client_id: {client_id}")
        ws_test_logger.critical(f"🟢 Connection Details - Client: {websocket.client}, Headers: {dict(websocket.headers)}")
        print(f"!!! PRINT DEBUG: /ws-test: ACCEPTED for {client_id} !!!", flush=True)
        
        # Send an initial message with connection details
        connection_info = f"Hello, {client_id}! Connection established with params: {query_params}"
        await websocket.send_text(connection_info)
        ws_test_logger.info(f"[{client_id}] /ws-test: Sent welcome message with params")
        
        # Echo messages back to the client
        while True:
            data = await websocket.receive_text()
            ws_test_logger.info(f"[{client_id}] /ws-test: Received: {data}")
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        ws_test_logger.warning(f"[{client_id}] /ws-test: Client disconnected")
    except Exception as e:
        ws_test_logger.error(f"[{client_id}] /ws-test: Error: {e}", exc_info=True)
        print(f"!!! PRINT DEBUG: /ws-test: ERROR for {client_id}: {str(e)} !!!", flush=True)
    finally:
        ws_test_logger.info(f"[{client_id}] /ws-test: Connection closed")
        print(f"!!! PRINT DEBUG: /ws-test: CONNECTION CLOSED for {client_id} !!!", flush=True)

@app.get("/")
async def index(request: Request) -> Dict[str, Any]:
    """Root endpoint that doesn't require database access."""
    # Add environment info to help diagnose routing issues
    env_type = (
        "Staging"
        if os.environ.get("FLASK_ENV") == "staging" or os.environ.get("IS_STAGING")
        else "Production"
    )
    return {
        "message": f"Welcome to Red Bar Sushi AI API ({env_type} Environment)",
        "version": "1.0.0",
        "environment": env_type,
        "host": request.headers.get("host", "unknown"),
        "base_url": str(request.base_url),
        "flask_env": os.environ.get("FLASK_ENV", "not set"),
    }

# /routes endpoint moved after API router inclusion to ensure it can see all routes

@app.get("/healthcheck")
async def healthcheck() -> Dict[str, Any]:
    """Basic health check endpoint."""
    # Basic health information
    health_info = {
        "status": "ok",
        "message": "RedBarSushiAI is running",
        "timestamp": datetime.now().isoformat(),
        "environment": (
            "staging"
            if os.environ.get("FLASK_ENV") == "staging"
            or os.environ.get("IS_STAGING")
            else (
                "production" if os.environ.get("RENDER", False) else "development"
            )
        ),
        "checks": {},
    }
    
    # Database check will be added later when the async database is implemented
    
    return health_info

@app.get("/environment")
async def environment_info() -> Dict[str, Any]:
    """Return detailed information about the environment."""
    import socket
    import platform

    # Get environment variables
    env_vars = {
        key: value
        for key, value in os.environ.items()
        if not any(
            secret in key.lower()
            for secret in ["key", "secret", "password", "token"]
        )
    }

    info = {
        "environment": os.environ.get("FLASK_ENV", "not set"),
        "is_staging": os.environ.get("IS_STAGING", False),
        "render": os.environ.get("RENDER", False),
        "docker": os.environ.get("DOCKER", False),
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "working_directory": os.getcwd(),
        "render_instance_id": os.environ.get("RENDER_INSTANCE_ID", "not in Render"),
        "render_service_id": os.environ.get("RENDER_SERVICE_ID", "not in Render"),
        "timestamp": datetime.now().isoformat(),
        "environment_variables": env_vars,
    }

    return info

# Note: We'll add the /routes endpoint after including the API router
# FastAPI doesn't allow modifying routes directly

# Import and include API routers
from app.api import api_router

# Include the main API router
app.include_router(api_router)

# Import and register WebSocket router separately (not under api_router prefix)
try:
    from app.api.voice import websocket_router
    app.include_router(websocket_router)
    logger.info("Successfully registered WebSocket router for /realtime/ws/media/{call_sid}")
except ImportError as e:
    logger.error(f"Failed to import WebSocket router: {e}")

# Add the /routes endpoint AFTER including the API router
# This ensures it can see all routes including the ones from api_router
@app.get("/routes", include_in_schema=False)
async def list_routes() -> Dict[str, Any]:
    """List all registered routes for debugging."""
    from fastapi.routing import APIRoute, APIRouter
    from starlette.routing import WebSocketRoute
    
    http_routes = []
    ws_routes = []
    sub_routers_info = []
    
    # Helper function to get route info
    def get_route_info(route):
        if isinstance(route, APIRoute):
            return {
                "path": route.path,
                "name": route.name,
                "methods": sorted(list(route.methods)) if route.methods else [],
                "endpoint": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
            }
        elif isinstance(route, WebSocketRoute):
            return {
                "path": route.path,
                "name": route.name,
                "endpoint": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
            }
        return None
    
    # List all routes in the app, including nested routers
    for route in app.routes:
        if isinstance(route, APIRouter):  # This checks for nested APIRouters
            # Log details about the sub-router itself
            sub_routers_info.append({
                "prefix": route.prefix,
                "tags": route.tags,
                "routes_count": len(route.routes) if hasattr(route, 'routes') else 0
            })
            
            # Process routes in the sub-router
            if hasattr(route, 'routes'):
                for sub_route in route.routes:
                    info = get_route_info(sub_route)
                    if info:
                        # Adjust path with the parent router's prefix
                        if route.prefix:
                            info["path"] = f"{route.prefix}{info['path']}"
                        if isinstance(sub_route, APIRoute):
                            http_routes.append(info)
                        elif isinstance(sub_route, WebSocketRoute):
                            ws_routes.append(info)
        else:
            # Direct routes on the app
            info = get_route_info(route)
            if info:
                if isinstance(route, APIRoute):
                    http_routes.append(info)
                elif isinstance(route, WebSocketRoute):
                    ws_routes.append(info)
    
    # Sort routes for consistent output
    http_routes.sort(key=lambda x: x["path"])
    ws_routes.sort(key=lambda x: x["path"])
    
    return {
        "http_routes": http_routes,
        "websocket_routes": ws_routes,
        "sub_routers_info": sub_routers_info,
        "total_app_routes_count": len(app.routes)
    }

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    logger.info("Application startup")
    
    # Log critical information about routes
    logger.critical(f"❗❗❗ APPLICATION STARTUP ❗❗❗")
    logger.critical(f"❗❗❗ WebSocket route should be available at: /realtime/ws/media/{{call_sid}} ❗❗❗")
    logger.critical(f"❗❗❗ TwiML route should be available at: /voice/ and /voice/webhook ❗❗❗")
    
    # Initialize Redis
    try:
        from app.redis_async import init_redis
        redis_client = await init_redis()
        if redis_client:
            logger.info("Redis initialized successfully")
        else:
            logger.warning("Redis initialization failed, using memory cache fallback")
    except Exception as e:
        logger.error(f"Error initializing Redis: {e}")
    
    # Initialize database
    try:
        from app.db_async import init_database, verify_connection
        
        # Check connection first
        is_connected = await verify_connection()
        if is_connected:
            logger.info("Database connection verified")
            
            # Initialize the database if needed
            if settings.INITIALIZE_MENU_DATABASE:
                await init_database()
                logger.info("Database initialized successfully")
        else:
            logger.error("Database connection failed")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    # Initialize async agent orchestrator
    try:
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        from app.db_async import get_db
        
        # Get a database session for agent initialization
        async for db in get_db():
            await async_agent_orchestrator.initialize(db=db)
            logger.info("Async agent orchestrator initialized successfully with database session")
            break
    except Exception as e:
        logger.error(f"Error initializing async agent orchestrator: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    logger.info("Application shutdown")
    
    # Close Redis connection
    try:
        from app.redis_async import _redis_client
        if _redis_client:
            await _redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
    # Close database connection pool
    try:
        from app.db_async import engine
        await engine.dispose()
        logger.info("Database connection pool closed")
    except Exception as e:
        logger.error(f"Error closing database connection pool: {e}")
        
    # Clean up any other resources
    try:
        # Close any other resources
        pass
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    # For development only - use Uvicorn server with reloading
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)