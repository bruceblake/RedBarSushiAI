#!/bin/bash
set -e

# Set environment variables to indicate we're in Docker
export DOCKER=true

# Always use headless mode for Render compatibility
export FORCE_HEADLESS=true
export PYNPUT_HEADLESS=1
export NO_X11=1
export HEADLESS=1
export OPENAI_REALTIME_NO_DISPLAY=1
export REALTIME_ENABLED=true

# Remove DISPLAY to prevent X11 connection attempts
if [ -n "$DISPLAY" ]; then
    echo "Unsetting DISPLAY variable to prevent X11 connection attempts"
    unset DISPLAY
fi

echo "💻 Running in headless mode with WebSocket implementation for Render compatibility"

# Enhanced environment handling for Render
if [ "$RENDER" = "true" ] || [ -n "$RENDER_SERVICE_ID" ]; then
    echo "Configuring for Render environment..."
    
    # Ensure environment is properly set for WebSockets
    export USE_DIRECT_WEBSOCKET=true
    export OPENAI_REALTIME_AVAILABLE=1
    
    echo "✅ Configured for Render environment with WebSocket implementation"
fi

export PYTHONPATH=/app:$PYTHONPATH

# Set environment variables for audio processing
export OPENAI_STREAMING=1             # Enable streaming for standard OpenAI API
export NODE_TLS_REJECT_UNAUTHORIZED=0 # Allow self-signed certificates in dev environments
export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"

# Set default environment variables if not provided
if [ -z "$REDIS_URL" ]; then
	echo "REDIS_URL not set. Using default value."
	export REDIS_URL="redis://localhost:6379/0"
	export CELERY_BROKER_URL="$REDIS_URL"
	export CELERY_RESULT_BACKEND="$REDIS_URL"
fi

# FastAPI does not need FLASK_APP
echo "Using FastAPI with Uvicorn"

# Use our comprehensive dependency installation script if available
if [ -f "install_all_dependencies.sh" ]; then
    echo "Running comprehensive dependency installation script..."
    chmod +x ./install_all_dependencies.sh
    # Set environment variables for the script to know we're in Render
    export RENDER=true
    export RENDER_SERVICE_ID=${RENDER_SERVICE_ID:-"docker-container"}
    
    # Run the installation script
    ./install_all_dependencies.sh || {
        echo "⚠️ Dependency installation script failed, falling back to manual installation"
        # Fall back to strict requirements
        if [ -f "requirements.strict.txt" ]; then
            echo "Installing from strict requirements file..."
            pip install --no-cache-dir -r requirements.strict.txt
            echo "✅ All dependencies installed successfully from requirements.strict.txt"
        else
            # Fall back to installing packages directly
            echo "⚠️ requirements.strict.txt not found, installing individually..."
            
            # Core web and WebSocket packages
            pip install --no-cache-dir flask==3.1.0
            pip install --no-cache-dir flask-sqlalchemy==3.1.1
            pip install --no-cache-dir flask-sock==0.7.0
            pip install --no-cache-dir uvicorn==0.34.0
            pip install --no-cache-dir websocket-client==1.7.0
            pip install --no-cache-dir gunicorn==23.0.0
            pip install --no-cache-dir websockets==13.1
            
            # Database and cache
            pip install --no-cache-dir psycopg2-binary==2.9.9
            pip install --no-cache-dir sqlalchemy==2.0.38
            pip install --no-cache-dir redis==5.2.1
            
            # API packages
            pip install --no-cache-dir openai==1.77.0
            pip install --no-cache-dir twilio==9.4.6
            pip install --no-cache-dir stripe==11.6.0
            
            # HTTP and networking
            pip install --no-cache-dir aiohttp==3.11.13
            pip install --no-cache-dir httpx==0.28.1
            
            # Async processing
            pip install --no-cache-dir celery==5.4.0
            
            # Audio processing
            pip install --no-cache-dir ffmpeg-python==0.2.0
        fi
    }
