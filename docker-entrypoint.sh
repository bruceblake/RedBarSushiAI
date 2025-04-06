#!/bin/bash
set -e

# Set environment variables to indicate we're in Docker
export DOCKER=true

# Debug information
echo "DEBUG: Starting Docker entrypoint script"
echo "DEBUG: Environment variables: DB_HOST=$DB_HOST, DB_PORT=$DB_PORT, DB_NAME=$DB_NAME"
echo "DEBUG: Current directory: $(pwd)"
echo "DEBUG: Directory contents: $(ls -la)"

# Expand environment variables in the SQLALCHEMY_DATABASE_URI
if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
    export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "Database URI set to postgresql connection string (credentials hidden)"
else
    echo "DEBUG: Missing one or more database environment variables"
    echo "DEBUG: DB_USER set: [$(if [ -n "$DB_USER" ]; then echo "YES"; else echo "NO"; fi)]"
    echo "DEBUG: DB_PASSWORD set: [$(if [ -n "$DB_PASSWORD" ]; then echo "YES"; else echo "NO"; fi)]"
    echo "DEBUG: DB_HOST set: [$(if [ -n "$DB_HOST" ]; then echo "YES"; else echo "NO"; fi)]"
    echo "DEBUG: DB_PORT set: [$(if [ -n "$DB_PORT" ]; then echo "YES"; else echo "NO"; fi)]"
    echo "DEBUG: DB_NAME set: [$(if [ -n "$DB_NAME" ]; then echo "YES"; else echo "NO"; fi)]"
fi

# Initialize database if needed
echo "Creating database tables if they don't exist..."
python -c "
from app import create_app, db
import os
print('DEBUG: Python script starting')
print('DEBUG: SQLALCHEMY_DATABASE_URI:', os.environ.get('SQLALCHEMY_DATABASE_URI', 'Not set'))
app = create_app()
print('DEBUG: App created')
with app.app_context():
    print('DEBUG: Creating database tables')
    db.create_all()
    print('DEBUG: Database tables created successfully')
"

# Determine which process to start based on the PROCESS environment variable
# This allows us to run the web server or Celery worker with the same Docker image
if [ "$PROCESS" = "celery" ]; then
    echo "Starting Celery worker..."
    exec celery -A celery_app worker --loglevel=INFO
elif [ "$PROCESS" = "celery-beat" ]; then
    echo "Starting Celery beat scheduler..."
    exec celery -A celery_app beat --loglevel=INFO
else
    # Default: start the web server
    # Check if PORT is set
    if [ -z "$PORT" ]; then
        echo "ERROR: PORT environment variable not set, defaulting to 8080"
        export PORT=8080
    fi
    
    echo "Starting web server on port $PORT..."
    # Use gunicorn with gevent worker for websocket support
    echo "DEBUG: Launch command: gunicorn --worker-class=gevent --workers=3 --threads=3 --bind=\"0.0.0.0:$PORT\" --log-level=debug \"run:app\""
    
    # Try to find run.py to make sure it exists
    if [ -f "run.py" ]; then
        echo "DEBUG: Found run.py in current directory"
    else
        echo "ERROR: run.py not found in current directory"
        echo "DEBUG: Files in current directory:"
        ls -la
    fi
    
    # Try both entry points (run.py and wsgi.py)
    if [ -f "wsgi.py" ]; then
        echo "DEBUG: Using wsgi.py entry point"
        exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" --log-level=debug "wsgi"
    else
        echo "DEBUG: Using run:app entry point"
        exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" --log-level=debug "run:app"
    fi
fi