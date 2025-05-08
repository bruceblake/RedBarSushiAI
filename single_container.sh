#!/bin/bash
# Script to set up a single container with environment variables from .env.development

set -e  # Exit on any error

echo "===== Setting up RedBarSushiAI in a single container ====="

# Step 1: Get environment variables from .env.development
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Error: $ENV_FILE not found"
  exit 1
fi

echo "✅ Using environment file: $ENV_FILE"

# Extract key environment variables
echo "Extracting environment variables..."
OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
FLASK_ENV=$(grep "^FLASK_ENV=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
LOG_LEVEL=$(grep "^LOG_LEVEL=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
TWILIO_ACCOUNT_SID=$(grep "^TWILIO_ACCOUNT_SID=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
TWILIO_AUTH_TOKEN=$(grep "^TWILIO_AUTH_TOKEN=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
TWILIO_PHONE_NUMBER=$(grep "^TWILIO_PHONE_NUMBER=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌ Error: OPENAI_API_KEY not found in $ENV_FILE"
  exit 1
fi

echo "✅ Environment variables extracted successfully"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."
echo "FLASK_ENV: $FLASK_ENV"
echo "LOG_LEVEL: $LOG_LEVEL"

# Step 2: Clean up any existing containers
echo "Cleaning up existing containers..."
docker rm -f redbarsushi-app redis postgres 2>/dev/null || true

# Step 3: Create a network for the containers
echo "Creating Docker network..."
docker network create redbarsushi-network 2>/dev/null || true

# Step 4: Start Redis
echo "Starting Redis container..."
docker run -d --name redis \
  --network redbarsushi-network \
  -p 6379:6379 \
  redis:6

# Step 5: Start PostgreSQL
echo "Starting PostgreSQL container..."
docker run -d --name postgres \
  --network redbarsushi-network \
  -p 5433:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=redbarsushi \
  -v "$(pwd)/db/init:/docker-entrypoint-initdb.d" \
  postgres:14

# Step 6: Wait for PostgreSQL to initialize
echo "Waiting for PostgreSQL to initialize..."
sleep 5

# Step 7: Start the app container with all environment variables
echo "Starting RedBarSushiAI app container..."
docker run -d --name redbarsushi-app \
  --network redbarsushi-network \
  -p 8080:8080 \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e FLASK_ENV="$FLASK_ENV" \
  -e LOG_LEVEL="$LOG_LEVEL" \
  -e TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
  -e TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
  -e TWILIO_PHONE_NUMBER="$TWILIO_PHONE_NUMBER" \
  -e VOICE_HANDLER=realtime \
  -e FORCE_HEADLESS=true \
  -e IS_STAGING=true \
  -v "$(pwd)/app:/app/app" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/init_database.py:/app/init_database.py" \
  -v "$(pwd)/menu_data.json:/app/menu_data.json" \
  --restart unless-stopped \
  redbarsushiai-app

echo "✅ RedBarSushiAI app container started"

# Step 8: Verify the environment variables
echo "Verifying environment variables in the container..."
sleep 5  # Wait for the container to start
docker exec redbarsushi-app env | grep -E "OPENAI_API_KEY|FLASK_ENV|LOG_LEVEL|VOICE_HANDLER"

echo "===== Setup completed ====="
echo "RedBarSushiAI is now running at http://localhost:8080"
echo "PostgreSQL is available at localhost:5433"
echo "Redis is available at localhost:6379"
echo ""
echo "You can check logs with: docker logs -f redbarsushi-app"