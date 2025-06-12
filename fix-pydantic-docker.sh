#!/bin/bash
# Script to fix Pydantic import issues in Docker

echo "🔧 Fixing Pydantic import issues..."

# 1. Stop and remove containers
echo "Stopping containers..."
docker-compose -f docker-compose.dev.yml down

# 2. Remove the old app image
echo "Removing old app image..."
docker rmi redbarsushiai-app:latest 2>/dev/null || true

# 3. Rebuild with fixed requirements
echo "Rebuilding app with fixed requirements..."
docker-compose -f docker-compose.dev.yml build --no-cache app

# 4. Start services
echo "Starting services..."
docker-compose -f docker-compose.dev.yml up -d

# 5. Wait for services
echo "Waiting for services to start..."
sleep 10

# 6. Check if app is running
echo "Checking app status..."
docker-compose -f docker-compose.dev.yml ps app

# 7. Check logs
echo -e "\nApp logs:"
docker-compose -f docker-compose.dev.yml logs --tail=30 app

# 8. Test health endpoint
echo -e "\nTesting health endpoint..."
curl -s http://localhost:8000/health | python -m json.tool || echo "App not ready yet"

echo -e "\n✅ Done! Check the logs above for any remaining issues."