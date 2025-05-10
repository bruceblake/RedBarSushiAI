#!/bin/bash
# Complete script to start the RedBarSushiAI Docker environment with ngrok and development environment variables

set -e  # Exit on any error

echo "===== Starting RedBarSushiAI Docker Environment with ngrok ====="

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

# Step 1: Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    log "❌ Error: ngrok is not installed. Please install it from https://ngrok.com/download"
    exit 1
fi

# Step 2: Set the path to the docker-compose.yml file
COMPOSE_FILE="./docker/compose/docker-compose.yml"

# Check if the docker-compose.yml file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    log "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi
log "✅ Using docker-compose.yml from: $COMPOSE_FILE"

# Step 3: Create or ensure .env.development exists
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
    log "📝 Creating $ENV_FILE..."
    
    # Create a template .env.development file
    cat > "$ENV_FILE" << EOF
# Development environment variables for RedBarSushiAI
FLASK_ENV=development
FASTAPI_ENV=development
FLASK_DEBUG=1
LOG_LEVEL=DEBUG

# OpenAI settings
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Database settings
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=redbarsushi
POSTGRES_PORT=5434

# Redis settings
REDIS_URL=redis://redis:6379/0
REDIS_PORT=6379
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Twilio settings
TWILIO_ACCOUNT_SID=AC-your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1your-twilio-phone-number

# Deliverect settings
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=your-deliverect-api-key
DELIVERECT_BASE_URL=https://api.staging.deliverect.com
DELIVERECT_API_URL=https://api.staging.deliverect.com/v2/orders
DELIVERECT_CLIENT_ID=your-deliverect-client-id
DELIVERECT_CLIENT_SECRET=your-deliverect-client-secret

# Application settings
APP_PORT=8080
FORCE_HEADLESS=true
VOICE_HANDLER=realtime
RENDER=false
EOF

    log "📝 Created $ENV_FILE template. Please update it with your API keys."
    log "⚠️ Important: Update your OpenAI API key in $ENV_FILE before continuing!"
    exit 1
else
    log "✅ Found environment file: $ENV_FILE"
fi

# Step 4: Force stop and remove all existing containers
log "Stopping and removing all existing containers..."
docker stop redis postgres redbarsushi-app ngrok-container 2>/dev/null || true
docker rm -f redis postgres redbarsushi-app ngrok-container 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=redis" -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=postgres" -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=redbarsushi" -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter "name=ngrok" -q) 2>/dev/null || true
log "✅ All containers stopped and removed"

# Step 5: Remove networks
log "Removing networks..."
docker network rm redbarsushi-network 2>/dev/null || true
log "✅ Networks removed"

# Step 6: Extract environment variables from .env.development
log "Extracting environment variables from $ENV_FILE..."

# More reliable way to extract variables
OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
FASTAPI_ENV=$(grep "^FASTAPI_ENV=" "$ENV_FILE" | cut -d= -f2-)
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
APP_PORT=$(grep "^APP_PORT=" "$ENV_FILE" | cut -d= -f2- || echo "8080")

# Verify API key is present and not the template version
if [[ "$OPENAI_API_KEY" == "sk-your-openai-api-key" || -z "$OPENAI_API_KEY" ]]; then
    log "❌ Error: Please update your OPENAI_API_KEY in $ENV_FILE"
    exit 1
fi

log "✅ Environment variables extracted"
log "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."
log "Using app port: $APP_PORT"

# Step 7: Create a network for the containers
log "Creating Docker network..."
docker network create redbarsushi-network || true

# Step 8: Start Redis
log "Starting Redis container..."
docker run -d --name redis \
  --network redbarsushi-network \
  -p 6379:6379 \
  redis:6

# Step 9: Start PostgreSQL
log "Starting PostgreSQL container..."
docker run -d --name postgres \
  --network redbarsushi-network \
  -p 5434:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=redbarsushi \
  -v "$(pwd)/db/init:/docker-entrypoint-initdb.d" \
  postgres:14

# Step 10: Wait for PostgreSQL to initialize
log "Waiting for PostgreSQL to initialize..."
sleep 5

# Verify PostgreSQL is running and properly initialized
log "Verifying PostgreSQL connection..."
max_attempts=10
attempt=1
while [ $attempt -le $max_attempts ]; do
    if docker exec postgres pg_isready -U postgres; then
        log "✅ PostgreSQL is ready"
        break
    else
        log "⚠️ PostgreSQL not ready yet, waiting... (attempt $attempt/$max_attempts)"
        sleep 5
        attempt=$((attempt+1))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    log "❌ PostgreSQL failed to initialize after multiple attempts"
    log "Checking PostgreSQL logs for errors:"
    docker logs postgres
    exit 1
fi

# Step 11: Check if schema was created successfully
log "Verifying database schema..."
if ! docker exec postgres psql -U postgres -d redbarsushi -c "\dt" 2>/dev/null | grep -q menu_items; then
    log "⚠️ Database schema not found, initializing schema manually..."
    # Remove the trailing EOF line if it exists
    cat db/init/01_schema.sql | grep -v "^EOF" | docker exec -i postgres psql -U postgres -d redbarsushi
fi

# Step 12: Check if the schema is already created
if ! docker exec postgres psql -U postgres -d redbarsushi -c "\dt" | grep -q menu_items; then
    log "⚠️ Database schema still not initialized correctly. Trying alternative approach..."
    schema_sql=$(cat db/init/01_schema.sql)
    docker exec -i postgres psql -U postgres -d redbarsushi <<EOF
