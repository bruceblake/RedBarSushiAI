#!/bin/bash
# Simple script to restart Docker environment

set -e

echo "===== Restarting RedBarSushiAI Docker Environment ====="

# Step 1: Stop and remove containers
echo "Step 1: Stopping and removing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Containers stopped and removed"

# Step 2: Remove volumes if --clean flag is provided
if [ "$1" == "--clean" ]; then
    echo "Step 2: Removing volumes for clean start..."
    docker volume rm postgres-data redis-data 2>/dev/null || true
    echo "✅ Volumes removed"
else
    echo "Step 2: Keeping existing volumes (use --clean to remove)"
fi

# Step 3: Start containers with docker-compose
echo "Step 3: Starting containers..."
docker compose -f docker-compose.simple.yml up -d --build
echo "✅ Containers started"

# Step 4: Wait for PostgreSQL to be healthy
echo "Step 4: Waiting for PostgreSQL to be healthy..."
attempts=0
max_attempts=30

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
        echo "✅ PostgreSQL is healthy"
        break
    fi
    
    echo "⏳ Waiting for PostgreSQL to be healthy... (${attempts}/${max_attempts})"
    sleep 2
done

# Step 5: Run database initialization script
echo "Step 5: Initializing database..."
docker exec redbarsushi-app-dev python /app/init_simple_db.py || echo "⚠️ Database initialization failed"

# Step 6: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Docker Environment Ready ====="
echo "The application should be available at: http://localhost:8080"
echo
echo "To view logs:"
echo "- App logs: docker logs redbarsushi-app-dev"
echo "- PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "- Redis logs: docker logs redbarsushi-redis-dev"
echo
echo "To restart with clean volumes: ./restart_docker_simple.sh --clean"
