#!/bin/bash
# Simple development script - just run ./dev.sh

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 Starting RedBarSushiAI Development Environment..."

# 1. Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ No .env file found!${NC}"
    echo "Creating one for you..."
    cat > .env << 'EOF'
# Required
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
TWILIO_ACCOUNT_SID=YOUR_SID_HERE
TWILIO_AUTH_TOKEN=YOUR_TOKEN_HERE
TWILIO_PHONE_NUMBER=+1234567890
NGROK_AUTHTOKEN=YOUR_NGROK_TOKEN_HERE

# Optional (defaults are fine)
CONVERSATION_RELAY_TTS_VOICE=rachel
LOG_LEVEL=INFO
EOF
    echo -e "${RED}Please edit .env and add your API keys!${NC}"
    exit 1
fi

# 2. Start everything
echo "Starting services..."
docker-compose -f docker-compose.dev.yml up -d

# 3. Wait for app to be ready
echo "Waiting for app to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ App is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# 4. Initialize database (only if needed)
if ! docker-compose -f docker-compose.dev.yml exec postgres psql -U postgres -d sushi_restaurant -c "SELECT 1 FROM menu_items LIMIT 1;" > /dev/null 2>&1; then
    echo "Initializing database..."
    docker-compose -f docker-compose.dev.yml exec app python init_db.py
    docker-compose -f docker-compose.dev.yml exec app python seed_menu_db.py
fi

# 5. Get ngrok URL
echo -e "\n${GREEN}========================================${NC}"
sleep 2
python get_ngrok_url.py 2>/dev/null || echo "Add NGROK_AUTHTOKEN to .env for public URL"

echo -e "\n${GREEN}✅ Everything is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo "📱 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
echo "🔍 Logs: docker-compose -f docker-compose.dev.yml logs -f app"
echo -e "${GREEN}========================================${NC}"