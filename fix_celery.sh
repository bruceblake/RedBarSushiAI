#!/bin/bash
# Script to fix Celery configuration on Render

# Ensure Redis URL is properly formatted
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

# Set process type to celery
export PROCESS="celery"

# Start Celery worker with memory optimizations
echo "Starting Celery worker with memory optimizations..."
exec celery -A celery_app worker --loglevel=INFO --concurrency=2 --max-memory-per-child=50000
