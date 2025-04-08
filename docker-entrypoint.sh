#!/bin/bash
set -e

# Set environment variables to indicate we're in Docker
export DOCKER=true

# Always use a virtual X server (Xvfb) for OpenAI Realtime client
# Only fall back to headless mode if Xvfb fails
export USE_XVFB=true

if [ "$USE_XVFB" = "true" ]; then
  echo "Setting up virtual X display with Xvfb"
  
  # Install Xvfb if not already installed
  if ! command -v Xvfb &> /dev/null; then
    echo "Installing Xvfb and X11 dependencies..."
    apt-get update && apt-get install -y xvfb x11-utils xorg libxrender1 libxtst6 libxi6 dbus-x11
    if [ $? -ne 0 ]; then
      echo "⚠️ Failed to install X11 dependencies. Will try to continue anyway."
    fi
  fi
  
  # Kill any existing Xvfb processes to avoid conflicts
  pkill Xvfb || true
  
  # Start Xvfb with more options for better compatibility
  Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
  export DISPLAY=:99
  
  # Wait for Xvfb to start
  sleep 3
  
  echo "Testing X server connection..."
  if ! command -v xdpyinfo &> /dev/null; then
    echo "xdpyinfo not found, installing x11-utils..."
    apt-get update && apt-get install -y x11-utils
    if [ $? -ne 0 ]; then
      echo "⚠️ Failed to install x11-utils. Will try to continue anyway."
    fi
  fi
  
  # Test the X server connection
  xdpyinfo > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "✅ X server is running and accessible at DISPLAY=:99"
    # Make sure OpenAI Realtime client uses this display
    export OPENAI_REALTIME_NO_DISPLAY=0
    export DISPLAY=:99
    echo "DISPLAY environment variable set to: $DISPLAY"
    
    # Create .Xauthority file if it doesn't exist (sometimes needed)
    touch ~/.Xauthority 2>/dev/null || true
    
    # Test X server again with a simple X11 app if available
    if command -v xlogo &> /dev/null; then
      echo "Running additional X server test with xlogo..."
      xlogo -display :99 2>/dev/null &
      XLOGO_PID=$!
      sleep 1
      kill $XLOGO_PID 2>/dev/null || true
    fi
  else
    echo "❌ X server connection failed. Trying one more approach before falling back..."
    
    # Try a different display number
    pkill Xvfb || true
    Xvfb :1 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
    export DISPLAY=:1
    sleep 2
    
    # Test again
    xdpyinfo > /dev/null 2>&1
    if [ $? -eq 0 ]; then
      echo "✅ X server is running on second attempt at DISPLAY=:1"
      export OPENAI_REALTIME_NO_DISPLAY=0
    else
      echo "❌ X server connection failed on second attempt. Falling back to headless mode."
      export PYNPUT_HEADLESS=1
      export NO_X11=1
      export HEADLESS=1
      export OPENAI_REALTIME_NO_DISPLAY=1
      unset DISPLAY
    fi
  fi
else
  # Set environment variables for completely headless operation
  export PYNPUT_HEADLESS=1
  export NO_X11=1
  export HEADLESS=1
  export OPENAI_REALTIME_NO_DISPLAY=1
  
  # Remove DISPLAY variable if it exists to prevent X11 connection attempts
  if [ -n "$DISPLAY" ]; then
    echo "Unsetting DISPLAY variable to prevent X11 connection attempts"
    unset DISPLAY
  fi
  
  echo "Running in fully headless mode without X11 requirements (using dual-backend WebSocket implementation)"
fi

export PYTHONPATH=/app:$PYTHONPATH

# Set environment variables for audio processing
export OPENAI_STREAMING=1            # Enable streaming for standard OpenAI API
export NODE_TLS_REJECT_UNAUTHORIZED=0 # Allow self-signed certificates in dev environments

