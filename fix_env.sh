#!/bin/bash
# Quick fix for environment variables in Docker

set -e  # Exit on any error

echo "===== Fixing Environment Variables ====="

# Set the path to the docker-compose.yml file
COMPOSE_FILE="./docker/compose/docker-compose.yml"

# Check if the docker-compose.yml file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi

# Check if the environment file exists
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    exit 1
fi

echo "✅ Found environment file: $ENV_FILE"

# Extract OPENAI_API_KEY from the environment file
OPENAI_API_KEY=$(grep "OPENAI_API_KEY" "$ENV_FILE" | cut -d= -f2)
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: Could not extract OPENAI_API_KEY from $ENV_FILE"
    exit 1
fi

echo "✅ Found OPENAI_API_KEY in $ENV_FILE"
echo "Key starts with: ${OPENAI_API_KEY:0:10}..."

# Create a docker-compose override file to explicitly pass the environment variables
OVERRIDE_FILE="./docker/compose/docker-compose.override.yml"
echo "Creating $OVERRIDE_FILE with environment variables..."

cat > "$OVERRIDE_FILE" << EOF
services:
  app:
    environment:
      - OPENAI_API_KEY=$OPENAI_API_KEY
      - FLASK_ENV=development
      - FLASK_DEBUG=1
      - LOG_LEVEL=DEBUG
      - VOICE_HANDLER=realtime
      - FORCE_HEADLESS=true
      - IS_STAGING=true
    volumes:
      - ../../logs:/app/logs
      - ../../app:/app/app
      - ../../init_database.py:/app/init_database.py
      - ../../menu_data.json:/app/menu_data.json
EOF

echo "✅ Created $OVERRIDE_FILE"

# Apply the changes to the running container
echo "Applying environment variables to the running container..."
docker-compose -f "$COMPOSE_FILE" exec app bash -c "export OPENAI_API_KEY='$OPENAI_API_KEY'"
docker-compose -f "$COMPOSE_FILE" exec app bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."'

echo "✅ Environment variables applied"
echo "✅ Restarting containers to apply changes..."

# Restart the containers to apply the changes
docker-compose -f "$COMPOSE_FILE" down
docker-compose -f "$COMPOSE_FILE" up -d

echo "✅ Containers restarted"
echo "✅ Fix completed. Check the logs for any errors:"
echo "docker-compose -f $COMPOSE_FILE logs -f app"