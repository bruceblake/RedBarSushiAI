# app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# ------------------------------
# General Application Settings
# ------------------------------
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "bd0acf5c060feaa576051293a661a49a")

# ------------------------------
# Database Configuration
# ------------------------------
# In Docker, the URI will be set by the entrypoint script
# For local/PythonAnywhere, use the MySQL connection
default_uri = 'mysql+pymysql://pegasus:Redbar2024!!@pegasus.mysql.pythonanywhere-services.com/pegasus$CALLER_INFORMATION'
pythonanyhere_uri = os.getenv("PYTHONANYHERE_DB_URI")

# First try to use a fully formed URI from the environment
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

# If that's not available, check for component parts to build a PostgreSQL URI
if not SQLALCHEMY_DATABASE_URI:
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # If all PostgreSQL components are available, build the URI
    if db_user and db_password and db_host and db_port and db_name:
        try:
            # Try to convert port to integer to validate it
            int(db_port)
            SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        except ValueError:
            # If port is not a valid number, fall back to default
            SQLALCHEMY_DATABASE_URI = pythonanyhere_uri or default_uri
    else:
        # Fall back to default if no complete configuration is found
        SQLALCHEMY_DATABASE_URI = pythonanyhere_uri or default_uri

SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", "False").lower() == "true"

# ------------------------------
# Ngrok & Twilio Configuration
# ------------------------------
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "2TPx8vjcOGWQiJj5x3rgkJ09uQ0_6krep2WJjqsNyzMedv4ew")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "ACb8391ed8d92871d85180ca9adea481b6")
TWILIO_API_KEY_SID = os.getenv("TWILIO_API_KEY_SID", "SK55c8d2ec3e662acffb868fcc42ed75ac")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET", "Ky6uApOQMFAZKCbhe5aaZkyGIBzdIRMT")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "d4830ea0bb52ffdb63620c2333fcdd59")
# Twilio Phone Numbers - Main phone numbers
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER", "+18333247207")

# Owner phone numbers for notifications
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "+18333247207")  

# Customer service numbers by environment
CUSTOMER_SERVICE_NUMBER = os.getenv("CUSTOMER_SERVICE_NUMBER", "+18333247207")

# Test phone numbers - useful for validating SMS without sending to customers
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER", "+18333247207")

# Environment-specific owner numbers
if os.environ.get('FLASK_ENV') == 'staging' or os.environ.get('IS_STAGING'):
    # Staging environment numbers
    STAGING_OWNER_PHONE = os.getenv("STAGING_OWNER_PHONE", OWNER_PHONE_NUMBER)
    # Use staging owner number if we're in staging environment
    OWNER_PHONE_NUMBER = STAGING_OWNER_PHONE

# ------------------------------
# AssemblyAI (if used)
# ------------------------------
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "a116ce3f35164bd78f295ddd6ccd7ee0")

# ------------------------------
# OpenAI Configuration
# ------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

# ------------------------------
# Stripe Configuration
# ------------------------------
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", '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')
STRIPE_PRODUCT_ID = os.getenv("STRIPE_PRODUCT_ID", 'prod_QbXflydy7HavBH')

# ------------------------------
# Deliverect Configuration
# ------------------------------
DELIVERECT_CLIENT_ID = os.getenv("DELIVERECT_CLIENT_ID", 'w2ajqOd1CMUsRBPF')
DELIVERECT_CLIENT_SECRET = os.getenv("DELIVERECT_CLIENT_SECRET", 'byOTwZy7CvhgFgQBuvdGVZVcWoxlfTj1')
DELIVERECT_API_URL = os.getenv("DELIVERECT_API_URL", 'https://api.staging.deliverect.com/nextgen/order/66e88f33475a66c53e90e62b')

# ------------------------------
# Local File Paths
# ------------------------------
MENU_FILE_PATH = os.getenv("MENU_FILE_PATH", "app/menu_data.json")

# Add a more robust fallback to account for deployment paths
if not os.path.exists(MENU_FILE_PATH):
    # Try to find the menu_data.json in the current directory or parent directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    potential_paths = [
        os.path.join(current_dir, 'menu_data.json'),
        os.path.join(os.path.dirname(current_dir), 'menu_data.json'),
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'menu_data.json'),
        "/home/proxyie/MySoftware/RedBarSushiAI/menu_data.json"  # Local dev path
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            MENU_FILE_PATH = path
            break

# ------------------------------
# Base URL Configuration
# ------------------------------
# Check if BASE_URL is explicitly set in environment - this takes precedence
if os.getenv('BASE_URL'):
    BASE_URL = os.getenv('BASE_URL')
# Otherwise, auto-detect environment and set appropriate base URL
elif os.environ.get('RENDER', '').lower() == 'true' or os.environ.get('RENDER_SERVICE_ID'):
    # Use Render-specific URL
    BASE_URL = 'https://redbarsushiai.onrender.com'
elif not os.environ.get('DISABLE_PYTHONANYWHERE_DETECTION', '').lower() == 'true' and any(path.endswith('pythonanywhere-services.com') for path in [default_uri, pythonanyhere_uri or '']):
    # Running on PythonAnywhere but force the Render URL for consistency
    BASE_URL = 'https://redbarsushiai.onrender.com'
else:
    # Default BASE_URL for local development
    BASE_URL = 'http://localhost:5000'

# Final safety check - NEVER use pythonanywhere.com in BASE_URL
if 'pythonanywhere.com' in BASE_URL:
    BASE_URL = 'https://redbarsushiai.onrender.com'

# Log the selected BASE_URL
print(f"Using BASE_URL: {BASE_URL}")

# ------------------------------
# Redis and Celery Configuration
# ------------------------------
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
