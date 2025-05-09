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
    print('All critical imports successful')
except ImportError as e:
    print(f'Error importing critical module: {e}')
    sys.exit(1)
"

# Try app initialization
log "Testing app initialization..."
python -c "
import sys
try:
    import os
    sys.path.insert(0, os.getcwd())
    
    from main import app
    print('FastAPI app initialization successful')
    
    # Check for FastAPI app instance
    if hasattr(app, 'router'):
        print(f'FastAPI app routes: {len(app.routes)}')
    else:
        print('WARNING: App instance may not be FastAPI')
    
except Exception as e:
    print(f'ERROR: App initialization failed: {e}')
    sys.exit(1)
"

# Start the FastAPI application
log "Starting FastAPI application with Uvicorn..."
PORT=${PORT:-8080}
WORKER_COUNT=${WORKER_COUNT:-4}

exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers $WORKER_COUNT --log-level info