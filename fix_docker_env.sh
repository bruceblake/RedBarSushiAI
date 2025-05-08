#!/bin/bash
# Script to fix Docker environment variables by directly injecting them from .env.development

set -e

# Step 1: Extract environment variables from .env.development
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    exit 1
fi

echo "✅ Found environment file: $ENV_FILE"

# Extract variables from .env.development
OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2)
FLASK_ENV=$(grep "^FLASK_ENV=" "$ENV_FILE" | cut -d= -f2)
LOG_LEVEL=$(grep "^LOG_LEVEL=" "$ENV_FILE" | cut -d= -f2)
TWILIO_ACCOUNT_SID=$(grep "^TWILIO_ACCOUNT_SID=" "$ENV_FILE" | cut -d= -f2)
TWILIO_AUTH_TOKEN=$(grep "^TWILIO_AUTH_TOKEN=" "$ENV_FILE" | cut -d= -f2)
TWILIO_PHONE_NUMBER=$(grep "^TWILIO_PHONE_NUMBER=" "$ENV_FILE" | cut -d= -f2)

# Check if we successfully extracted the OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: Could not extract OPENAI_API_KEY from $ENV_FILE"
    exit 1
fi

echo "✅ Successfully extracted environment variables from $ENV_FILE"

# Step 2: Apply these directly to the running container
echo "Injecting environment variables into the running container..."

# Stop the app container first
docker stop compose-app-1 || true

# Start the container with explicit environment variables
echo "Starting container with explicit environment variables..."
docker run -d --name compose-app-1 \
  --network=compose_redbarsushi-network \
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
  --volume "$(pwd)/app:/app/app" \
  --volume "$(pwd)/logs:/app/logs" \
  --volume "$(pwd)/init_database.py:/app/init_database.py" \
  --volume "$(pwd)/menu_data.json:/app/menu_data.json" \
  --restart unless-stopped \
  redbarsushiai-app

echo "✅ Container restarted with environment variables"

# Verify the environment variables are now set
echo "Verifying environment variables..."
docker exec compose-app-1 bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."'
docker exec compose-app-1 bash -c 'echo "FLASK_ENV: $FLASK_ENV"'
docker exec compose-app-1 bash -c 'echo "LOG_LEVEL: $LOG_LEVEL"'
docker exec compose-app-1 bash -c 'echo "VOICE_HANDLER: $VOICE_HANDLER"'

echo "✅ Fix completed successfully"