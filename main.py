#!/usr/bin/env python3
"""
Main entry point for the RedBarSushiAI FastAPI application.
This file is used by Uvicorn to run the FastAPI server.
"""

import os
import logging
import sys
from fastapi import FastAPI, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import socket
import platform

# Configure logging early
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

# Important - BASE_URL must be set in environment
os.environ["BASE_URL"] = os.environ.get(
    "BASE_URL", "https://redbarsushiai.onrender.com"
)
print(f"Setting BASE_URL to {os.environ['BASE_URL']}")

# Disable PythonAnywhere detection to force the correct BASE_URL
os.environ["DISABLE_PYTHONANYWHERE_DETECTION"] = "true"

# If running on Render, set the environment variable
if os.environ.get("RENDER_SERVICE_ID"):
    os.environ["RENDER"] = "true"
    print("Running on Render platform")

# Configure headless mode for server environments
# X11 is not needed for WebSocket-based Realtime integration
# The voice system works fully headless without any GUI components

# Force headless mode for production environments (e.g., Render)
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

    logging.info("Headless mode active (no X11 needed)")
else:
    # X11 mode - only for development with GUI components
    # This branch should not be used in production
    logging.warning("X11 mode active - not recommended for production")
    
    # Use the working display provided by the startup script
    if "DISPLAY" in os.environ and os.environ["DISPLAY"]:
        logging.info(f"Using provided X display: {os.environ['DISPLAY']}")
    else:
        # Default to no display
        logging.warning("No display set, using headless mode instead")
        os.environ["PYNPUT_HEADLESS"] = "1"
        os.environ["NO_X11"] = "1"
        os.environ["HEADLESS"] = "1"
        os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

# Enhanced logging setup
try:
    from app.utils.enhanced_logging import initialize_logging
    log_dir = initialize_logging()
    logging.info(f"Enhanced logging system initialized, logs directory: {log_dir}")
except ImportError:
    # Fall back to basic logging if enhanced logging isn't available
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    logging.warning("Enhanced logging system not available, using basic logging instead")

# Initialize database
from app.db_async import init_database

# Create FastAPI application
app = FastAPI(title="RedBarSushiAI", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be set to specific origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import API routes
from app.api import api_router

# Define diagnostic routes
from fastapi.routing import APIRoute, APIRouter, WebSocketRoute
from typing import List, Set
from fastapi.responses import RedirectResponse

@app.get("/routes", summary="List all registered application routes", include_in_schema=False)
async def list_routes_endpoint() -> Dict[str, Any]:
    """List all registered routes for debugging."""
    http_routes_info = []
    ws_routes_info = []
    
    processed_routes: Set[str] = set()

    def get_route_details(r, prefix=""):
        path = f"{prefix}{r.path}"
        if path in processed_routes:  # Avoid duplicates if same route object is on multiple routers
            return None
        processed_routes.add(path)

        if isinstance(r, APIRoute):
            return {
                "path": path,
                "name": r.name,
                "methods": sorted(list(r.methods)) if r.methods else [],
                "endpoint": f"{r.endpoint.__module__}.{r.endpoint.__name__}" if hasattr(r.endpoint, "__module__") and hasattr(r.endpoint, "__name__") else str(r.endpoint),
            }
        elif isinstance(r, WebSocketRoute):
            return {
                "path": path,
                "name": r.name,
                "endpoint": f"{r.endpoint.__module__}.{r.endpoint.__name__}" if hasattr(r.endpoint, "__module__") and hasattr(r.endpoint, "__name__") else str(r.endpoint),
            }
        return None

    # First, collect routes directly on the app
    for r in app.routes:
        if isinstance(r, APIRouter):  # It's a sub-router included directly on app
            router_prefix = getattr(r, "prefix", "")
            router_routes = getattr(r, "routes", [])
            
            for sub_r in router_routes:
                details = get_route_details(sub_r, prefix=router_prefix)
                if details:
                    if isinstance(sub_r, APIRoute):
                        http_routes_info.append(details)
                    elif isinstance(sub_r, WebSocketRoute):
                        ws_routes_info.append(details)
        else:  # It's a route directly on app
            details = get_route_details(r)
            if details:
                if isinstance(r, APIRoute):
                    http_routes_info.append(details)
                elif isinstance(r, WebSocketRoute):
                    ws_routes_info.append(details)
    
    # Process included APIRouter (api_router) separate from app.routes
    if hasattr(api_router, "routes"):
        router_prefix = getattr(api_router, "prefix", "")
        for r in api_router.routes:
            if isinstance(r, APIRouter):  # Nested router
                sub_prefix = getattr(r, "prefix", "")
                full_prefix = f"{router_prefix}{sub_prefix}"
                
                for sub_r in getattr(r, "routes", []):
                    details = get_route_details(sub_r, prefix=full_prefix)
                    if details:
                        if isinstance(sub_r, APIRoute):
                            http_routes_info.append(details)
                        elif isinstance(sub_r, WebSocketRoute):
                            ws_routes_info.append(details)
            else:  # Direct route on api_router
                details = get_route_details(r, prefix=router_prefix)
                if details:
                    if isinstance(r, APIRoute):
                        http_routes_info.append(details)
                    elif isinstance(r, WebSocketRoute):
                        ws_routes_info.append(details)
    
    # Sort the routes by path
    http_routes_info.sort(key=lambda x: x["path"])
    ws_routes_info.sort(key=lambda x: x["path"])

    return {
        "http_routes": http_routes_info,
        "websocket_routes": ws_routes_info,
        "total_http_routes": len(http_routes_info),
        "total_websocket_routes": len(ws_routes_info),
    }

# Add a simple endpoint to access the websocket test page
@app.get("/ws-test-page")
async def websocket_test_page():
    """Redirect to the WebSocket test page."""
    return RedirectResponse(url="/static/websocket-test.html")

# Mount static files directory
from fastapi.staticfiles import StaticFiles

# Create static directory if it doesn't exist
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    logging.info(f"Created static directory: {static_dir}")

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")
logging.info(f"Mounted static files directory: {static_dir}")

# Include API router after defining diagnostic routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    # Initialize the database
    try:
        await init_database()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}", exc_info=True)
        logging.warning("App will continue starting up despite database initialization error")

