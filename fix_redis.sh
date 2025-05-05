#!/bin/bash
set -e

# This script fixes Redis connection issues in Docker environments
echo "Fixing Redis connection issues..."

# Check if Redis service is running
if command -v docker &> /dev/null; then
    echo "Checking for Redis container..."
    if ! docker ps | grep -q redis; then
        echo "No Redis container found, starting one..."
        docker run --name redis-server -p 6379:6379 -d redis
        echo "Redis container started."
    else
        echo "Redis container is already running."
    fi
else
    echo "Docker not found, installing Redis locally..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y redis-server
        sudo systemctl enable redis-server
        sudo systemctl start redis-server
        echo "Redis server installed and started."
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
        sudo systemctl enable redis
        sudo systemctl start redis
        echo "Redis server installed and started."
    else
        echo "Unable to install Redis automatically. Please install Redis manually."
        exit 1
    fi
fi

# Configure the application to use the correct Redis URL
echo "Setting Redis environment variables..."

# For Docker environments
if [ -n "$DOCKER" ] || [ -n "$RENDER_SERVICE_ID" ]; then
    echo "Setting Redis URL for Docker/Render environment..."
    
    # Determine Redis host
    REDIS_HOST="redis"
    if [ -n "$RENDER_SERVICE_ID" ]; then
        # On Render, we need to use the Redis service address
        REDIS_HOST="red-ceqpb6rf1sgc739ut8e0"
    elif [ -n "$REDIS_HOST" ]; then
        # Use the provided REDIS_HOST
        echo "Using provided REDIS_HOST: $REDIS_HOST"
    else
        # Default Docker service name
        REDIS_HOST="redis"
    fi
    
    # Set Redis environment variables
    export REDIS_URL="redis://${REDIS_HOST}:6379/0"
    export CELERY_BROKER_URL="redis://${REDIS_HOST}:6379/1"
    export CELERY_RESULT_BACKEND="redis://${REDIS_HOST}:6379/1"
    
    echo "Redis URL set to: $REDIS_URL"
    echo "Celery broker URL set to: $CELERY_BROKER_URL"
    echo "Celery result backend set to: $CELERY_RESULT_BACKEND"
else
    # For local development
    echo "Setting Redis URL for local environment..."
    export REDIS_URL="redis://localhost:6379/0"
    export CELERY_BROKER_URL="redis://localhost:6379/1"
    export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
    
    echo "Redis URL set to: $REDIS_URL"
    echo "Celery broker URL set to: $CELERY_BROKER_URL"
    echo "Celery result backend set to: $CELERY_RESULT_BACKEND"
fi

# Update .env file if it exists
if [ -f ".env" ]; then
    echo "Updating .env file..."
    # Remove existing Redis-related entries
    sed -i '/REDIS_URL=/d' .env
    sed -i '/CELERY_BROKER_URL=/d' .env
    sed -i '/CELERY_RESULT_BACKEND=/d' .env
    
    # Add new entries
    echo "REDIS_URL=$REDIS_URL" >> .env
    echo "CELERY_BROKER_URL=$CELERY_BROKER_URL" >> .env
    echo "CELERY_RESULT_BACKEND=$CELERY_RESULT_BACKEND" >> .env
    echo ".env file updated."
fi

echo "Redis connection fix completed."