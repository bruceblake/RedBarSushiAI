#!/bin/bash
set -e

# Set environment variables to indicate we're in Docker
export DOCKER=true

# Always use a virtual X server (Xvfb) for OpenAI Realtime client
export USE_XVFB=true

echo "===== Setting up virtual X display for OpenAI Realtime client ====="

# Make sure X11 packages are installed
if ! command -v Xvfb &> /dev/null; then
    echo "Installing Xvfb and X11 dependencies..."
    apt-get update -y && apt-get install -y xvfb x11-utils xorg libxrender1 libxtst6 libxi6 dbus-x11
    if [ $? -ne 0 ]; then
        echo "⚠️ Failed to install X11 dependencies. Will try with existing packages."
    fi
fi

# Try various methods to start Xvfb and ensure it's running properly
echo "Starting virtual X server..."

# Kill any existing Xvfb processes to avoid conflicts
pkill Xvfb 2>/dev/null || true
    
# Try multiple displays (:99, :1, :0) in case some are already in use
for display_num in 99 1 0; do
    echo "Trying display :${display_num}..."
    Xvfb :${display_num} -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
    XVFB_PID=$!
    export DISPLAY=:${display_num}
    sleep 3  # Give it time to start
        
    # Install xdpyinfo if not present
    if ! command -v xdpyinfo &> /dev/null; then
        apt-get update -y && apt-get install -y x11-utils
    fi
        
    # Test with xdpyinfo
    if xdpyinfo >/dev/null 2>&1; then
        echo "✅ Successfully started Xvfb on display :${display_num}"
        export X11_SETUP_SUCCESS=true
        break
    else
        echo "❌ Failed to connect to display :${display_num}"
        kill $XVFB_PID 2>/dev/null || true
        unset XVFB_PID
    fi
done

# Register a trap to kill Xvfb on exit
trap 'if [ -n "$XVFB_PID" ]; then echo "Cleaning up Xvfb process..."; kill $XVFB_PID 2>/dev/null || true; fi' EXIT INT TERM

# Set appropriate environment variables based on whether Xvfb was successfully started
if [ -n "$XVFB_PID" ] && [ "$X11_SETUP_SUCCESS" = "true" ]; then
    # X11 mode with virtual display
    echo "✅ Virtual X display is working"
    export PYNPUT_HEADLESS=0
    export NO_X11=0
    export HEADLESS=0
    export OPENAI_REALTIME_NO_DISPLAY=0
    
    # Export this so other processes can detect if X11 was successfully set up
    export X11_SETUP_SUCCESS=true
    
    # Create .Xauthority file if it doesn't exist (sometimes needed)
    touch ~/.Xauthority 2>/dev/null || true
    
    # Run a final test with xlogo if available
    if command -v xlogo &> /dev/null; then
        echo "Running additional X server test with xlogo..."
        xlogo -display $DISPLAY 2>/dev/null &
        XLOGO_PID=$!
        sleep 1
        kill $XLOGO_PID 2>/dev/null || true
    fi
    
    echo "🖥️ Using OpenAI Realtime client with virtual X display: $DISPLAY"
    export OPENAI_REALTIME_AVAILABLE=1
else
    # Headless mode - using direct WebSocket implementation
    echo "❌ Could not set up working X display. Using headless mode instead."
    export PYNPUT_HEADLESS=1
    export NO_X11=1
    export HEADLESS=1
    export OPENAI_REALTIME_NO_DISPLAY=1
    
    # Remove DISPLAY to prevent X11 connection attempts
    if [ -n "$DISPLAY" ]; then
        echo "Unsetting DISPLAY variable to prevent X11 connection attempts"
        unset DISPLAY
    fi
    
    echo "💻 Running in headless mode (using dual-backend WebSocket implementation)"
    # Still mark realtime as available since we're using our custom implementation
    export OPENAI_REALTIME_AVAILABLE=1
fi

export PYTHONPATH=/app:$PYTHONPATH

