#!/usr/bin/env python3
"""
WSGI entry point for the RedBarSushiAI project.
This file is used by Render and other WSGI-compatible servers with gevent worker.
"""

# Apply gevent monkey patching BEFORE any imports to ensure all standard library calls are patched
try:
    import gevent.monkey
    gevent.monkey.patch_all()
    print("Applied gevent monkey patching for WebSocket support")
except ImportError:
    print("ERROR: Gevent not installed, WebSocket functionality will fail!")
    # Raise an exception to prevent further execution
    raise RuntimeError("Gevent is required for WebSocket functionality")

# Continue with standard imports after patching
import os
import logging
import sys

print("wsgi.py initializing...")

# Important - BASE_URL must be set in environment before importing app
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

# Configure logging early
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

# Create application instance AFTER gevent monkey patching
from app import create_app

application = create_app()

# For compatibility with different WSGI servers
app = application

# We're using gevent directly with Flask-Sock as per Flask-Sock docs
# No need for ASGI compatibility layer since we're using WSGI with gevent
logging.info("Using gevent worker with Flask-Sock for WebSocket support")

# Export the Flask app directly for Gunicorn with gevent worker
__all__ = ['app', 'application']

if __name__ == "__main__":
    # This will only run when directly executing this file (not via WSGI server)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
