#!/bin/bash
# Script to restart Docker containers for RedBarSushiAI development environment

# Create directory structure
mkdir -p docker/images
mkdir -p logs
mkdir -p db/init

# Copy the fix script to docker directory if it doesn't exist
if [ ! -f docker/main_simplified.py ]; then
    cp -f docker/main_simplified.py docker/ 2>/dev/null || echo "Note: main_simplified.py not found, but that's ok"
fi

set -e  # Exit on any error

echo "===== Restarting RedBarSushiAI Development Docker Environment ====="

# Step 1: Define the docker-compose file and environment file
COMPOSE_FILE="docker-compose.development.yml"
ENV_FILE=".env.development"

# Check if files exist
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: $COMPOSE_FILE not found"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    exit 1
fi

echo "✅ Using compose file: $COMPOSE_FILE and environment file: $ENV_FILE"

# Step 2: Stop and remove all existing containers
echo "Stopping and removing all existing containers..."
docker-compose -f $COMPOSE_FILE down --remove-orphans
echo "✅ All containers stopped and removed"

# Step 3: Remove any existing development containers that might not be managed by docker-compose
echo "Removing any stray development containers..."
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Stray containers removed"

# Step 4: Clean up volumes if requested
if [ "$1" == "--clean" ]; then
    echo "Cleaning volumes as requested..."
    docker volume rm postgres-dev-data redis-dev-data 2>/dev/null || true
    echo "✅ Volumes cleaned"
fi

# Step 5: Start containers with docker-compose
echo "Starting development containers with docker-compose..."
docker-compose -f $COMPOSE_FILE up -d
echo "✅ Development containers started"

# Step 6: Wait for containers to be healthy
echo "Waiting for containers to be healthy..."
attempts=0
max_attempts=30
all_healthy=false

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-app-dev" | grep -q "(healthy)"; then
        all_healthy=true
        break
    fi
    
    echo "⏳ Waiting for containers to be healthy... ($attempts/$max_attempts)"
    sleep 2
done

if [ "$all_healthy" = true ]; then
    echo "✅ All containers are healthy!"
else
    echo "⚠️ Containers may not be fully healthy yet. Check with 'docker ps'"
fi

# Step 7: Display container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Development Environment ====="
echo "• API: http://localhost:8080"
echo "• WebSocket Test: ws://localhost:8080/ws-test/test"
echo "• Health Check: http://localhost:8080/healthcheck"
echo

echo "You can manage the environment with these commands:"
echo "• View logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "• Restart: ./restart_docker_dev.sh"
echo "• Stop: docker-compose -f $COMPOSE_FILE down"
echo "• Clean restart: ./restart_docker_dev.sh --clean"
echo
echo "===== Development Environment Ready ====="