# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock
import stripe
from twilio.rest import Client
import logging
import sys
import os
from app.config import *
from datetime import datetime

# Initialize X11 environment variables depending on whether virtual X server is available
# Check if we have a virtual X server by looking for the X11_SETUP_SUCCESS environment variable
if os.environ.get('X11_SETUP_SUCCESS') == 'true':
    # X11 mode - use virtual X server
    if 'DISPLAY' not in os.environ or not os.environ['DISPLAY']:
        os.environ['DISPLAY'] = ':99'  # Default to display 99
    
    # Set X11 environment variables
    os.environ['PYNPUT_HEADLESS'] = '0'
    os.environ['NO_X11'] = '0'
    os.environ['HEADLESS'] = '0'
    os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '0'
else:
    # Headless mode - no X11 server
    os.environ['PYNPUT_HEADLESS'] = '1'
    os.environ['NO_X11'] = '1'
    os.environ['HEADLESS'] = '1'
    os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '1'
    
    # Unset DISPLAY to prevent X11 connection attempts
    if 'DISPLAY' in os.environ:
        del os.environ['DISPLAY']

# Logging setup
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

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
        version_match = re.match(r'^(\d+)\.(\d+)\.(\d+)', twilio_version)
        if version_match:
            major, minor, patch = map(int, version_match.groups())
            
            if major >= 7:
                # Newer versions support timeout in the constructor
                twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, timeout=10)
            else:
                # Older versions don't support timeout in constructor
                twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        else:
            # Fallback if version can't be parsed
            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
        logging.info(f"Twilio client initialized successfully (version {twilio_version})")
    except Exception as parse_error:
        # If version parsing fails, create client without timeout
        logging.warning(f"Error parsing Twilio version: {parse_error}, creating client without timeout")
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
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,
        'pool_timeout': 20,
        'pool_pre_ping': True,
        'connect_args': {'connect_timeout': 10}
    }
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout
    app.secret_key = APP_SECRET_KEY
    
    # Override with test config if provided
    if test_config:
        app.config.update(test_config)

    # Initialize the database
    db.init_app(app)
    
    # Initialize WebSockets
    sock.init_app(app)

    # Register Blueprints for routes
    from app.routes.voice import voice_bp
    from app.routes.menu import menu_bp
    from app.routes.order import order_bp
    from app.routes.location import location_bp
    from app.routes.webhook import webhook_bp, init_app as init_webhook

    # Register blueprints with explicit URL prefixes for clarity
    # Register blueprints with original structure for backwards compatibility
    app.register_blueprint(voice_bp)  # Keep at root level for Twilio webhook compatibility
    app.register_blueprint(menu_bp)   # Keep at root level for existing Deliverect integrations
    app.register_blueprint(order_bp)  # Keep at root level for order webhooks
    app.register_blueprint(location_bp) # Keep at root level for consistency
    app.register_blueprint(webhook_bp) # Register webhook routes
    
    # Initialize webhook module
    init_webhook(app)

    # Configure optimized logging
    # Clear any existing handlers to avoid duplicates
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging based on environment
    if os.environ.get('RENDER', False) or os.environ.get('DOCKER', False):
        # Simpler, more efficient logging for production
        log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            stream=sys.stderr,
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
    else:
        # More detailed logging for development
        logging.basicConfig(
            filename='progress.log',
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        # Also log to console in dev environment
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    
    # Reduce verbosity of some noisy loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Log startup information
    logging.info(f"Application starting in {'production' if os.environ.get('RENDER', False) else 'development'} mode")
    
    # Log the environment as a test
    app.logger.debug("Application initialized with SQLAlchemy URI type: %s", 
                    type(app.config['SQLALCHEMY_DATABASE_URI']))
                    
    # Simple root route that doesn't require database access
    @app.route('/')
    def index():
        return {"message": "Welcome to Red Bar Sushi AI API", "version": "1.0.0"}
        
    @app.route('/menu-check')
    def menu_check():
        """Diagnostic endpoint to check menu status"""
        from app.utils.menu_utils import load_menu_data, MENU_FILE_PATH
        import os
        
        result = {
            "menu_file_path": MENU_FILE_PATH,
            "exists": os.path.exists(MENU_FILE_PATH),
            "locations_checked": [],
            "items_count": 0
        }
        
        # Check common locations
        for path in [
            MENU_FILE_PATH,
            os.path.join(os.getcwd(), 'menu_data.json'),
            '/app/menu_data.json',
            '/var/task/menu_data.json'
        ]:
            exists = os.path.exists(path)
            size = os.path.getsize(path) if exists else 0
            result["locations_checked"].append({
                "path": path,
                "exists": exists,
                "size": size,
                "permissions": oct(os.stat(path).st_mode) if exists else "N/A"
            })
            
        # Actually load the menu
        try:
            menu = load_menu_data(force_refresh=True)
            result["load_success"] = True
            result["items_count"] = len(menu.get("items", []))
            result["items_sample"] = [item.get("name") for item in menu.get("items", [])[:5]]
            result["variants_count"] = len(menu.get("name_variants", {}))
        except Exception as e:
            result["load_success"] = False
            result["error"] = str(e)
            
        return result
        
    # Add a comprehensive health check endpoint
    @app.route('/healthcheck')
    def healthcheck():
        # Basic health information
        health_info = {
            'status': 'ok',
            'message': 'RedBarSushiAI is running',
            'timestamp': datetime.now().isoformat(),
            'environment': 'production' if os.environ.get('RENDER', False) else 'development',
            'checks': {}
        }
        
        # Check database connection
        try:
            # Simple database ping
            with app.app_context():
                db.session.execute('SELECT 1').scalar()
            health_info['checks']['database'] = 'ok'
        except Exception as e:
            health_info['checks']['database'] = f'error: {str(e)}'
            health_info['status'] = 'degraded'
        
        # Check Redis if we're using it
        redis_url = os.environ.get('CELERY_BROKER_URL')
        if redis_url:
            try:
                import redis
                r = redis.from_url(redis_url, socket_timeout=2.0)
                r.ping()
                health_info['checks']['redis'] = 'ok'
            except Exception as e:
                health_info['checks']['redis'] = f'error: {str(e)}'
                # Redis issues shouldn't mark the whole system as down
                if health_info['status'] == 'ok':
                    health_info['status'] = 'degraded'
        
        # Check menu data
        try:
            from app.utils.menu_utils import load_menu_data
            menu = load_menu_data()
            items_count = len(menu.get('items', []))
            health_info['checks']['menu'] = f'ok ({items_count} items)'
        except Exception as e:
            health_info['checks']['menu'] = f'error: {str(e)}'
            if health_info['status'] == 'ok':
                health_info['status'] = 'degraded'
        
        # Return application/json response with appropriate status code
        from flask import jsonify
        return jsonify(health_info)
        
    # Add database connection cleanup to prevent memory leaks
    @app.teardown_appcontext
    def cleanup_db_resources(exception=None):
        db.session.close()

    return app