else
    # No installation script, use traditional approach
    echo "Installing all required dependencies with exact versions..."
    if [ -f "requirements.strict.txt" ]; then
        # Install everything from strict requirements
        pip install --no-cache-dir -r requirements.strict.txt
        echo "✅ All dependencies installed successfully from requirements.strict.txt"
    else
        # Fall back to installing packages directly
        echo "⚠️ requirements.strict.txt not found, installing individually..."
        
        # Core web and WebSocket packages
        pip install --no-cache-dir flask==3.1.0
        pip install --no-cache-dir flask-sqlalchemy==3.1.1
        pip install --no-cache-dir flask-sock==0.7.0
        pip install --no-cache-dir uvicorn==0.34.0
        pip install --no-cache-dir websocket-client==1.7.0
        pip install --no-cache-dir gunicorn==23.0.0
        pip install --no-cache-dir websockets==13.1
        
        # Database and cache
        pip install --no-cache-dir psycopg2-binary==2.9.9
        pip install --no-cache-dir sqlalchemy==2.0.38
        pip install --no-cache-dir redis==5.2.1
        
        # API packages
        pip install --no-cache-dir openai==1.77.0
        pip install --no-cache-dir twilio==9.4.6
        pip install --no-cache-dir stripe==11.6.0
        
        # HTTP and networking
        pip install --no-cache-dir aiohttp==3.11.13
        pip install --no-cache-dir httpx==0.28.1
        
        # Async processing
        pip install --no-cache-dir celery==5.4.0
        
        # Audio processing
        pip install --no-cache-dir ffmpeg-python==0.2.0
    fi
fi

# Try to install PyAudio directly with system dependencies
echo "Installing PyAudio..."
pip install --no-cache-dir pyaudio==0.2.14 || {
    echo "⚠️ PyAudio installation failed - continuing anyway as this is not critical"
    # Try alternative installation methods
    if command -v apt-get > /dev/null; then
        echo "Trying to install system dependencies for PyAudio..."
        apt-get update && apt-get install -y --no-install-recommends \
            portaudio19-dev \
            libportaudio2 \
            libportaudiocpp0 \
            python3-dev
        pip install --no-cache-dir pyaudio==0.2.14 || echo "⚠️ PyAudio installation still failed after installing system dependencies"
    fi
}

# Install OpenAI Realtime client
echo "Installing OpenAI Realtime client..."
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

# Debug information
echo "DEBUG: Starting Docker entrypoint script"
echo "DEBUG: Environment variables: DB_HOST=$DB_HOST, DB_PORT=$DB_PORT, DB_NAME=$DB_NAME"
echo "DEBUG: Current directory: $(pwd)"
echo "DEBUG: Directory contents: $(ls -la)"

