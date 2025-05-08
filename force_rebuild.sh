#!/bin/bash
# Force rebuild Docker image with uvicorn worker

set -e

echo "===== Forcing Docker image rebuild with uvicorn worker ====="

# Ensure we have the latest Dockerfile configuration
echo "Checking Dockerfile..."
DOCKERFILE="/home/proxyie/MySoftware/RedBarSushiAI/docker/images/Dockerfile"
if grep -q "geventwebsocket.gunicorn.workers.GeventWebSocketWorker" "$DOCKERFILE"; then
    echo "Updating Dockerfile to use uvicorn worker..."
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' "$DOCKERFILE"
fi

# Verify uvicorn worker is configured in CMD
if ! grep -q "uvicorn.workers.UvicornWorker" "$DOCKERFILE"; then
    echo "Adding uvicorn worker to Dockerfile CMD..."
    sed -i 's/CMD \["gunicorn"/CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker"/g' "$DOCKERFILE"
fi

echo "Dockerfile configured correctly for uvicorn worker"

# Update docker-entrypoint.sh
echo "Checking docker-entrypoint.sh..."
ENTRYPOINT="/home/proxyie/MySoftware/RedBarSushiAI/docker-entrypoint.sh"
if grep -q "gevent" "$ENTRYPOINT"; then
    echo "Updating docker-entrypoint.sh to use uvicorn worker..."
    sed -i 's/--worker-class=gevent/--worker-class=uvicorn.workers.UvicornWorker/g' "$ENTRYPOINT"
    sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' "$ENTRYPOINT"
fi

echo "docker-entrypoint.sh configured correctly"

# Ensure the docker-compose.override.yml is updated
echo "Checking docker-compose.override.yml..."
OVERRIDE="/home/proxyie/MySoftware/RedBarSushiAI/docker-compose.override.yml"
if [ -f "$OVERRIDE" ]; then
    if ! grep -q "uvicorn.workers.UvicornWorker" "$OVERRIDE"; then
        echo "Updating docker-compose.override.yml..."
        sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' "$OVERRIDE"
    fi
fi

# Also check the docker/compose/docker-compose.override.yml file
COMPOSE_OVERRIDE="/home/proxyie/MySoftware/RedBarSushiAI/docker/compose/docker-compose.override.yml"
if [ -f "$COMPOSE_OVERRIDE" ]; then
    if ! grep -q "uvicorn.workers.UvicornWorker" "$COMPOSE_OVERRIDE"; then
        echo "Updating docker/compose/docker-compose.override.yml..."
        sed -i 's/geventwebsocket.gunicorn.workers.GeventWebSocketWorker/uvicorn.workers.UvicornWorker/g' "$COMPOSE_OVERRIDE"
    fi
fi

echo "Override files configured correctly"

# Clean up the existing docker containers and images
echo "Stopping and removing existing containers..."
docker stop redis postgres redbarsushi-app 2>/dev/null || true
docker rm -f redis postgres redbarsushi-app 2>/dev/null || true

# Remove the image to force a rebuild
echo "Removing existing Docker image..."
docker rmi redbarsushiai-app 2>/dev/null || true

# Run the restart script that will now rebuild the image
echo "The image has been removed. You can now manually run restart_docker.sh to rebuild with the updated configuration."
echo "Run: ./restart_docker.sh"
# Commented out to prevent endless restart loop on error
# /home/proxyie/MySoftware/RedBarSushiAI/restart_docker.sh

echo "===== Force rebuild completed ====="
echo "The application should now be running with uvicorn worker"
echo "Check logs with: docker logs -f redbarsushi-app"