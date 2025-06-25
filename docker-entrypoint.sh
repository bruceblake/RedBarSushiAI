#!/bin/bash
set -e

# =============================================================================
# Consolidated Docker Entrypoint Script for RedBarSushiAI
# =============================================================================
# This script provides a single, idempotent entrypoint for running either the
# FastAPI web server or Celery workers based on the APP_ROLE environment variable.
#
# Usage:
#   APP_ROLE=api    - Starts the FastAPI web server (default)
#   APP_ROLE=worker - Starts a Celery worker
#   APP_ROLE=beat   - Starts the Celery beat scheduler
# =============================================================================

# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------

# Set Python environment variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export PYTHONPATH=/app:$PYTHONPATH

# Set default PORT if not provided
: "${PORT:=8080}"

# Set default APP_ROLE if not provided
: "${APP_ROLE:=api}"

# Set default database pool configuration
: "${DB_POOL_SIZE:=10}"
: "${DB_MAX_OVERFLOW:=20}"
: "${DB_POOL_RECYCLE:=1800}"
: "${DB_POOL_TIMEOUT:=30}"

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------

# Configure database URL based on environment
if [ -n "$DATABASE_URL" ]; then
    export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
    echo "✅ Using DATABASE_URL for database connection"
elif [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
    export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "✅ Constructed database URL from components"
else
    echo "⚠️  WARNING: No database configuration found. Using default localhost connection."
    export SQLALCHEMY_DATABASE_URI="postgresql://redbarsushi:redbarsushi@localhost:5432/redbarsushi"
fi

# Configure Redis/Celery URLs
if [ -z "$REDIS_URL" ]; then
    echo "⚠️  WARNING: REDIS_URL not set. Using default localhost connection."
    export REDIS_URL="redis://localhost:6380/0"
fi
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-$REDIS_URL}"

# -----------------------------------------------------------------------------
# Database Initialization (API role only)
# -----------------------------------------------------------------------------

if [ "$APP_ROLE" = "api" ]; then
    echo "🔧 Initializing database..."
    python -c "
import asyncio
import sys
from app.db_async import init_db

async def initialize_database():
    try:
        await init_db()
        print('✅ Database initialized successfully')
    except Exception as e:
        print(f'❌ Database initialization failed: {e}')
        sys.exit(1)

asyncio.run(initialize_database())
" || {
        echo "❌ Failed to initialize database. Exiting."
        exit 1
    }
fi

# -----------------------------------------------------------------------------
# Application Startup
# -----------------------------------------------------------------------------

case "$APP_ROLE" in
    api)
        echo "🚀 Starting FastAPI web server on port $PORT"
        exec uvicorn app.main:app \
            --host="0.0.0.0" \
            --port="$PORT" \
            --log-level="${LOG_LEVEL:-info}" \
            ${RELOAD:+--reload}
        ;;
    
    worker)
        echo "🔧 Starting Celery worker"
        exec celery -A app.celery_app:celery_app worker \
            --loglevel="${LOG_LEVEL:-INFO}" \
            --concurrency="${CELERY_CONCURRENCY:-2}" \
            --max-memory-per-child="${CELERY_MAX_MEMORY:-200000}" \
            --pool="${CELERY_POOL:-prefork}"
        ;;
    
    beat)
        echo "⏰ Starting Celery beat scheduler"
        exec celery -A app.celery_app:celery_app beat \
            --loglevel="${LOG_LEVEL:-INFO}"
        ;;
    
    *)
        echo "❌ Unknown APP_ROLE: $APP_ROLE"
        echo "   Valid roles: api, worker, beat"
        exit 1
        ;;
esac