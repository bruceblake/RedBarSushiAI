#!/bin/bash
set -e

# This script fixes deployment issues for Render

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

log "Starting Render deployment fixes..."

# Check if running in Render
if [ -n "$RENDER_SERVICE_ID" ]; then
  log "Detected Render environment"
  export RENDER=true
  export FORCE_HEADLESS=true
else
  log "Not running in Render, using local environment settings"
fi

# Fix environment variables
log "Setting environment variables..."
echo "APP_SECRET_KEY=render_secret_key_placeholder" >> .env
echo "TWILIO_PHONE_NUMBER=+10000000000" >> .env
echo "DELIVERECT_API_KEY=dummy-key-replace-in-prod" >> .env
echo "DELIVERECT_API_URL=https://api.staging.deliverect.com/v2/orders" >> .env
echo "DELIVERECT_CLIENT_ID=dummy-client-id-replace-in-prod" >> .env
echo "DELIVERECT_CLIENT_SECRET=dummy-client-secret-replace-in-prod" >> .env
echo "STRIPE_API_KEY=sk-stripe-dummy-replace-in-prod" >> .env

# Fix redis_async.py _memory_cache issue
log "Fixing redis_async.py..."
sed -i 's/global _memory_cache, _memory_cache_timestamps/_memory_cache.clear()\n            _memory_cache_timestamps.clear()/g' app/redis_async.py

# Fix circular import in db.py
log "Fixing circular import in db.py..."
sed -i 's/from app import db as _db/# Import Flask-SQLAlchemy directly to avoid circular import\nfrom flask_sqlalchemy import SQLAlchemy\n_db = SQLAlchemy()/g' app/db.py

# Fix models to use SQLAlchemy 2.0 style imports
log "Creating compatibility module for SQLAlchemy models..."
cat > app/compat_models.py << 'EOF'
"""
Compatibility module for database models transitioning from Flask-SQLAlchemy to SQLAlchemy 2.0.
This module provides compatibility classes and functions to help transition models from the
Flask-SQLAlchemy style to the SQLAlchemy 2.0 async style.
"""

import logging
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base

# Import the SQLAlchemy 2.0 Base from db_async
from app.db_async import Base

