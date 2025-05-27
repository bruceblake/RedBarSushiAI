# app/__init__.py
"""
RedBarSushiAI package initialization.
This module contains the initialization for the FastAPI application.
"""

import os
import logging
import sys
import traceback
from datetime import datetime

# Optional imports for services that might not be configured
try:
    import stripe
except ImportError:
    stripe = None
    logging.warning("Stripe module not found - payment functionality will be disabled")

try:
    from twilio.rest import Client
except ImportError:
    Client = None
    logging.warning("Twilio module not found - SMS functionality will be disabled")

from app.config import settings

# Set up module-level logger
logger = logging.getLogger(__name__)

# Check if we're in testing mode
is_testing = os.environ.get("TESTING") == "True" or os.environ.get("TESTING") == "true"

# Mock celery and related modules for test environments to avoid dependency issues
if is_testing:
    # Create mock module for celery to use in tests
    class MockCelery:
        def __init__(self, *args, **kwargs):
            self.conf = type(
                "conf",
                (),
                {
                    "update": lambda x: None,
                    "imports": [],
                    "beat_schedule": {},
                },
            )

        def task(self, *args, **kwargs):
            def decorator(func):
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)

                return wrapper

            return decorator

    class MockTask:
        def __call__(self, *args, **kwargs):
            return None

    # Mock the celery module for test environments
    sys.modules["celery"] = type("celery", (), {"Celery": MockCelery, "Task": MockTask})

    # Create a mock tasks module
    class MockTasks:
        @staticmethod
        def send_confirmation_sms_task(*args, **kwargs):
            return None

        @staticmethod
        def send_order_status_update_task(*args, **kwargs):
            return None

        @staticmethod
        def sync_menu_references(*args, **kwargs):
            return None

    # Mock the tasks module
    sys.modules["tasks"] = MockTasks()

    # Mock the celery_app module to avoid circular imports
    class MockCeleryApp:
        celery = MockCelery()

    # Mock the celery_app module
    sys.modules["celery_app"] = MockCeleryApp()

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

# Initialize clients with proper error handling
try:
    # Initialize Twilio client
    # Check which version of twilio we're using
    import twilio
    import pkg_resources

    twilio_version = pkg_resources.get_distribution("twilio").version
    logging.info(f"Detected Twilio version: {twilio_version}")

    # Parse version as integers
    try:
        # Remove any alpha/beta/etc. suffixes for version comparison
        import re

        # Try to create client with timeout first, fall back if not supported
        try:
            # Try with timeout parameter (supported in some versions)
            twilio_client = Client(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, timeout=10
            )
        except TypeError as e:
            # If timeout parameter is not supported, create without it
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        logging.info(
            f"Twilio client initialized successfully (version {twilio_version})"
        )
    except Exception as parse_error:
        # If version parsing fails, create client without timeout
        logging.warning(
            f"Error parsing Twilio version: {parse_error}, creating client without timeout"
        )
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

except Exception as e:
    logging.error(f"Error initializing Twilio client: {e}")

    # Create a dummy client that won't crash the app
    class DummyTwilioClient:
        def __getattr__(self, name):
            return self

        def __call__(self, *args, **kwargs):
            return None

        def create(self, *args, **kwargs):
            logging.warning("Dummy Twilio client used - message not sent")
            return None

    twilio_client = DummyTwilioClient()

if stripe:
    try:
        # Initialize Stripe with timeout
        stripe.api_key = settings.STRIPE_API_KEY
        stripe.max_network_retries = 2
        stripe.default_http_client = stripe.http_client.RequestsClient(timeout=10)
        logging.info("Stripe client initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing Stripe client: {e}")
else:
    logging.warning("Stripe not available - payment functionality disabled")
