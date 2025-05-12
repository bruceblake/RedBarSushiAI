#!/bin/bash
set -e

echo "=== Stopping and removing existing containers ==="
docker-compose -f docker-compose.fixed.yml down -v

echo "=== Clearing any persistent volumes ==="
docker volume rm $(docker volume ls -q | grep redbarsushi) || echo "No volumes to remove"

echo "=== Building and starting containers ==="
docker-compose -f docker-compose.fixed.yml up -d --build

echo "=== Waiting for database to be ready ==="
sleep 5

echo "=== Testing database connection ==="
docker exec redbarsushi-postgres pg_isready -U postgres || echo "Database not ready yet, waiting..."
sleep 5
docker exec redbarsushi-postgres pg_isready -U postgres

echo "=== Testing Redis connection ==="
docker exec redbarsushi-redis redis-cli ping

echo "=== Viewing logs from the app container ==="
docker logs redbarsushi-app

echo "=== Setup complete! ==="
echo "To view continued logs from the app container, run:"
echo "docker logs -f redbarsushi-app"