# app/__init__.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock
import stripe
from twilio.rest import Client
import logging
import sys
import os
from app.config import *
from datetime import datetime

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

# Initialize X11 environment variables depending on whether virtual X server is available
# Check if we have a virtual X server by looking for the X11_SETUP_SUCCESS environment variable
if os.environ.get("X11_SETUP_SUCCESS") == "true":
    # X11 mode - use virtual X server

    # Use the working display provided by the startup script
    # This might be different from :99 in some environments
    if "DISPLAY" in os.environ and os.environ["DISPLAY"]:
        logging.info(f"Using provided X display: {os.environ['DISPLAY']}")
    else:
        # Try several displays in order until one works
        # Don't default to :99 as it might be in use
        for display in [":1", ":99", ":0"]:
            try:
                logging.info(f"Testing display {display}...")
                os.environ["DISPLAY"] = display
                break
            except Exception as e:
                logging.warning(f"Display {display} failed: {e}")

    # Set X11 environment variables
    os.environ["PYNPUT_HEADLESS"] = "0"
    os.environ["NO_X11"] = "0"
    os.environ["HEADLESS"] = "0"
    os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "0"

    logging.info(f"X11 mode active with display: {os.environ.get('DISPLAY')}")
else:
    # Headless mode - no X11 server
    os.environ["PYNPUT_HEADLESS"] = "1"
    os.environ["NO_X11"] = "1"
    os.environ["HEADLESS"] = "1"
    os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

    # Unset DISPLAY to prevent X11 connection attempts
    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]

    logging.info("Headless mode active (no X11)")

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

# Initialize SQLAlchemy
db = SQLAlchemy()

# Initialize Sock for WebSockets
sock = Sock()

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

        version_match = re.match(r"^(\d+)\.(\d+)\.(\d+)", twilio_version)
        if version_match:
            major, minor, patch = map(int, version_match.groups())

            if major >= 7:
                # Newer versions support timeout in the constructor
                twilio_client = Client(
                    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, timeout=10
                )
            else:
                # Older versions don't support timeout in constructor
                twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        else:
            # Fallback if version can't be parsed
            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        logging.info(
            f"Twilio client initialized successfully (version {twilio_version})"
        )
    except Exception as parse_error:
        # If version parsing fails, create client without timeout
        logging.warning(
            f"Error parsing Twilio version: {parse_error}, creating client without timeout"
        )
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

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

try:
    # Initialize Stripe with timeout
    stripe.api_key = STRIPE_API_KEY
    stripe.max_network_retries = 2
    stripe.default_http_client = stripe.http_client.RequestsClient(timeout=10)
    logging.info("Stripe client initialized successfully")
except Exception as e:
    logging.error(f"Error initializing Stripe client: {e}")