# Configure Realtime API availability based on environment
if [ "$USE_XVFB" = "true" ] && [ -n "$DISPLAY" ]; then
  # If using Xvfb and it's working, enable the Realtime API
  echo "Enabling OpenAI Realtime client with virtual X display"
  export OPENAI_REALTIME_AVAILABLE=1
else
  # Default to using our custom WebSocket implementation instead
  echo "Using custom WebSocket implementation for OpenAI Realtime API"
  # This doesn't disable the API, just indicates we're using our custom implementation
  export OPENAI_REALTIME_AVAILABLE=1
fi

export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"

# Ensure we have all required dependencies in the right order
echo "Installing or upgrading required dependencies..."
pip install --no-cache-dir websockets==13.1 
pip install --no-cache-dir python-socketio==5.8.0 eventlet==0.33.3 gevent==23.9.1 gevent-websocket==0.10.1
pip install --no-cache-dir --upgrade openai-realtime-client==0.1.0

# Check if installation was successful
if [ -f "/usr/local/lib/python3.11/site-packages/openai_realtime_client/__init__.py" ]; then
    echo "✅ OpenAI Realtime client installed successfully!"
else
    echo "⚠️ Could not find OpenAI Realtime client, using fallback methods"
fi

# Run diagnostic script
if [ -f "diagnose.py" ]; then
    echo "Running diagnostic tests..."
    python diagnose.py
    echo "Diagnostic tests complete"
fi

# Explicitly set the Python path to avoid import issues
export PYTHONPATH=/app:$PYTHONPATH

# Set RENDER flag if this is running on Render
if [ -n "$RENDER_SERVICE_ID" ]; then
    export RENDER=true
    echo "Running on Render (Service ID: $RENDER_SERVICE_ID)"
    
    # Fix Redis URL format for Render if needed
    if [ -n "$REDIS_URL" ] && [[ "$REDIS_URL" != redis://* ]]; then
        echo "Fixing Redis URL format..."
        # Extract parts from the URL
        if [[ "$REDIS_URL" == *":"* ]] && [[ "$REDIS_URL" == *"/"* ]]; then
            # Format appears to be hostname:port/db
            HOST_PORT="${REDIS_URL%/*}"
            DB="${REDIS_URL#*/}"
            HOST="${HOST_PORT%:*}"
            PORT="${HOST_PORT#*:}"
            
            # Make sure DB is a number
            if ! [[ "$DB" =~ ^[0-9]+$ ]]; then
                DB=0
            fi
            
            # Construct proper Redis URL
            export REDIS_URL="redis://${HOST}:${PORT}/${DB}"
            export CELERY_BROKER_URL="$REDIS_URL"
            export CELERY_RESULT_BACKEND="$REDIS_URL"
            echo "Fixed Redis URL: ${REDIS_URL}"
        else
            # Just prefix with redis://
            export REDIS_URL="redis://${REDIS_URL}"
            export CELERY_BROKER_URL="$REDIS_URL"
            export CELERY_RESULT_BACKEND="$REDIS_URL"
            echo "Added redis:// prefix to Redis URL: ${REDIS_URL}"
        fi
    fi
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
    echo "Starting Celery worker with memory optimizations..."
    exec celery -A celery_app worker --loglevel=INFO --concurrency=2 --max-memory-per-child=50000
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
    print('ERROR: Missing required modules: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)
else:
    print('All required modules are available', file=sys.stderr)
"
    
    # Try both entry points (run.py and wsgi.py) with memory optimizations
    if [ -f "wsgi.py" ]; then
        echo "DEBUG: Using wsgi.py entry point with memory optimizations"
        # Removed the unsupported max-memory-per-child argument
        exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                     --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                     --worker-connections=500 --timeout=120 "wsgi"
    else
        echo "DEBUG: Using run:app entry point with memory optimizations"
        # Removed the unsupported max-memory-per-child argument
        exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                     --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                     --worker-connections=500 --timeout=120 "run:app"
    fi
fi