# Expand environment variables in the SQLALCHEMY_DATABASE_URI
if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
	# Handle database connection correctly based on environment
	if [ "$RENDER" = "true" ]; then
		# We're running on Render, prioritize external database URLs
		if [ -n "$DATABASE_URL" ]; then
			# User-provided external database URL has highest priority
			export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
			echo "Using DATABASE_URL for external database connection"
		elif [ -n "$RENDER_DATABASE_URL" ]; then
			# Render-provided external database URL
			export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
			echo "Using RENDER_DATABASE_URL for external database connection"
		elif [ -n "$INTERNAL_DATABASE_URL" ]; then
			# Transform internal URL to external URL
			internal_url="$INTERNAL_DATABASE_URL"
			# Extract parts
			if [[ "$internal_url" == postgresql://* ]]; then
				user_part="${internal_url#postgresql://}"
				user_part="${user_part%%@*}"
				host_part="${internal_url#*@}"
				host="${host_part%%:*}"
				rest="${host_part#*:}"

				# Add .virginia-postgres.render.com to hostname if it's not already a render.com domain
				if [[ "$host" != *".render.com" ]]; then
					external_host="${host}.virginia-postgres.render.com"
					external_url="postgresql://${user_part}@${external_host}:${rest}"
					export SQLALCHEMY_DATABASE_URI="$external_url"
					echo "Transformed internal URL to external URL for database connection"
				else
					# Already has render.com domain
					export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
					echo "Using INTERNAL_DATABASE_URL for database connection"
				fi
			else
				# Not in expected format, use as-is
				export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
				echo "Using INTERNAL_DATABASE_URL for database connection (unknown format)"
			fi
		else
			# Fallback to component-based construction
			export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}.virginia-postgres.render.com:${DB_PORT}/${DB_NAME}"
			echo "WARNING: Constructed external database URL from components - may not be correct"
		fi
	else
		# Normal case for non-Render environments - construct the URI from parts
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

# Fix logger initialization issues
if [ -f "/app/fix_logger.py" ]; then
	echo "Fixing logger initialization issues..."
	python /app/fix_logger.py
elif [ -f "fix_logger.py" ]; then
	echo "Fixing logger initialization issues..."
	python fix_logger.py
fi

# Initialize database if needed
echo "Creating database tables if they don't exist..."
python -c "
import os
import asyncio
print('DEBUG: Python script starting')
print('DEBUG: SQLALCHEMY_DATABASE_URI:', os.environ.get('DATABASE_URL', 'Not set'))

# Import the async database initialization
try:
    from app.db_async import init_db
    print('DEBUG: Imported async database initialization')
    
    # Create an async function and run it
    async def init_database():
        print('DEBUG: Initializing database')
        await init_db()
        print('DEBUG: Database initialized successfully')
    
    # Run the async function
    asyncio.run(init_database())
except ImportError as e:
    print(f'ERROR: Failed to import async database initialization: {e}')
except Exception as e:
    print(f'ERROR: Failed to initialize database: {e}')
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
	echo "DEBUG: Launch command: gunicorn --worker-class=uvicorn.workers.UvicornWorker --workers=4 --worker-connections=1000 --bind=\"0.0.0.0:$PORT\" --log-level=debug \"wsgi:app\""

	# Check if app directory exists with the factory
	if [ -f "app/__init__.py" ]; then
		echo "DEBUG: Found app/__init__.py with create_app() factory function"
	else
		echo "ERROR: app/__init__.py not found in current directory"
		echo "DEBUG: Files in current directory:"
		ls -la
	fi

	# Check database connection before starting server
	echo "Testing database connection..."
	echo "SQLALCHEMY_DATABASE_URI: ${SQLALCHEMY_DATABASE_URI:0:25}..." # Show just the start, not credentials

	# Handle database URL with priority for external URLs
	if [ -n "$DATABASE_URL" ]; then
		echo "DATABASE_URL is set, using external URL directly"
		export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
	elif [ -n "$RENDER_DATABASE_URL" ]; then
		echo "RENDER_DATABASE_URL is set, using external URL directly"
		export SQLALCHEMY_DATABASE_URI="$RENDER_DATABASE_URL"
	elif [ -n "$INTERNAL_DATABASE_URL" ] && [ "$RENDER" = "true" ]; then
		echo "Only INTERNAL_DATABASE_URL is available, transforming to external URL"
		# Extract hostname from internal URL and add .virginia-postgres.render.com
		internal_url="$INTERNAL_DATABASE_URL"
		if [[ "$internal_url" == postgresql://* ]] && [[ "$internal_url" == *"@"* ]]; then
			user_part="${internal_url#postgresql://}"
			user_part="${user_part%%@*}"
			host_part="${internal_url#*@}"
			host="${host_part%%:*}"
			rest="${host_part#*:}"

			# Transform hostname if it's not already a render.com domain
			if [[ "$host" != *".render.com" ]]; then
				external_host="${host}.virginia-postgres.render.com"
				external_url="postgresql://${user_part}@${external_host}:${rest}"
				export SQLALCHEMY_DATABASE_URI="$external_url"
				echo "Using transformed external URL: ${external_url}"
			else
				export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
			fi
		else
			export SQLALCHEMY_DATABASE_URI="$INTERNAL_DATABASE_URL"
		fi
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
		cat >/tmp/gunicorn_env_wrapper.py <<'EOF'
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

		if [ -f "main.py" ]; then
			echo "DEBUG: Using main.py entry point for FastAPI"
			exec uvicorn main:app --workers=4 --host="0.0.0.0" --port="$PORT" \
				--log-level=debug
		else
			echo "DEBUG: Using main.py entry point for FastAPI"
			exec uvicorn main:app --workers=4 --host="0.0.0.0" --port="$PORT" \
				--log-level=debug
		fi
	else
		# Use uvicorn for FastAPI
		if [ -f "main.py" ]; then
			echo "DEBUG: Using main.py entry point for FastAPI"
			
			echo "Starting with Uvicorn for FastAPI"
			exec uvicorn main:app --workers=4 --host="0.0.0.0" --port="$PORT" \
    --log-level=info
		else
			echo "DEBUG: Using main.py entry point for FastAPI"
			exec uvicorn main:app --workers=4 --host="0.0.0.0" --port="$PORT" \
				--log-level=info
		fi
	fi
fi