def create_app(test_config=None):
    app = Flask(__name__)

    # Default configuration with timeouts
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS

    # Configure SQLAlchemy engine options based on database type
    engine_options = {
        "pool_recycle": 1800,  # 30 minutes to match Render's proxy timeout
        "pool_pre_ping": True,  # Check connection before using it
        "pool_reset_on_return": True,  # Reset connections when returned to pool
    }

    # Only add options compatible with the specific database type
    if SQLALCHEMY_DATABASE_URI:
        if "sqlite" in SQLALCHEMY_DATABASE_URI:
            # SQLite doesn't support pool_timeout or connect_timeout
            pass
        elif (
            "postgresql" in SQLALCHEMY_DATABASE_URI
            or "postgres" in SQLALCHEMY_DATABASE_URI
        ):
            # PostgreSQL-specific optimizations for Render
            engine_options.update(
                {
                    "pool_timeout": 30,  # Increased timeout for connection acquisition
                    "connect_args": {
                        "connect_timeout": 15,  # Increased connection timeout
                        "keepalives": 1,  # Enable TCP keepalives
                        "keepalives_idle": 60,  # Send keepalive after 60 seconds of inactivity
                        "keepalives_interval": 10,  # 10 seconds between keepalives
                        "keepalives_count": 3,  # Number of keepalives before dropping connection
                        # Additional PostgreSQL-specific settings for better reliability
                        "application_name": "RedBarSushiAI",  # Identify app in pg_stat_activity
                        "options": "-c statement_timeout=60000",  # 60s statement timeout
                    },
                }
            )
        else:
            # For MySQL and other full DB engines
            engine_options.update(
                {
                    "pool_timeout": 30,  # Increased timeout for connection acquisition
                    "connect_args": {
                        "connect_timeout": 15,  # Increased connection timeout
                    },
                }
            )

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
    app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour session timeout
    app.secret_key = APP_SECRET_KEY

    # Override with test config if provided
    if test_config:
        app.config.update(test_config)

    # Initialize the database, but handle API schema validation better in testing environments
    skip_db_init = False

    # Skip database initialization in API schema validation mode to avoid connection failures
    if is_testing and os.environ.get("SKIP_DB_INIT") == "true":
        skip_db_init = True
        logger = logging.getLogger(__name__)
        logger.info("Skipping database initialization in API schema validation mode")

    if not skip_db_init:
        # Initialize SQLAlchemy with our app
        db.init_app(app)

        # Initialize the database for menu storage if configured
        if app.config.get("INITIALIZE_MENU_DATABASE", True):
            with app.app_context():
                try:
                    # Import here to avoid circular imports
                    from app.db_init import init_database, fresh_session

                    # Ensure we have a fresh session for initialization
                    fresh_session()

                    # Initialize database with retry logic
                    init_database()
                except Exception as e:
                    app.logger.error(
                        f"Failed to initialize menu database: {e}", exc_info=True
                    )
                    # Continue anyway to ensure app starts
                    app.logger.warning(
                        "App will continue starting up despite database initialization error"
                    )

                    # Try to clean up the session to prevent future errors
                    try:
                        db.session.remove()
                    except:
                        pass

    # Initialize WebSockets
    sock.init_app(app)
    


    # Import common routes
    from app.routes.realtime import realtime_bp
    from app.routes.escalation import escalation_bp
    from app.routes.monitoring import monitoring_bp
    from app.routes.menu import menu_bp
    # Import order_bp from refactored module structure
    from app.routes.order import order_bp
    from app.routes.location import location_bp
    from app.routes.order_ai import order_ai_bp
    
    # Import voice implementations
    from app.config import VOICE_HANDLER
    from flask import Blueprint
    
    # Import voice blueprints with try/except to handle potential circular imports
    try:
        from app.routes.voice import voice_bp
    except ImportError as e:
        logger.error(f"Error importing voice_bp: {e}")
        voice_bp = Blueprint('voice', __name__)  # Create a dummy blueprint

    try:
        from app.routes.voice_orchestrated import orchestrated_voice_bp
    except ImportError as e:
        logger.error(f"Error importing orchestrated_voice_bp: {e}")
        orchestrated_voice_bp = Blueprint('orchestrated_voice', __name__)  # Create a dummy blueprint
    
    try:
        from app.routes.voice_orchestrated_realtime import realtime_voice_bp
    except ImportError as e:
        logger.error(f"Error importing realtime_voice_bp: {e}")
        realtime_voice_bp = Blueprint('voice_orchestrated_realtime', __name__)  # Create a dummy blueprint
    
    # Register non-voice routes
    app.register_blueprint(menu_bp)  # Menu routes
    app.register_blueprint(order_bp)  # Order routes
    app.register_blueprint(location_bp)  # Location routes
    app.register_blueprint(order_ai_bp)  # AI-powered interactive order resolution
    app.register_blueprint(realtime_bp, url_prefix='/realtime')  # Realtime audio processing
    app.register_blueprint(escalation_bp)  # Staff handoff and escalation routes
    app.register_blueprint(monitoring_bp, url_prefix='/monitoring')  # Monitoring and health check routes
    
    # Register the appropriate voice handler based on configuration
    app_logger = logging.getLogger(__name__)
    app_logger.info(f"Configuring voice handler: {VOICE_HANDLER}")
    
    if VOICE_HANDLER == "realtime":
        # Use the Realtime API implementation as primary handler
        app.register_blueprint(realtime_voice_bp)
        app.register_blueprint(orchestrated_voice_bp, url_prefix='/voice_orchestrated')  # Orchestrated as fallback
        app.register_blueprint(voice_bp, url_prefix='/voice_standard')  # Standard as fallback
        app_logger.info("Voice handler set to REALTIME (OpenAI Realtime API with WebSockets)")
    elif VOICE_HANDLER == "orchestrated":
        # Use the advanced orchestrated implementation as primary handler
        app.register_blueprint(orchestrated_voice_bp)
        app.register_blueprint(realtime_voice_bp, url_prefix='/voice_realtime')  # Realtime as alternative
        app.register_blueprint(voice_bp, url_prefix='/voice_standard')  # Standard as fallback
        app_logger.info("Voice handler set to ORCHESTRATED (multi-agent with handoffs, FSM, etc.)")
    else:
        # Use the standard implementation as primary handler
        app.register_blueprint(voice_bp)
        app.register_blueprint(orchestrated_voice_bp, url_prefix='/voice_orchestrated')  # Orchestrated as alternative
        app.register_blueprint(realtime_voice_bp, url_prefix='/voice_realtime')  # Realtime as alternative
        app_logger.info("Voice handler set to STANDARD (original implementation)")

    # Configure optimized logging
    # Clear any existing handlers to avoid duplicates
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    # Initialize monitoring
    from app.utils.monitoring import init_monitoring
    init_monitoring(app)

    # Configure logging based on environment
    if os.environ.get("RENDER", False) or os.environ.get("DOCKER", False):
        # Simpler, more efficient logging for production
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            stream=sys.stderr,
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
    else:
        # More detailed logging for development
        logging.basicConfig(
            filename="progress.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
        # Also log to console in dev environment
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)

    # Reduce verbosity of some noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log startup information
    logging.info(
        f"Application starting in {'production' if os.environ.get('RENDER', False) else 'development'} mode"
    )

    # Log the environment as a test
    app.logger.debug(
        "Application initialized with SQLAlchemy URI type: %s",
        type(app.config["SQLALCHEMY_DATABASE_URI"]),
    )

    # Simple root route that doesn't require database access
    @app.route("/")
    def index():
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
            "host": request.host,
            "base_url": request.base_url,
            "flask_env": os.environ.get("FLASK_ENV", "not set"),
        }

    @app.route("/menu-check")
    def menu_check():
        """Diagnostic endpoint to check menu status from database"""
        from app.utils.menu_utils_db import load_menu_data
        from app.utils.menu_db_store import menu_db_store

        result = {
            "database": True,
            "storage_method": "database",
            "database_connection": True,
            "items_count": 0,
        }

        # Load the menu from database
        try:
            menu = load_menu_data(force_refresh=True)
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

    # Add a comprehensive health check endpoint
    # Add a special endpoint to help diagnose routing issues
    @app.route("/environment")
    def environment_info():
        """Return detailed information about the environment"""
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
            "host": request.host,
            "url": request.url,
            "base_url": request.base_url,
            "remote_addr": request.remote_addr,
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

        return jsonify(info)

    @app.route("/healthcheck")
    def healthcheck():
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

        # Check database connection
        try:
            # Simple database ping with proper session handling
            with app.app_context():
                # Import from db_init to use our fresh session logic
                from app.db_init import fresh_session, verify_connection

                # Ensure we have a fresh session
                fresh_session()

                # Use our verify_connection function that handles session lifecycle
                if verify_connection():
                    health_info["checks"]["database"] = "ok"
                else:
                    health_info["checks"][
                        "database"
                    ] = "error: Connection verification failed"
                    health_info["status"] = "degraded"
        except Exception as e:
            health_info["checks"]["database"] = f"error: {str(e)}"
            health_info["status"] = "degraded"

            # Clean up the session to prevent future errors
            try:
                db.session.remove()
            except:
                pass

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
            from app.utils.menu_utils_db import load_menu_data

            menu = load_menu_data()
            items_count = len(menu.get("items", []))
            health_info["checks"]["menu"] = f"ok ({items_count} items)"
        except Exception as e:
            health_info["checks"]["menu"] = f"error: {str(e)}"
            if health_info["status"] == "ok":
                health_info["status"] = "degraded"

        # Return application/json response with appropriate status code
        from flask import jsonify

        return jsonify(health_info)

    # Add database connection cleanup to prevent memory leaks
    @app.teardown_appcontext
    def cleanup_db_resources(exception=None):
        if hasattr(db, 'session'):
            db.session.close()

    return app
