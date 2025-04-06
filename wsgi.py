#!/usr/bin/env python3
"""
WSGI entry point for the RedBarSushiAI project.
This file is used by Render and other WSGI-compatible servers.
"""
import os
import logging
import sys

print("wsgi.py initializing...")

# Important - BASE_URL must be set in environment before importing app
os.environ['BASE_URL'] = os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')
print(f"Setting BASE_URL to {os.environ['BASE_URL']}")

# Disable PythonAnywhere detection to force the correct BASE_URL
os.environ['DISABLE_PYTHONANYWHERE_DETECTION'] = 'true'

# If running on Render, set the environment variable
if os.environ.get('RENDER_SERVICE_ID'):
    os.environ['RENDER'] = 'true'
    print("Running on Render platform")

# Configure logging early
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

# Create application instance
from app import create_app
application = create_app()

# For compatibility with different WSGI servers
app = application

if __name__ == '__main__':
    # This will only run when directly executing this file (not via WSGI server)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)