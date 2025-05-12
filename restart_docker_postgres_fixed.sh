#!/bin/bash
# Script to restart Docker with fixed PostgreSQL configuration

set -e

echo "===== Starting RedBarSushiAI with Fixed PostgreSQL Configuration ====="

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

# Step 3: Starting the containers with fixed configuration
echo "Step 3: Starting the containers with fixed PostgreSQL configuration..."
docker compose -f docker-compose.postgres-fixed.yml up -d --build --force-recreate
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

# Step 5: Check PostgreSQL status
echo "Step 5: Checking PostgreSQL status..."
if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
    echo "✅ PostgreSQL is healthy"
    
    # Test PostgreSQL access with docker exec
    echo "Testing PostgreSQL access directly..."
    docker exec -it redbarsushi-postgres-dev psql -U postgres -c "SELECT 1 as test" || echo "⚠️ Direct PostgreSQL access failed"
    
    # Check application container logs
    echo "App container logs (last 10 lines):"
    docker logs redbarsushi-app-dev --tail 10
    
    # Wait for application to try connecting
    echo "Waiting for application to attempt database connection..."
    sleep 5
    
    # Show database-related logs
    echo "Database-related logs from app container:"
    docker logs redbarsushi-app-dev | grep -i "database\|db\|postgres\|sql" | tail -20
else
    echo "⚠️ PostgreSQL container not healthy after waiting"
    echo "PostgreSQL container logs:"
    docker logs redbarsushi-postgres-dev --tail 20
fi

# Step 6: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Next Steps ====="
echo "1. Check container logs for detailed information:"
echo "   - View PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "   - View application logs: docker logs redbarsushi-app-dev"
echo "2. If issues persist, try restarting with clean volumes:"
echo "   ./restart_docker_postgres_fixed.sh --clean-volumes"
echo "3. Access the application at: http://localhost:8080"
echo
echo "===== Setup Complete ====="
