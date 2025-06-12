#!/bin/bash
# Quick fix for the running container

echo "🔧 Applying quick fix to running container..."

# Install pydantic-settings in the running container
echo "Installing pydantic-settings..."
docker-compose -f docker-compose.dev.yml exec app pip install pydantic-settings

# Restart the app
echo "Restarting app..."
docker-compose -f docker-compose.dev.yml restart app

# Wait a moment
sleep 5

# Check if it's working
echo "Checking if app is running..."
curl -s http://localhost:8000/health | python -m json.tool || echo "Still starting..."

# Show logs
echo -e "\n📋 App logs:"
docker-compose -f docker-compose.dev.yml logs --tail=30 app