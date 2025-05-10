#!/bin/bash
# Script to run RedBarSushiAI with Docker Compose using a fixed environment file

set -e  # Exit on any error

echo "===== Starting RedBarSushiAI Docker with Fixed Environment ====="

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

# Check if .env.development.fixed exists
if [ ! -f ".env.development.fixed" ]; then
    log "❌ Error: .env.development.fixed not found"
    exit 1
fi

# Backup current .env.development if it exists
if [ -f ".env.development" ]; then
    log "Creating backup of current .env.development to .env.development.bak"
    cp .env.development .env.development.bak
fi

# Replace .env.development with our fixed version
log "Using fixed environment file"
cp .env.development.fixed .env.development

# Check Docker Compose configuration
COMPOSE_FILE="./docker/compose/docker-compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    log "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi

# Stop and remove any existing containers
log "Stopping and removing existing containers..."
docker-compose -f $COMPOSE_FILE down 2>/dev/null || true

# Make sure volumes are properly cleaned up 
log "Ensuring volumes are clean..."
docker volume prune -f

# Start Docker Compose
log "Starting Docker Compose..."
docker-compose -f $COMPOSE_FILE up -d --build

# Wait for services to be ready
log "Waiting for services to be ready..."
sleep 5

# Check if services are running
if ! docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
    log "❌ Error: Services did not start correctly"
    log "Checking logs:"
    docker-compose -f $COMPOSE_FILE logs
    exit 1
fi

log "✅ Docker Compose services are running"

# Start ngrok if available
if command -v ngrok &> /dev/null; then
    log "Starting ngrok for Twilio webhook forwarding..."
    # Kill any existing ngrok processes
    pkill -f ngrok || true
    
    # Get the app port from .env.development
    APP_PORT=$(grep "^APP_PORT=" .env.development | cut -d= -f2 || echo "8080")
    
    # Start ngrok in the background
    ngrok http $APP_PORT > /dev/null &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 3
    
    # Get the ngrok URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'http[^"]*' || echo "")
    
    if [ -n "$NGROK_URL" ]; then
        log "✅ ngrok tunnel established: $NGROK_URL"
        
        # Update the BASE_URL environment variable in the container
        log "Updating BASE_URL in the container..."
        docker-compose -f $COMPOSE_FILE exec app bash -c "export BASE_URL='$NGROK_URL'"
        
        echo
        echo "===== Twilio Configuration ====="
        echo "Update your Twilio webhook URLs to:"
        echo "Voice URL: $NGROK_URL/voice/incoming"
        echo "Status Callback URL: $NGROK_URL/voice/status-callback"
    else
        log "⚠️ ngrok URL not available. Check 'ngrok http $APP_PORT' manually."
    fi
else
    log "⚠️ ngrok not installed. Install it from https://ngrok.com/download for Twilio webhook support."
fi

# Show running containers
echo
echo "===== Running Containers ====="
docker-compose -f $COMPOSE_FILE ps

echo
echo "===== Docker Compose is Ready ====="
echo "You can access the application at:"
echo "- Local: http://localhost:$APP_PORT"
if [ -n "$NGROK_URL" ]; then
    echo "- Public (ngrok): $NGROK_URL"
fi
echo
echo "Commands:"
echo "- View logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "- Stop services: docker-compose -f $COMPOSE_FILE down"
echo "- Access shell: docker-compose -f $COMPOSE_FILE exec app bash"

# Enable enhanced debugging for OpenAI Realtime API
log "Do you want to enable enhanced debugging for OpenAI Realtime API? (y/n)"
read -r enable_debug
if [[ "$enable_debug" =~ ^[Yy] ]]; then
    log "Enabling enhanced debugging..."
    
    if [ -f "realtime_debug.sh" ]; then
        docker-compose -f $COMPOSE_FILE exec app bash -c "cd /app && bash /app/realtime_debug.sh"
        log "✅ Enhanced debugging enabled"
    else
        log "❌ realtime_debug.sh not found"
    fi
fi

echo
echo "Environment is ready for testing!"