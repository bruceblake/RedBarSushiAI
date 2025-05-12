#!/bin/bash
# Clean up Docker volumes related to RedBarSushi

echo "Removing Docker volumes for RedBarSushi..."
docker volume rm postgres-dev-data redis-dev-data 2>/dev/null || true
echo "✅ Volumes removed"