$schema_sql
EOF
    log "Alternative schema initialization completed."
fi

# Step 13: Check if the image exists
if ! docker image inspect redbarsushiai-app >/dev/null 2>&1; then
    log "⚠️ redbarsushiai-app image not found. Building it..."
    docker build -f docker/images/Dockerfile -t redbarsushiai-app .
fi

# Step 14: Start the app container with all environment variables from .env.development
log "Starting RedBarSushiAI app container..."
docker run -d --name redbarsushi-app \
  --network redbarsushi-network \
  -p $APP_PORT:8080 \
  --env-file "$ENV_FILE" \
  -e "REDIS_URL=redis://redis:6379/0" \
  -e "DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi" \
  -e "VOICE_HANDLER=realtime" \
  -e "FORCE_HEADLESS=true" \
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

log "✅ RedBarSushiAI app container started"

# Step 15: Apply fixes on the container
log "Applying fixes to the container..."
docker exec redbarsushi-app bash -c "
if [ -f '/app/fix_render_deploy.sh' ]; then
    echo 'Running fix_render_deploy.sh...'
    cd /app && bash fix_render_deploy.sh
fi
"

# Step 16: Start ngrok to expose the app to the internet
log "Starting ngrok container to expose the app..."
docker run -d --name ngrok-container \
  --network redbarsushi-network \
  -e "NGROK_AUTHTOKEN=${NGROK_AUTHTOKEN:-''}" \
  -p 4040:4040 \
  ngrok/ngrok:latest http redbarsushi-app:8080

# Step 17: Wait for ngrok to initialize
log "Waiting for ngrok to initialize..."
sleep 5

# Step 18: Get the ngrok public URL
log "Fetching ngrok public URL..."
max_attempts=10
attempt=1
while [ $attempt -le $max_attempts ]; do
    NGROK_PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'http[^"]*' || echo "")
    
    if [ -n "$NGROK_PUBLIC_URL" ]; then
        log "✅ ngrok public URL: $NGROK_PUBLIC_URL"
        break
    else
        log "⚠️ ngrok URL not available yet, waiting... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt+1))
    fi
done

if [ -z "$NGROK_PUBLIC_URL" ]; then
    log "⚠️ Could not retrieve ngrok URL. You can check it manually at http://localhost:4040"
else
    # Update BASE_URL environment variable in the container
    log "Updating BASE_URL to ngrok URL in the container..."
    docker exec redbarsushi-app bash -c "export BASE_URL='$NGROK_PUBLIC_URL'"
fi

# Step 19: Verify environment variables
log "Verifying environment variables in the container..."
docker exec redbarsushi-app bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."'
docker exec redbarsushi-app bash -c 'echo "FASTAPI_ENV: $FASTAPI_ENV"'
docker exec redbarsushi-app bash -c 'echo "VOICE_HANDLER: $VOICE_HANDLER"'
docker exec redbarsushi-app bash -c 'echo "DATABASE_URL: $DATABASE_URL"'
docker exec redbarsushi-app bash -c 'echo "BASE_URL: $BASE_URL"'

# Step 20: Test database connection from inside the container
log "Testing database connection from the container..."
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

# Step 21: Test WebSocket connectivity
log "Testing WebSocket server availability..."
docker exec redbarsushi-app bash -c 'curl -s http://localhost:8080/healthcheck || echo "❌ Health check endpoint not available"'

# Step 22: Print container status
echo
echo "===== Container Status ====="
docker ps -a | grep -E 'redbarsushi-app|redis|postgres|ngrok'

echo
echo "===== Environment ====="
echo "Using: $ENV_FILE"
echo "Mode: $FASTAPI_ENV"

if [ -n "$NGROK_PUBLIC_URL" ]; then
    echo "Public URL: $NGROK_PUBLIC_URL"
fi

echo
echo "===== Setup Complete ====="
echo "RedBarSushiAI is now running with the following endpoints:"
echo "- Local API: http://localhost:$APP_PORT"
echo "- Local WebSocket: ws://localhost:$APP_PORT/ws/media"

if [ -n "$NGROK_PUBLIC_URL" ]; then
    echo "- Public API: $NGROK_PUBLIC_URL"
    echo "- Public WebSocket: ${NGROK_PUBLIC_URL/http/ws}/ws/media"
fi

echo 
echo "ngrok admin interface: http://localhost:4040"
echo
echo "Commands you can use:"
echo "- View logs: docker logs -f redbarsushi-app"
echo "- Access shell: docker exec -it redbarsushi-app bash"
echo "- Test WebSocket: python websocket_test_client.py --url ws://localhost:$APP_PORT/ws/media"
echo "- Stop services: docker stop redbarsushi-app redis postgres ngrok-container"
echo "- Restart all: ./start_docker_with_ngrok.sh"
echo
echo "To configure Twilio to use your ngrok URL:"
echo "1. Go to https://www.twilio.com/console/voice/twiml/apps"
echo "2. Update your TwiML app's Voice 'REQUEST URL' to: ${NGROK_PUBLIC_URL}/voice/incoming"
echo "3. Update your TwiML app's Voice 'STATUS CALLBACK URL' to: ${NGROK_PUBLIC_URL}/voice/status-callback"
echo
echo "Note: ngrok URL will change each time you restart this script unless you have a paid ngrok account."