# Define the TimestampMixin using SQLAlchemy 2.0 style
class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps using SQLAlchemy 2.0 style."""
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create a compatibility class to replace db
class DBCompat:
    """Compatibility class to replace Flask-SQLAlchemy db object."""
    Model = Base
    Column = Column
    String = String
    Integer = Integer
    Float = Float
    DateTime = DateTime
    ForeignKey = ForeignKey
    Text = Text
    Boolean = Boolean
    Table = Table
    
    @staticmethod
    def relationship(*args, **kwargs):
        return relationship(*args, **kwargs)
    
    class func:
        @staticmethod
        def current_timestamp():
            return func.current_timestamp()
    
    @staticmethod
    def session():
        # This is just a placeholder - using SQLAlchemy 2.0 async sessions instead
        return None

# Export a compatibility db object
db = DBCompat()
EOF

# Fix app/models/order.py to use compatibility module
log "Fixing order.py to use SQLAlchemy 2.0 style..."
sed -i 's/from app import db/from app.compat_models import db, TimestampMixin/g' app/models/order.py
sed -i 's/from app.models.base import TimestampMixin//g' app/models/order.py

# Fix app/models/location.py to use compatibility module 
log "Fixing location.py to use SQLAlchemy 2.0 style..."
sed -i 's/from app import db/from app.compat_models import db, TimestampMixin/g' app/models/location.py
sed -i 's/from app.models.base import TimestampMixin//g' app/models/location.py

# Fix app/models/menu.py to use compatibility module
log "Fixing menu.py to use SQLAlchemy 2.0 style..."
sed -i 's/from app import db/from app.compat_models import db, TimestampMixin/g' app/models/menu.py
sed -i 's/from app.models.base import TimestampMixin//g' app/models/menu.py

# Fix syntax error in voice_async.py
log "Fixing syntax error in voice_async.py..."
sed -i 's/        })$/        )/g' app/api/voice_async.py

# Fix Deliverect auth imports
log "Fixing Deliverect auth imports..."
sed -i 's/from app.config import DELIVERECT_CLIENT_ID, DELIVERECT_CLIENT_SECRET/from app.config import settings/g' app/utils/deliverect/auth.py
sed -i 's/client_id = DELIVERECT_CLIENT_ID/client_id = settings.DELIVERECT_CLIENT_ID/g' app/utils/deliverect/auth.py
sed -i 's/client_secret = DELIVERECT_CLIENT_SECRET/client_secret = settings.DELIVERECT_CLIENT_SECRET/g' app/utils/deliverect/auth.py

# Fix all direct imports from app.config
log "Fixing all direct imports from app.config..."
python3 fix_config_imports.py app

# Fix API model imports
log "Fixing API model imports..."
python3 fix_api_imports.py

# Fix JSONB handling in menu.py
log "Fixing JSONB handling in menu.py..."
cat > app/jsonb_helper.py << 'EOF'
"""
Helper module for handling PostgreSQL JSONB type safely.
"""
import logging
import os
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Text
from app.db_async import DATABASE_URL
from app.config import settings

# Set up logger
logger = logging.getLogger(__name__)

# Check if using PostgreSQL based on connection string
def is_postgresql():
    """Determine if using PostgreSQL based on DATABASE_URL"""
    # On Render, we know it's always PostgreSQL
    if os.environ.get("RENDER") == "true" or getattr(settings, "RENDER", False):
        return True
    
    # Otherwise check the connection string
    db_url = getattr(settings, "DATABASE_URL", None) or DATABASE_URL
    return db_url.startswith('postgresql+asyncpg://') or db_url.startswith('postgresql://')

# Get appropriate column type
def get_jsonb_column():
    """Get the appropriate column type for JSON data"""
    if is_postgresql():
        logger.info("Using PostgreSQL JSONB for properties column")
        return JSONB
    else:
        logger.info("Using Text for properties column (non-PostgreSQL database)")
        return Text

# Get default value
def get_default_value():
    """Get appropriate default value for the column type"""
    if is_postgresql():
        return dict
    else:
        return lambda: '{}'
EOF

# Update menu.py to use the jsonb_helper
sed -i 's/^def is_postgresql.*$/from app.jsonb_helper import is_postgresql, get_jsonb_column, get_default_value/g' app/models/menu.py
sed -i '/^# Function to determine if we/,/^def get_jsonb_column/d' app/models/menu.py

# Fix database init function name in main.py
log "Fixing main.py db initialization functions..."
sed -i 's/from app.db_async import init_db/from app.db_async import init_database/g' main.py
sed -i 's/await init_db()/await init_database()/g' main.py
sed -i 's/verify_connection_async/verify_connection/g' main.py

# Fix menu_cache_sdk.py to not rely on Flask's create_app
log "Fixing menu_cache_sdk.py Redis client issues..."
cat > fix_menu_cache_sdk.py << 'EOF'
#!/usr/bin/env python3
import os
import re

# Path to the menu_cache_sdk.py file
menu_cache_sdk_path = 'app/utils/menu_cache_sdk.py'

if not os.path.exists(menu_cache_sdk_path):
    print(f"Error: {menu_cache_sdk_path} not found!")
    exit(1)

# Read the file
with open(menu_cache_sdk_path, 'r') as f:
    content = f.read()

# Replace the import for get_redis_client
replacement = '''
def get_redis_client():
    """
    Get a Redis client connection.
    
    Returns:
        Optional[redis.Redis]: Redis client or None if not available
    """
    try:
        # Try to import settings first
        try:
            from app.config import settings
            redis_url = settings.REDIS_URL
        except (ImportError, AttributeError):
            # Fall back to environment variable
            redis_url = os.environ.get("REDIS_URL")
        
        if redis_url:
            logger.info(f"Creating Redis client with URL: {redis_url.split('@')[-1] if '@' in redis_url else 'redis://localhost'}")
            return redis.Redis.from_url(redis_url)
        
        # Last resort - try localhost
        logger.warning("No Redis URL found, trying localhost")
        return redis.Redis(host="localhost", port=6379, db=0)
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None
'''

# Remove the existing import for get_redis_client
content = re.sub(r'from app\.utils\.agents_sdk import get_redis_client\s+', '', content)

# Find where to insert the new function
# Insert after logger initialization but before any other code
logger_pattern = r'logger = logging\.getLogger\(__name__\)'
content = re.sub(f'{logger_pattern}', f'{logger_pattern}\n{replacement}', content)

# Write the changes back
with open(menu_cache_sdk_path, 'w') as f:
    f.write(content)

print(f"Successfully updated {menu_cache_sdk_path}")
EOF

# Execute the fix script
python3 fix_menu_cache_sdk.py

# Make entrypoint script executable
log "Making entrypoint script executable..."
chmod +x fastapi_render_entrypoint.sh

log "All fixes applied. Ready for deployment."