#!/usr/bin/env python3
"""
Diagnose and fix WebSocket route registration issues in the Flask app.
This script identifies why /ws/voice/media and other WebSocket routes aren't registering
and provides a fix by ensuring Flask-Sock is properly initialized.
"""

import os
import sys
import importlib
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("fix_websocket")

def check_flask_sock_version():
    """Check the installed Flask-Sock version."""
    try:
        import flask_sock
        logger.info(f"Flask-Sock version: {flask_sock.__version__}")
        return flask_sock.__version__
    except (ImportError, AttributeError) as e:
        logger.error(f"Error getting Flask-Sock version: {e}")
        return None

def check_werkzeug_version():
    """Check the installed Werkzeug version."""
    try:
        import werkzeug
        logger.info(f"Werkzeug version: {werkzeug.__version__}")
        return werkzeug.__version__
    except (ImportError, AttributeError) as e:
        logger.error(f"Error getting Werkzeug version: {e}")
        return None

def check_flask_version():
    """Check the installed Flask version."""
    try:
        import flask
        logger.info(f"Flask version: {flask.__version__}")
        return flask.__version__
    except (ImportError, AttributeError) as e:
        logger.error(f"Error getting Flask version: {e}")
        return None

def fix_websocket_initialization():
    """
    Fix the WebSocket route registration by modifying app/__init__.py
    to ensure Flask-Sock is properly initialized.
    """
    init_file = "/home/proxyie/MySoftware/RedBarSushiAI/app/__init__.py"
    
    # Read the current file
    logger.info(f"Reading {init_file}")
    try:
        with open(init_file, 'r') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading {init_file}: {e}")
        return False
    
    # Check if sock initialization is already fixed
    if "app.wsgi_app = sock.websocket(app.wsgi_app)" in content:
        logger.info("Flask-Sock initialization already fixed.")
        return True
    
    # Find the location to insert the fix
    new_content = []
    sock_init_line = "    sock.init_app(app)"
    fixed = False
    
    for line in content.splitlines():
        new_content.append(line)
        if line.strip() == sock_init_line:
            # Add the fix to properly initialize the WebSocket WSGI middleware
            new_content.append("    # Fix for WebSocket route registration")
            new_content.append("    app.wsgi_app = sock.websocket(app.wsgi_app)")
            fixed = True
    
    if not fixed:
        logger.error(f"Could not find 'sock.init_app(app)' line in {init_file}")
        return False
    
    # Write the fixed content back
    logger.info(f"Writing fixed content to {init_file}")
    try:
        with open(init_file, 'w') as f:
            f.write('\n'.join(new_content))
        return True
    except Exception as e:
        logger.error(f"Error writing to {init_file}: {e}")
        return False

def main():
    logger.info("Starting WebSocket fix script")
    
    # Check package versions
    check_flask_version()
    check_werkzeug_version()
    check_flask_sock_version()
    
    # Apply the fix
    if fix_websocket_initialization():
        logger.info("Successfully applied WebSocket initialization fix")
        logger.info("Please restart the Flask app for changes to take effect")
        return 0
    else:
        logger.error("Failed to apply WebSocket initialization fix")
        return 1

if __name__ == "__main__":
    sys.exit(main())