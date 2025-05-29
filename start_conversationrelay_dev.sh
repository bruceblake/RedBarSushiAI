#!/bin/bash
# Start script for ConversationRelay development with FSM agents

echo "🚀 Starting RedBarSushiAI with ConversationRelay..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please update .env with your API keys${NC}"
    exit 1
fi

# Check for required environment variables
source .env
required_vars=("OPENAI_API_KEY" "TWILIO_ACCOUNT_SID" "TWILIO_AUTH_TOKEN")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=($var)
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo -e "${RED}❌ Missing required environment variables:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo -e "${YELLOW}Please update your .env file${NC}"
    exit 1
fi

# Check if VOICE_HANDLER is set to conversation_relay
if [ "$VOICE_HANDLER" != "conversation_relay" ]; then
    echo -e "${YELLOW}⚠️  VOICE_HANDLER is not set to 'conversation_relay'${NC}"
    echo "Setting VOICE_HANDLER=conversation_relay in .env..."
    
    # Update or add VOICE_HANDLER in .env
    if grep -q "^VOICE_HANDLER=" .env; then
        sed -i 's/^VOICE_HANDLER=.*/VOICE_HANDLER=conversation_relay/' .env
    else
        echo "VOICE_HANDLER=conversation_relay" >> .env
    fi
    
    # Reload the variable
    export VOICE_HANDLER=conversation_relay
fi

echo -e "${GREEN}✓ Environment variables configured${NC}"

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down

# Clean up old volumes if requested
if [ "$1" == "--clean" ]; then
    echo "Cleaning up Docker volumes..."
    docker-compose down -v
    docker volume rm redbarsushi_postgres-data redbarsushi_redis-data 2>/dev/null || true
fi

# Build and start containers
echo "Building and starting Docker containers..."
docker-compose up -d --build

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check container health
echo -e "\n${GREEN}Container Status:${NC}"
docker-compose ps

# Initialize database if needed
echo -e "\n${GREEN}Initializing database...${NC}"
docker-compose exec -T app python -c "
import asyncio
from app.db_async import init_database
asyncio.run(init_database())
print('✓ Database initialized')
"

# Seed menu data if empty
echo -e "\n${GREEN}Checking menu data...${NC}"
docker-compose exec -T app python -c "
import asyncio
from app.db_async import get_db
from sqlalchemy import select
from app.models.menu_async import MenuItem

async def check_menu():
    async for db in get_db():
        result = await db.execute(select(MenuItem).limit(1))
        if not result.scalar():
            print('Menu is empty, seeding data...')
            import seed_menu_db
            await seed_menu_db.main()
        else:
            print('✓ Menu data exists')
        break

asyncio.run(check_menu())
"

# Run the test script
echo -e "\n${GREEN}Running ConversationRelay setup tests...${NC}"
docker-compose exec -T app python test_conversationrelay_setup.py

# Show logs
echo -e "\n${GREEN}Showing application logs (Ctrl+C to stop)...${NC}"
echo "=================================="
echo "To test ConversationRelay:"
echo "1. In a new terminal: ngrok http 8000"
echo "2. Update Twilio webhook with ngrok URL"
echo "3. Call your Twilio number"
echo "=================================="
echo ""

# Follow logs
docker-compose logs -f app