#!/bin/bash
# Complete script to restart and fix Docker environment for RedBarSushiAI

set -e  # Exit on any error

echo "===== Restarting RedBarSushiAI Docker Environment ====="

# Step 1: Set the path to the docker-compose.yml file
COMPOSE_FILE="./docker/compose/docker-compose.yml"

# Check if the docker-compose.yml file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi
echo "✅ Using docker-compose.yml from: $COMPOSE_FILE"

# Step 2: Force stop and remove all existing containers
echo "Stopping and removing all existing containers..."
docker stop redis postgres redbarsushi-app 2>/dev/null || true
docker rm -f redis postgres redbarsushi-app 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=redis" -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=postgres" -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=redbarsushi" -q) 2>/dev/null || true
echo "✅ All containers stopped and removed"

# Step 3: Remove networks
echo "Removing networks..."
docker network rm redbarsushi-network 2>/dev/null || true
echo "✅ Networks removed"

# Step 4: Verify environment file exists
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    exit 1
fi
echo "✅ Found environment file: $ENV_FILE"

# Step 5: Extract environment variables
echo "Extracting environment variables from $ENV_FILE..."

# More reliable way to extract variables
OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
FLASK_ENV=$(grep "^FLASK_ENV=" "$ENV_FILE" | cut -d= -f2-)
LOG_LEVEL=$(grep "^LOG_LEVEL=" "$ENV_FILE" | cut -d= -f2-)
TWILIO_ACCOUNT_SID=$(grep "^TWILIO_ACCOUNT_SID=" "$ENV_FILE" | cut -d= -f2-)
TWILIO_AUTH_TOKEN=$(grep "^TWILIO_AUTH_TOKEN=" "$ENV_FILE" | cut -d= -f2-)
TWILIO_PHONE_NUMBER=$(grep "^TWILIO_PHONE_NUMBER=" "$ENV_FILE" | cut -d= -f2-)
DELIVERECT_CHANNEL_NAME=$(grep "^DELIVERECT_CHANNEL_NAME=" "$ENV_FILE" | cut -d= -f2-)
DELIVERECT_API_KEY=$(grep "^DELIVERECT_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
DELIVERECT_BASE_URL=$(grep "^DELIVERECT_BASE_URL=" "$ENV_FILE" | cut -d= -f2-)
DATABASE_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" | cut -d= -f2-)
REDIS_URL=$(grep "^REDIS_URL=" "$ENV_FILE" | cut -d= -f2-)
POSTGRES_USER=$(grep "^POSTGRES_USER=" "$ENV_FILE" | cut -d= -f2-)
POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d= -f2-)
POSTGRES_DB=$(grep "^POSTGRES_DB=" "$ENV_FILE" | cut -d= -f2-)

# Verify API key is present
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not found in $ENV_FILE"
    exit 1
fi

echo "✅ Environment variables extracted"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."

# Step 6: Create a network for the containers
echo "Creating Docker network..."
docker network create redbarsushi-network || true

# Step 7: Start Redis
echo "Starting Redis container..."
docker run -d --name redis \
  --network redbarsushi-network \
  -p 6379:6379 \
  redis:6

# Step 8: Start PostgreSQL
echo "Starting PostgreSQL container..."
# Try to use a different port (5434) since 5433 seems to be already in use
docker run -d --name postgres \
  --network redbarsushi-network \
  -p 5434:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=redbarsushi \
  -v "$(pwd)/db/init:/docker-entrypoint-initdb.d" \
  postgres:14

# Step 9: Wait for PostgreSQL to initialize
echo "Waiting for PostgreSQL to initialize..."
sleep 5

# Verify PostgreSQL is running and properly initialized
echo "Verifying PostgreSQL connection..."
max_attempts=10
attempt=1
while [ $attempt -le $max_attempts ]; do
    if docker exec postgres pg_isready -U postgres; then
        echo "✅ PostgreSQL is ready"
        break
    else
        echo "⚠️ PostgreSQL not ready yet, waiting... (attempt $attempt/$max_attempts)"
        sleep 5
        attempt=$((attempt+1))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ PostgreSQL failed to initialize after multiple attempts"
    echo "Checking PostgreSQL logs for errors:"
    docker logs postgres
    exit 1
fi

# Step 10: Check if schema was created successfully
echo "Verifying database schema..."
if ! docker exec postgres psql -U postgres -d redbarsushi -c "\dt" 2>/dev/null | grep -q menu_items; then
    echo "⚠️ Database schema not found, initializing schema manually..."
    # Remove the trailing EOF line if it exists
    cat db/init/01_schema.sql | grep -v "^EOF" | docker exec -i postgres psql -U postgres -d redbarsushi
fi

# Step A: Check if the schema is already created
if ! docker exec postgres psql -U postgres -d redbarsushi -c "\dt" | grep -q menu_items; then
    echo "⚠️ Database schema still not initialized correctly. Trying alternative approach..."
    schema_sql=$(cat db/init/01_schema.sql)
    docker exec -i postgres psql -U postgres -d redbarsushi <<EOF
