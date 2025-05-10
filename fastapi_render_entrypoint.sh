#!/bin/bash
set -e

# This entrypoint script is specifically for FastAPI on Render

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

log "Starting RedBarSushiAI with FastAPI on Render..."

# Set environment variables
export RENDER=true
export FORCE_HEADLESS=true
export PYTHONPATH=/app:$PYTHONPATH
export FASTAPI_ENV=${FASTAPI_ENV:-staging}
export FLASK_ENV=${FLASK_ENV:-staging}

# Database checking/initialization
log "Testing database connection..."
python -c "
import sys
import os
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

async def test_db_async():
    try:
        # Try async database initialization if available
        try:
            from app.db_async import init_db, get_async_engine
            print('Using async database initialization')
            await init_db()
            print('Database initialized successfully')
            return True
        except ImportError:
            print('Async database module not available, using SQLAlchemy')
            # Use regular SQLAlchemy
            db_uri = os.environ.get('DATABASE_URL')
            if not db_uri:
                print('ERROR: DATABASE_URL not set')
                return False
                
            engine = create_engine(db_uri)
            with engine.connect() as conn:
                result = conn.execute(text('SELECT 1'))
                if result.scalar() == 1:
                    print('Database connection successful')
                    return True
                else:
                    print('Database query returned unexpected result')
                    return False
    except Exception as e:
        print(f'Database connection error: {e}')
        return False

# Run the async function
if asyncio.run(test_db_async()):
    print('Database check passed')
    sys.exit(0)
else:
    print('Database check failed')
    sys.exit(1)
"

# Installing the required dependencies from requirements-fastapi.txt
log "Installing FastAPI dependencies..."
if [ -f "requirements-fastapi.txt" ]; then
    pip install -r requirements-fastapi.txt
    log "Installed FastAPI dependencies from requirements-fastapi.txt"
else
    log "requirements-fastapi.txt not found, installing core dependencies manually"
    pip install pydantic==1.10.8 fastapi==0.115.11 uvicorn==0.34.0 websockets==13.1 websocket-client==1.7.0
fi

# Check python installation and dependencies
log "Checking critical dependencies..."
python -c "
import sys
try:
    import fastapi
    import uvicorn
    import sqlalchemy
    import psycopg2
    import redis
    import twilio
    
    # Check pydantic version
    import pydantic
    print(f'Pydantic version: {pydantic.__version__}')
    
    # No need to check for pydantic-settings - we're using pydantic v1
    
    print('All critical imports successful')
except ImportError as e:
    print(f'Error importing critical module: {e}')
    # Try to install missing dependencies
    print('Attempting to install missing dependencies...')
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pydantic==1.10.8'])
    print('Dependencies installed. Continuing...')
"

# Try app initialization
log "Testing app initialization..."
python -c "
import sys
import traceback

# Confirm we're using pydantic v1 which has BaseSettings
try:
    import pydantic
    print(f'Using pydantic version: {pydantic.__version__}')
    if not hasattr(pydantic, 'BaseSettings'):
        print('ERROR: pydantic version does not have BaseSettings!')
        # Force reinstall the right version
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--force-reinstall', 'pydantic==1.10.8'])
        # Reimport
        import importlib
        importlib.reload(pydantic)
        print(f'Reinstalled pydantic version: {pydantic.__version__}')
        
        if not hasattr(pydantic, 'BaseSettings'):
            print('ERROR: Still missing BaseSettings after reinstall')
            sys.exit(1)
except Exception as e:
    print(f'Warning: pydantic check failed: {e}')

try:
    import os
    sys.path.insert(0, os.getcwd())
    
    print('Attempting to import main app...')
    try:
        from main import app
        print('FastAPI app initialization successful')
        
        # Check for FastAPI app instance
        if hasattr(app, 'router'):
            print(f'FastAPI app routes: {len(app.routes)}')
        else:
            print('WARNING: App instance may not be FastAPI')
    except Exception as e:
        print(f'Error importing app: {e}')
        if 'BaseSettings' in str(e):
            print('Detected BaseSettings import error, trying to fix...')
            # Force install the right versions
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--force-reinstall', 'pydantic==1.10.8'])
            print('Fixed pydantic to version 1.10.8, retrying import...')
            
            # Clear module cache and retry
            import importlib
            if 'pydantic' in sys.modules:
                del sys.modules['pydantic']
            if 'main' in sys.modules:
                del sys.modules['main']
            if 'app' in sys.modules:
                del sys.modules['app']
            if 'app.config' in sys.modules:
                del sys.modules['app.config']
                
            # Try import again
            try:
                from main import app
                print('FastAPI app initialization successful after pydantic fix')
            except Exception as retry_e:
                print(f'Error after pydantic fix: {retry_e}')
                raise
        else:
            # Not a BaseSettings issue
            raise
except Exception as e:
    print(f'ERROR: App initialization failed: {e}')
    traceback.print_exc()
    sys.exit(1)
"

# Start the FastAPI application
log "Starting FastAPI application with Uvicorn..."
PORT=${PORT:-8080}
WORKER_COUNT=${WORKER_COUNT:-4}

exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers $WORKER_COUNT --log-level info