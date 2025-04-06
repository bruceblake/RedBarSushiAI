#!/bin/bash
# Specialized entrypoint for Render.com deployment
set -e

echo "Starting Render entrypoint script"

# Set environment flags
export DOCKER=true
export RENDER=true

# Use Render's database URL if available (this is the most reliable approach)
if [ -n "$RENDER_DATABASE_URL" ]; then
    echo "Using RENDER_DATABASE_URL for database connection"
    export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
elif [ -n "$INTERNAL_DATABASE_URL" ]; then
    echo "Using INTERNAL_DATABASE_URL for database connection"
    export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
else
    echo "WARNING: No Render database URL found, will try to construct from components"
    # Construct from components if needed
    if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
        export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
        echo "Database URI constructed from components"
    else
        echo "ERROR: Missing database configuration"
        echo "Please set RENDER_DATABASE_URL or provide individual DB_* variables"
        exit 1
    fi
fi

# Test the database connection
echo "Testing database connection..."
python test_db.py
if [ $? -ne 0 ]; then
    echo "Database connection test failed! Check your credentials and try again."
    exit 1
fi

# Initialize database if needed
echo "Creating database tables if they don't exist..."
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"

# Determine which process to start based on the PROCESS environment variable
if [ "$PROCESS" = "celery" ]; then
    echo "Starting Celery worker..."
    exec celery -A celery_app worker --loglevel=INFO
elif [ "$PROCESS" = "celery-beat" ]; then
    echo "Starting Celery beat scheduler..."
    exec celery -A celery_app beat --loglevel=INFO
else
    # Default: start the web server
    # Check if PORT is set by Render
    if [ -z "$PORT" ]; then
        echo "WARNING: PORT environment variable not set, defaulting to 8080"
        export PORT=8080
    fi
    
    echo "Starting web server on port $PORT..."
    exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" "wsgi"
fi