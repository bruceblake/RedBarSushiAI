#!/bin/bash
# Script to ensure that the application uses uvicorn.workers.UvicornWorker in Docker

echo "Ensuring uvicorn worker is used throughout the application..."

# Fix docker-compose.override.yml if it exists
if [ -f "docker-compose.override.yml" ]; then
    echo "Updating docker-compose.override.yml..."
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' docker-compose.override.yml
    echo "✓ Updated docker-compose.override.yml"
fi

# Fix docker/compose/docker-compose.override.yml if it exists
if [ -f "docker/compose/docker-compose.override.yml" ]; then
    echo "Updating docker/compose/docker-compose.override.yml..."
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' docker/compose/docker-compose.override.yml
    echo "✓ Updated docker/compose/docker-compose.override.yml"
fi

# Fix docker-entrypoint.sh
if [ -f "docker-entrypoint.sh" ]; then
    echo "Updating docker-entrypoint.sh..."
    # Replace all instances of gevent-based workers with uvicorn
    sed -i 's/--worker-class=gevent/--worker-class=uvicorn.workers.UvicornWorker/g' docker-entrypoint.sh
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' docker-entrypoint.sh
    echo "✓ Updated docker-entrypoint.sh"
fi

# Update start_docker.sh
if [ -f "start_docker.sh" ]; then
    echo "Updating start_docker.sh..."
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' start_docker.sh
    echo "✓ Updated start_docker.sh"
fi

# Install required packages
echo "Installing required Python packages..."
pip install --no-cache-dir uvicorn==0.34.0 websockets==13.1

echo "All updates completed. Please run ./restart_docker.sh to apply changes."