#!/bin/bash
# Script to run RedBarSushiAI with fixed Docker Compose configuration

set -e  # Exit on any error

echo "===== Starting RedBarSushiAI with Fixed Docker Configuration ====="

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

# Check if running on Render
IS_RENDER=${RENDER:-false}
if [ "$IS_RENDER" = "true" ]; then
    log "Running on Render, exiting script (intended for local use only)"
    exit 1
fi

# Base directory
BASE_DIR="$(pwd)"
COMPOSE_FILE="$BASE_DIR/docker/compose/docker-compose.fixed.yml"
ENV_FILE="$BASE_DIR/.env.development.fixed"

# Check if required files exist
if [ ! -f "$COMPOSE_FILE" ]; then
    log "❌ Error: docker-compose.fixed.yml not found at $COMPOSE_FILE"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    log "❌ Error: .env.development.fixed not found at $ENV_FILE"
    exit 1
fi

# Backup current .env.development if it exists
if [ -f "$BASE_DIR/.env.development" ]; then
    log "Creating backup of current .env.development to .env.development.bak"
    cp "$BASE_DIR/.env.development" "$BASE_DIR/.env.development.bak"
fi

# Apply our fixed environment file
log "Applying fixed environment file..."
cp "$ENV_FILE" "$BASE_DIR/.env.development"

# Stop any existing containers
log "Stopping any existing containers..."
docker-compose -f "$COMPOSE_FILE" down 2>/dev/null || true

# Clean up volumes if requested
if [ "$1" = "--clean" ]; then
    log "Cleaning up volumes..."
    docker-compose -f "$COMPOSE_FILE" down -v
    docker volume prune -f
fi

# Build and start containers
log "Building and starting containers..."
docker-compose -f "$COMPOSE_FILE" up -d --build

# Wait for containers to be ready
log "Waiting for containers to be ready..."
counter=0
max_attempts=30

while [ $counter -lt $max_attempts ]; do
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        break
    fi
    log "Waiting for containers to start ($((counter+1))/$max_attempts)..."
    sleep 2
    counter=$((counter+1))
done

if [ $counter -eq $max_attempts ]; then
    log "❌ Error: Containers failed to start in time"
    log "Logs from app container:"
    docker-compose -f "$COMPOSE_FILE" logs app
    exit 1
fi

# Get app container ID
APP_CONTAINER=$(docker-compose -f "$COMPOSE_FILE" ps -q app)
if [ -z "$APP_CONTAINER" ]; then
    log "❌ Error: Could not find app container"
    exit 1
fi

log "✅ App container is running: $APP_CONTAINER"

# Get configured app port
APP_PORT=$(grep "^APP_PORT=" "$BASE_DIR/.env.development" | cut -d= -f2 || echo "8080")
log "App is configured to use port: $APP_PORT"

# Check if ngrok is available
if command -v ngrok &> /dev/null; then
    log "Setting up ngrok for Twilio webhook forwarding..."
    
    # Kill any existing ngrok processes
    pkill -f ngrok 2>/dev/null || true
    
    # Start ngrok in background
    ngrok http $APP_PORT > /dev/null &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 3
    
    # Check if ngrok started successfully
    if ! pgrep -f "ngrok http $APP_PORT" > /dev/null; then
        log "⚠️ ngrok failed to start. Make sure it's properly configured."
    else
        # Get the ngrok URL
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'http[^"]*' || echo "")
        
        if [ -n "$NGROK_URL" ]; then
            log "✅ ngrok tunnel established: $NGROK_URL"
            
            # Update the BASE_URL in the container
            docker exec $APP_CONTAINER bash -c "export BASE_URL='$NGROK_URL'"
            
            echo
            echo "===== Twilio Configuration ====="
            echo "Update your Twilio webhook URLs to:"
            echo "Voice URL: $NGROK_URL/voice/incoming"
            echo "Status Callback URL: $NGROK_URL/voice/status-callback"
        else
            log "⚠️ Could not determine ngrok URL. Visit http://localhost:4040 to check."
        fi
    fi
else
    log "⚠️ ngrok not found. Install ngrok to expose your local server to Twilio."
    log "Visit https://ngrok.com/download for installation instructions."
fi

# Ask about enabling enhanced debugging
echo
echo "Do you want to enable enhanced debugging for OpenAI Realtime API? (y/n)"
read -r enable_debug

if [[ "$enable_debug" =~ ^[Yy] ]]; then
    log "Enabling enhanced debugging inside the container..."
    
    docker exec $APP_CONTAINER bash -c "if [ -f /app/realtime_debug.sh ]; then cd /app && bash /app/realtime_debug.sh; else echo 'Debug script not found in container'; fi"
    
    log "✅ Enhanced debugging enabled"
fi

# Display connections
echo
echo "===== Connection Information ====="
echo "App URL: http://localhost:$APP_PORT"
if [ -n "$NGROK_URL" ]; then
    echo "Public URL (ngrok): $NGROK_URL"
    echo "ngrok Web Interface: http://localhost:4040"
fi
echo
echo "===== Docker Containers ====="
docker-compose -f "$COMPOSE_FILE" ps
echo
echo "===== Commands ====="
echo "View logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "Access app shell: docker exec -it $APP_CONTAINER bash"
echo "Stop all: docker-compose -f $COMPOSE_FILE down"
echo
log "Setup complete! Your RedBarSushiAI environment is ready."