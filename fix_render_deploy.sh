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

# Fix database init function name in main.py
log "Fixing main.py db initialization functions..."
sed -i 's/from app.db_async import init_db/from app.db_async import init_database/g' main.py
sed -i 's/await init_db()/await init_database()/g' main.py
sed -i 's/verify_connection_async/verify_connection/g' main.py

# Make entrypoint script executable
log "Making entrypoint script executable..."
chmod +x fastapi_render_entrypoint.sh

log "All fixes applied. Ready for deployment."