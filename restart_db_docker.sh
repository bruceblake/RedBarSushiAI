#!/bin/bash
# Comprehensive script to restart Docker environment with database fixes

set -e  # Exit on any error

echo "===== Restarting RedBarSushiAI Docker Environment with DB Fixes ====="

# Step 1: Clean up existing containers
echo "Step 1: Stopping and removing existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker network rm redbarsushi-dev-network 2>/dev/null || true
echo "✅ Containers and network cleaned up"

# Step 2: Clean up volumes (only if explicitly wanted)
if [ "$1" == "--clean-volumes" ]; then
    echo "Step 2: Removing volumes for fresh start..."
    docker volume rm postgres-dev-data redis-dev-data 2>/dev/null || true
    echo "✅ Volumes removed for fresh start"
else
    echo "Step 2: Keeping existing volumes (use --clean-volumes to remove)"
fi

# Step 3: Start Docker services with fixed configuration
echo "Step 3: Starting Docker services with fixed configuration..."
# Using --force-recreate to ensure we get fresh containers
docker compose -f docker-compose.fixed.yml up -d --build --force-recreate
echo "✅ Docker services started with fixed configuration"

# Step 4: Wait for services to be ready
echo "Step 4: Waiting for services to be ready..."
attempts=0
max_attempts=30
all_healthy=false

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    # Check if postgres is healthy
    if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
        echo "✅ PostgreSQL is healthy"
        all_healthy=true
        break
    fi
    
    echo "⏳ Waiting for PostgreSQL to be healthy... ($attempts/$max_attempts)"
    sleep 2
done

if [ "$all_healthy" = true ]; then
    echo "✅ PostgreSQL is healthy and ready"
    
    # Give the app container a moment to start trying to connect
    echo "Waiting for app container to connect to database..."
    sleep 10
    
    # Show logs from the app container related to database connection
    echo "Database connection logs from app container:"
    docker logs redbarsushi-app-dev --tail 50 | grep -i "database\|db\|postgres\|sql" || true
else
    echo "⚠️ PostgreSQL may not be fully healthy yet. Check with 'docker ps'"
fi

# Step 5: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi || true

echo
echo "===== Database Connection Troubleshooting ====="
echo "If database connection issues persist, try these commands:"
echo "• View app logs: docker logs redbarsushi-app-dev"
echo "• View PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "• Test connection from app: docker exec -it redbarsushi-app-dev python check_db_enhanced.py"
echo "• Manual PostgreSQL check: docker exec -it redbarsushi-postgres-dev psql -U postgres -c 'SELECT 1'"
echo "• Restart with clean volumes: ./restart_db_docker.sh --clean-volumes"
echo

# Step 6: Provide next steps
echo "===== Next Steps ====="
echo "1. Check the logs for any database-related errors"
echo "2. Verify that the app container can connect to PostgreSQL"
echo "3. If issues persist, try restarting with --clean-volumes"
echo
echo "===== Setup Complete ====="