# Set environment variables for audio processing
export OPENAI_STREAMING=1            # Enable streaming for standard OpenAI API
export NODE_TLS_REJECT_UNAUTHORIZED=0 # Allow self-signed certificates in dev environments
export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"

# Install required packages
echo "Installing or upgrading required dependencies..."
pip install --no-cache-dir websockets==13.1 
pip install --no-cache-dir aiohttp==3.11.13
pip install --no-cache-dir python-socketio==5.8.0 eventlet==0.33.3 gevent==23.9.1 gevent-websocket==0.10.1
pip install --no-cache-dir --upgrade openai-realtime-client==0.1.0

# Check if installation was successful
if [ -f "/usr/local/lib/python3.11/site-packages/openai_realtime_client/__init__.py" ]; then
    echo "✅ OpenAI Realtime client installed successfully!"
else
    echo "⚠️ Could not find OpenAI Realtime client, using fallback methods"
fi

# Run the test script to verify the setup
echo "Running test script to verify setup..."
if [ -f "test_realtime_client.py" ]; then
    # Use X11 environment variables before running test
    if [ -n "$DISPLAY" ] && [ "$X11_SETUP_SUCCESS" = "true" ]; then
        # Set up X11 environment variables
        export PYNPUT_HEADLESS=0
        export NO_X11=0
        export HEADLESS=0
        export OPENAI_REALTIME_NO_DISPLAY=0
        export USE_XVFB=true
        
        echo "Running test with X11 environment: DISPLAY=$DISPLAY"
    else
        echo "Running test without X11 environment"
    fi
    
    # Run the test script directly
    python test_realtime_client.py || true
fi

# Run diagnostic script if it exists
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
    
    # Make sure the DISPLAY environment variable is in the worker's environment
    if [ -n "$DISPLAY" ]; then
        echo "Ensuring DISPLAY=$DISPLAY is passed to the workers"
        
        # Create a wrapper script to set environment variables for gunicorn workers
        cat > /tmp/gunicorn_env_wrapper.py << 'EOF'
import os
import sys

# Ensure all environment variables are passed to workers
os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':99')
os.environ['PYNPUT_HEADLESS'] = '0'
os.environ['NO_X11'] = '0' 
os.environ['HEADLESS'] = '0'
os.environ['OPENAI_REALTIME_NO_DISPLAY'] = '0'
os.environ['X11_SETUP_SUCCESS'] = 'true'  # Indicate X11 is working

# Import the actual app
sys.path.insert(0, '/app')
if os.path.exists('/app/wsgi.py'):
    from wsgi import app
else:
    from run import app

# Export the app for gunicorn
application = app
EOF
        
        # Use environment variables directly with Gunicorn
        echo "DEBUG: Using direct environment variables with Gunicorn"
        
        # Export all X11 variables explicitly for Gunicorn workers
        export DISPLAY=${DISPLAY}
        export PYNPUT_HEADLESS=0
        export NO_X11=0
        export HEADLESS=0
        export OPENAI_REALTIME_NO_DISPLAY=0
        export X11_SETUP_SUCCESS=true
        
        if [ -f "wsgi.py" ]; then
            echo "DEBUG: Using wsgi.py entry point with memory optimizations"
            exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                         --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                         --worker-connections=500 --timeout=120 "wsgi"
        else
            echo "DEBUG: Using run:app entry point with memory optimizations"
            exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                         --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                         --worker-connections=500 --timeout=120 "run:app"
        fi
    else
        # Standard startup if DISPLAY isn't set
        if [ -f "wsgi.py" ]; then
            echo "DEBUG: Using wsgi.py entry point with memory optimizations"
            exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                         --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                         --worker-connections=500 --timeout=120 "wsgi"
        else
            echo "DEBUG: Using run:app entry point with memory optimizations"
            exec gunicorn --worker-class=gevent --workers=1 --threads=4 --bind="0.0.0.0:$PORT" \
                         --log-level=debug --max-requests=500 --max-requests-jitter=50 \
                         --worker-connections=500 --timeout=120 "run:app"
        fi
    fi
fi