# WebSocket test endpoint for diagnostics
@app.websocket("/ws-test/{client_id}")
async def websocket_test_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket test endpoint for diagnostics."""
    print(f"⚠️ WEBSOCKET TEST: Connection attempt from {client_id}")
    logging.critical(f"⚠️ WEBSOCKET TEST: Connection attempt from {client_id}")
    
    try:
        await websocket.accept()
        print(f"✅ WEBSOCKET TEST: Connection accepted for {client_id}")
        logging.critical(f"✅ WEBSOCKET TEST: Connection accepted for {client_id}")
        
        # Send an initial message
        await websocket.send_text(f"Hello, {client_id}! Connection established.")
        
        # Echo messages back to the client
        while True:
            data = await websocket.receive_text()
            logging.info(f"WEBSOCKET TEST: Received message from {client_id}: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logging.warning(f"WEBSOCKET TEST: Client {client_id} disconnected")
    except Exception as e:
        logging.error(f"WEBSOCKET TEST: Error with {client_id}: {str(e)}")
        print(f"❌ WEBSOCKET TEST: Error with {client_id}: {str(e)}")
    finally:
        logging.info(f"WEBSOCKET TEST: Connection closed for {client_id}")

@app.get("/")
async def index():
    """Root endpoint."""
    # Add environment info to help diagnose routing issues
    env_type = (
        "Staging"
        if os.environ.get("FASTAPI_ENV") == "staging" or os.environ.get("IS_STAGING")
        else "Production"
    )
    return {
        "message": f"Welcome to Red Bar Sushi AI API ({env_type} Environment)",
        "version": "1.0.0",
        "environment": env_type,
        "host": socket.gethostname(),
        "base_url": os.environ.get("BASE_URL", ""),
        "fastapi_env": os.environ.get("FASTAPI_ENV", "not set"),
    }

@app.get("/menu-check")
async def menu_check():
    """Diagnostic endpoint to check menu status from database."""
    from app.utils.menu_utils_db import load_menu_data_async
    from app.utils.menu_db_store import menu_db_store_async

    result = {
        "database": True,
        "storage_method": "database",
        "database_connection": True,
        "items_count": 0,
    }

    # Load the menu from database
    try:
        menu = await load_menu_data_async(force_refresh=True)
        result["load_success"] = True
        result["items_count"] = len(menu.get("items", []))
        result["modifiers_count"] = len(menu.get("modifiers", []))
        result["groups_count"] = len(menu.get("modifierGroups", []))
        result["items_sample"] = [
            item.get("name") for item in menu.get("items", [])[:5]
        ]
    except Exception as e:
        result["load_success"] = False
        result["error"] = str(e)

    return result

@app.get("/environment")
async def environment_info():
    """Return detailed information about the environment."""
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
        "environment": os.environ.get("FASTAPI_ENV", "not set"),
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

@app.get("/healthcheck")
async def healthcheck():
    """Health check endpoint."""
    # Basic health information
    health_info = {
        "status": "ok",
        "message": "RedBarSushiAI is running",
        "timestamp": datetime.now().isoformat(),
        "environment": (
            "staging"
            if os.environ.get("FASTAPI_ENV") == "staging"
            or os.environ.get("IS_STAGING")
            else (
                "production" if os.environ.get("RENDER", False) else "development"
            )
        ),
        "checks": {},
    }

    # Check database connection
    try:
        # Simple database ping with proper session handling
        from app.db_async import verify_connection

        # Use our verify_connection function that handles session lifecycle
        if await verify_connection():
            health_info["checks"]["database"] = "ok"
        else:
            health_info["checks"][
                "database"
            ] = "error: Connection verification failed"
            health_info["status"] = "degraded"
    except Exception as e:
        health_info["checks"]["database"] = f"error: {str(e)}"
        health_info["status"] = "degraded"

    # Check Redis if we're using it
    # Prioritize REDIS_URL over CELERY_BROKER_URL
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
    if redis_url:
        try:
            import redis

            # Ensure the URL has the proper redis:// prefix
            if not redis_url.startswith("redis://"):
                redis_url = f"redis://{redis_url}"
                
            r = redis.from_url(redis_url, socket_timeout=2.0)
            r.ping()
            health_info["checks"]["redis"] = "ok"
            health_info["checks"]["redis_url"] = redis_url.replace(redis_url.split("@")[-1] if "@" in redis_url else redis_url, "*****")  # Hide actual hostname/credentials
        except Exception as e:
            health_info["checks"]["redis"] = f"error: {str(e)}"
            # Redis issues shouldn't mark the whole system as down
            if health_info["status"] == "ok":
                health_info["status"] = "degraded"

    # Check menu data
    try:
        from app.utils.menu_utils_db import load_menu_data_async

        menu = await load_menu_data_async()
        items_count = len(menu.get("items", []))
        health_info["checks"]["menu"] = f"ok ({items_count} items)"
    except Exception as e:
        health_info["checks"]["menu"] = f"error: {str(e)}"
        if health_info["status"] == "ok":
            health_info["status"] = "degraded"

    return health_info

# Run the application directly if executed
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)