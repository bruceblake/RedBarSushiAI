#!/bin/bash
# Specialized entrypoint for Render.com deployment
set -e

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

log "Starting Render entrypoint script"

# Set environment flags
export DOCKER=true
export RENDER=true

# Database connection setup with error handling
setup_database_connection() {
    # Use Render's database URL if available (most reliable approach)
    if [ -n "$RENDER_DATABASE_URL" ]; then
        log "Using RENDER_DATABASE_URL for database connection"
        export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
        return 0
    elif [ -n "$INTERNAL_DATABASE_URL" ]; then
        log "Using INTERNAL_DATABASE_URL for database connection"
        export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
        return 0
    else
        log "WARNING: No Render database URL found, trying to construct from components"
        # Construct from components if needed
        if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
            export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            log "Database URI constructed from components"
            return 0
        else
            log "ERROR: Missing database configuration"
            log "Please set RENDER_DATABASE_URL or provide individual DB_* variables"
            return 1
        fi
    fi
}

# Try to set up database connection
if ! setup_database_connection; then
    log "Failed to set up database connection. Exiting."
    exit 1
fi

# Test the database connection with retry logic
test_database_connection() {
    local max_retries=5
    local retry_count=0
    local retry_delay=5
    
    while [ $retry_count -lt $max_retries ]; do
        log "Testing database connection (attempt $(($retry_count + 1))/$max_retries)..."
        
        # Simple connection test using Python
        python -c "
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

try:
    db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        print('ERROR: SQLALCHEMY_DATABASE_URI not set', file=sys.stderr)
        sys.exit(1)
    
    print('Creating database engine...', file=sys.stderr)
    engine = create_engine(db_uri)
    print('Connecting to database...', file=sys.stderr)
    connection = engine.connect()
    print('Connected!', file=sys.stderr)
    connection.close()
    print('Database connection test successful!', file=sys.stderr)
    sys.exit(0)
except Exception as e:
    print(f'Error connecting to database: {str(e)}', file=sys.stderr)
    sys.exit(1)
"
        
        if [ $? -eq 0 ]; then
            log "Database connection successful"
            return 0
        else
            retry_count=$((retry_count + 1))
            log "Connection failed. Retrying in $retry_delay seconds..."
            sleep $retry_delay
            retry_delay=$((retry_delay * 2)) # Exponential backoff
        fi
    done
    
    log "Database connection failed after $max_retries attempts. Exiting."
    return 1
}

# Try to connect to the database with retries
if ! test_database_connection; then
    log "Giving up on database connection. Exiting."
    exit 1
fi

# Initialize database with error handling
log "Creating database tables if they don't exist..."
python -c "
import sys
from app import create_app, db

try:
    app = create_app()
    with app.app_context():
        db.create_all()
        print('Database tables created successfully')
        sys.exit(0)
except Exception as e:
    print(f'Error creating database tables: {str(e)}')
    sys.exit(1)
"

# Check the return code
if [ $? -ne 0 ]; then
    log "Failed to create database tables. Continuing anyway..."
    # We continue here as tables might already exist
fi

# Determine which process to start based on the PROCESS environment variable
if [ "$PROCESS" = "celery" ]; then
    log "Starting Celery worker with memory optimizations..."
    # Set Celery concurrency based on available resources
    CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-2}
    # Set memory limit with fallback
    CELERY_MAX_MEMORY=${CELERY_MAX_MEMORY:-50000}
    
    exec celery -A celery_app worker \
        --loglevel=INFO \
        --concurrency=$CELERY_CONCURRENCY \
        --max-memory-per-child=$CELERY_MAX_MEMORY \
        --max-tasks-per-child=10
        
elif [ "$PROCESS" = "celery-beat" ]; then
    log "Starting Celery beat scheduler..."
    exec celery -A celery_app beat --loglevel=INFO
else
    # Default: start the web server
    # Check if PORT is set by Render
    if [ -z "$PORT" ]; then
        log "WARNING: PORT environment variable not set, defaulting to 8080"
        export PORT=8080
    fi
    
    # Determine worker count based on CPU cores with reasonable defaults
    WORKER_COUNT=${WORKER_COUNT:-3}
    THREAD_COUNT=${THREAD_COUNT:-3}
    
    log "Starting web server on port $PORT with $WORKER_COUNT workers and $THREAD_COUNT threads..."
    exec gunicorn \
        --worker-class=gevent \
        --workers=$WORKER_COUNT \
        --threads=$THREAD_COUNT \
        --timeout=120 \
        --keep-alive=5 \
        --max-requests=1000 \
        --max-requests-jitter=50 \
        --bind="0.0.0.0:$PORT" \
        --log-level=info \
        "wsgi"
fi