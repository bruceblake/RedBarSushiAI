#!/bin/bash
set -e

# Set environment variables to indicate we're in Docker
export DOCKER=true

# Set RENDER flag if this is running on Render
if [ -n "$RENDER_SERVICE_ID" ]; then
    export RENDER=true
    echo "Running on Render (Service ID: $RENDER_SERVICE_ID)"
fi

# Debug information
echo "DEBUG: Starting Docker entrypoint script"
echo "DEBUG: Environment variables: DB_HOST=$DB_HOST, DB_PORT=$DB_PORT, DB_NAME=$DB_NAME"
echo "DEBUG: Current directory: $(pwd)"
echo "DEBUG: Directory contents: $(ls -la)"

# Expand environment variables in the SQLALCHEMY_DATABASE_URI
if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
    # Check if DB_HOST is "db" - this is only for local docker-compose
    if [ "$DB_HOST" = "db" ] && [ "$RENDER" = "true" ]; then
        # In Render, we need to use the actual database URL from the environment
        echo "WARNING: DB_HOST is set to 'db' but we're running on Render. Looking for RENDER_DATABASE_URL..."
        if [ -n "$RENDER_DATABASE_URL" ]; then
            export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
            echo "Using RENDER_DATABASE_URL for database connection"
        else
            export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            echo "WARNING: Using potentially incorrect database URL. RENDER_DATABASE_URL is not set."
        fi
    else
        # Normal case - construct the URI from parts
        export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
        echo "Database URI set to postgresql connection string (credentials hidden)"
    fi
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
    
    # Check database connection before starting server
    echo "Testing database connection..."
    echo "SQLALCHEMY_DATABASE_URI: ${SQLALCHEMY_DATABASE_URI:0:25}..." # Show just the start, not credentials
    
    # If using RENDER_DATABASE_URL directly, log and use it
    if [ -n "$RENDER_DATABASE_URL" ]; then
        echo "RENDER_DATABASE_URL is set, using it directly"
        export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
    fi
    
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
    
    # Show database info without revealing password
    parts = db_uri.split('@')
    if len(parts) > 1:
        auth_parts = parts[0].split(':')
        if len(auth_parts) > 1:
            username = auth_parts[-2].split('/')[-1]  # Extract username
            print(f'Connecting as user: {username}', file=sys.stderr)
            host_part = parts[1].split('/')
            print(f'To database host: {host_part[0]}', file=sys.stderr)
    
    print('Creating database engine...', file=sys.stderr)
    engine = create_engine(db_uri)
    print('Connecting to database...', file=sys.stderr)
    connection = engine.connect()
    print('Connected!', file=sys.stderr)
    connection.close()
    print('Database connection test successful!', file=sys.stderr)
except SQLAlchemyError as e:
    print(f'ERROR connecting to database: {str(e)}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Unexpected error during database test: {str(e)}', file=sys.stderr)
    sys.exit(1)
"
    
    # Check Python dependencies
    echo "Checking for required modules..."
    python -c "
import sys
required_modules = ['psycopg2', 'flask_sqlalchemy', 'gunicorn', 'gevent', 'flask', 'gunicorn']
missing = []

for module in required_modules:
    try:
        __import__(module)
        print(f'✓ {module}', file=sys.stderr)
    except ImportError:
        missing.append(module)
        print(f'✗ {module} - MISSING', file=sys.stderr)

if missing:
    missing_str = ", ".join(missing)
    print(f'ERROR: Missing required modules: {missing_str}', file=sys.stderr)
    sys.exit(1)
else:
    print('All required modules are available', file=sys.stderr)
"
    
    # Try both entry points (run.py and wsgi.py)
    if [ -f "wsgi.py" ]; then
        echo "DEBUG: Using wsgi.py entry point"
        exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" --log-level=debug "wsgi"
    else
        echo "DEBUG: Using run:app entry point"
        exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" --log-level=debug "run:app"
    fi
fi