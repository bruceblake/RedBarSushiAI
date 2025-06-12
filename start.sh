#!/bin/bash
# Simple start script for development

echo "🚀 Starting RedBarSushiAI..."

# Use the dev compose file
COMPOSE="docker-compose -f docker-compose.dev.yml"

# Start everything
$COMPOSE up -d

# Wait for app to be ready
echo "⏳ Waiting for app to start..."
for i in {1..20}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n✅ App is ready!"
        break
    fi
    echo -n "."
    sleep 2
done

echo -e "\n======================================"
echo "📱 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
echo "======================================"

# Show ngrok URL if available
python get_ngrok_url.py 2>/dev/null || echo "ℹ️  Add NGROK_AUTHTOKEN to .env for public URL"

echo -e "\nTo see logs: $COMPOSE logs -f app"
echo "To stop: $COMPOSE down"