$schema_sql
EOF
    echo "Alternative schema initialization completed."
fi

# Step 11: Check if the image exists
if ! docker image inspect redbarsushiai-app >/dev/null 2>&1; then
    echo "⚠️ redbarsushiai-app image not found. Building it..."
    docker build -f docker/images/Dockerfile -t redbarsushiai-app .
fi

# Step 12: Start the app container with all environment variables
echo "Starting RedBarSushiAI app container..."
docker run -d --name redbarsushi-app \
  --network redbarsushi-network \
  -p 8080:8080 \
  -e "REDIS_URL=$REDIS_URL" \
  -e "DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi" \
  -e "POSTGRES_USER=$POSTGRES_USER" \
  -e "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" \
  -e "POSTGRES_DB=$POSTGRES_DB" \
  -e "OPENAI_API_KEY=$OPENAI_API_KEY" \
  -e "FASTAPI_ENV=${FLASK_ENV:-development}" \
  -e "FLASK_ENV=${FLASK_ENV:-development}" \
  -e "FLASK_DEBUG=1" \
  -e "LOG_LEVEL=$LOG_LEVEL" \
  -e "TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID" \
  -e "TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN" \
  -e "TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER" \
  -e "DELIVERECT_CHANNEL_NAME=$DELIVERECT_CHANNEL_NAME" \
  -e "DELIVERECT_API_KEY=$DELIVERECT_API_KEY" \
  -e "DELIVERECT_BASE_URL=$DELIVERECT_BASE_URL" \
  -e "VOICE_HANDLER=realtime" \
  -e "FORCE_HEADLESS=true" \
  -e "IS_STAGING=true" \
  -e "DB_USER=postgres" \
  -e "DB_PASSWORD=postgres" \
  -e "DB_HOST=postgres" \
  -e "DB_PORT=5432" \
  -e "DB_NAME=redbarsushi" \
  -v "$(pwd)/app:/app/app" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/init_database.py:/app/init_database.py" \
  -v "$(pwd)/menu_data.json:/app/menu_data.json" \
  -v "$(pwd)/websocket_test_client.py:/app/websocket_test_client.py" \
  --restart unless-stopped \
  redbarsushiai-app \
  "uvicorn" "main:app" "--host" "0.0.0.0" "--port" "8080" "--workers" "4"

echo "✅ RedBarSushiAI app container started"

# Step 13: Verify environment variables
echo "Verifying environment variables in the container..."
sleep 5  # Wait for the container to fully start
docker exec redbarsushi-app bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."'
docker exec redbarsushi-app bash -c 'echo "FASTAPI_ENV: $FASTAPI_ENV"'
docker exec redbarsushi-app bash -c 'echo "FLASK_ENV: $FLASK_ENV"'
docker exec redbarsushi-app bash -c 'echo "VOICE_HANDLER: $VOICE_HANDLER"'
docker exec redbarsushi-app bash -c 'echo "DATABASE_URL: $DATABASE_URL"'
docker exec redbarsushi-app bash -c 'echo "DB_USER: $DB_USER"'

# Test database connection from inside the container
echo "Testing database connection from the container..."
docker exec redbarsushi-app bash -c 'python -c "
import os, sys
try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get(\"DB_HOST\", \"postgres\"),
        port=os.environ.get(\"DB_PORT\", \"5432\"),
        dbname=os.environ.get(\"DB_NAME\", \"redbarsushi\"),
        user=os.environ.get(\"DB_USER\", \"postgres\"),
        password=os.environ.get(\"DB_PASSWORD\", \"postgres\")
    )
    cursor = conn.cursor()
    cursor.execute(\"SELECT version()\")
    version = cursor.fetchone()
    print(f\"✅ Database connection successful: {version[0]}\")
    cursor.close()
    conn.close()
except ImportError:
    print(\"❌ psycopg2 not installed in container\")
except Exception as e:
    print(f\"❌ Database connection failed: {e}\")
    sys.exit(1)
"'

# Step 14: Test WebSocket connectivity
echo "Testing WebSocket server availability..."
# Check if the /ws/media endpoint is accessible via curl
docker exec redbarsushi-app bash -c 'curl -s http://localhost:8080/healthcheck || echo "❌ Health check endpoint not available"'

# Step 15: Print container status
echo
echo "===== Container Status ====="
docker ps -a | grep -E 'redbarsushi-app|redis|postgres'

echo
echo "===== Environment ====="
echo "Using: $ENV_FILE"
echo "Mode: $FLASK_ENV"

echo
echo "===== Restart Complete ====="
echo "RedBarSushiAI is now running with the following endpoints:"
echo "- API: http://localhost:8080"
echo "- WebSocket: ws://localhost:8080/ws/media"
echo
echo "Commands you can use:"
echo "- View logs: docker logs -f redbarsushi-app"
echo "- Access shell: docker exec -it redbarsushi-app bash"
echo "- Test WebSocket: python websocket_test_client.py --url ws://localhost:8080/ws/media"
echo "- Stop services: docker stop redbarsushi-app redis postgres"
echo "- Restart all: ./restart_docker.sh"
echo