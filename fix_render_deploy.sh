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

# Fix database init function name in main.py
log "Fixing main.py db initialization functions..."
sed -i 's/from app.db_async import init_db/from app.db_async import init_database/g' main.py
sed -i 's/await init_db()/await init_database()/g' main.py
sed -i 's/verify_connection_async/verify_connection/g' main.py

# Make entrypoint script executable
log "Making entrypoint script executable..."
chmod +x fastapi_render_entrypoint.sh

log "All fixes applied. Ready for deployment."