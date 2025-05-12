#!/usr/bin/env bash

# Unified script to manage the RedBarSushiAI Docker development environment

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR" # Assuming this script is in the project root
ENV_FILE="$PROJECT_ROOT/.env.development"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.fixed.yml" # Default Docker Compose file

# Log function for consistent output
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')][RedBarSushiDev] - $1"
}

# --- Helper Functions ---
check_files() {
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        log "❌ ERROR: Docker Compose file not found at $DOCKER_COMPOSE_FILE"
        log "Ensure it exists or update DOCKER_COMPOSE_FILE variable in this script."
        exit 1
    fi
    log "✅ Using Docker Compose file: $DOCKER_COMPOSE_FILE"

    if [ ! -f "$ENV_FILE" ]; then
        log "⚠️ WARNING: Environment file not found at $ENV_FILE."
        log "⚠️ Creating basic .env.development file with PLACEHOLDERS."
        log "👉 IMPORTANT: You MUST edit $ENV_FILE and replace placeholders with your actual credentials/keys!"
        create_placeholder_env_file
    else
        log "✅ Using environment file: $ENV_FILE"
        # Check if critical keys are still placeholders
        if grep -q "YOUR_DEV_OPENAI_KEY_HERE" "$ENV_FILE" || grep -q "YOUR_DEV_TWILIO_AUTH_TOKEN_HERE" "$ENV_FILE"; then
            log "🔥🔥🔥 WARNING: $ENV_FILE seems to contain placeholder API keys/secrets. Please update it with real values! 🔥🔥🔥"
        fi
    fi
}

create_placeholder_env_file() {
    log "Creating placeholder .env.development file..."
    cat >"$ENV_FILE" <<EOF
# RedBarSushi Development Environment Variables
# ❗❗❗ IMPORTANT: Replace placeholder values with your actual development credentials! ❗❗❗

# Server Configuration
APP_ENV=development
FASTAPI_ENV=development
FLASK_ENV=development
LOG_LEVEL=DEBUG
VOICE_HANDLER=realtime
FORCE_HEADLESS=true
IS_STAGING=true
OPENAI_REALTIME_VAD_SILENCE_MS=1000

# Security
APP_SECRET_KEY=REPLACE_WITH_A_STRONG_RANDOM_SECRET_KEY_FOR_DEVELOPMENT

# Database Configuration (for Docker Compose service names)
# Ensure these service names match your docker-compose.fixed.yml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=redbarsushi
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/redbarsushi

# Database variables in alternative format (for compatibility)
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=postgres
DB_PORT=5432
DB_NAME=redbarsushi

# Redis Configuration
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# OpenAI Configuration - Use REAL (test-tier if possible) key for development
OPENAI_API_KEY=sk-YOUR_DEV_OPENAI_KEY_HERE
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Twilio Configuration - Use REAL test credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=YOUR_DEV_TWILIO_AUTH_TOKEN_HERE
TWILIO_PHONE_NUMBER=+15551234567 # A Twilio number you own for testing

# Deliverect Configuration
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=YOUR_DEV_DELIVERECT_API_KEY_HERE
DELIVERECT_CLIENT_ID=YOUR_DEV_DELIVERECT_CLIENT_ID_HERE
DELIVERECT_CLIENT_SECRET=YOUR_DEV_DELIVERECT_CLIENT_SECRET_HERE
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application URL (Ngrok will provide the public one for Twilio)
BASE_URL=http://localhost:\${APP_PORT:-8080}

# Docker Ports (host:container)
APP_PORT=8080
POSTGRES_PORT=5433
REDIS_PORT=6380
EOF
    log "✅ Placeholder .env.development file created. 🔥 EDIT IT NOW with your credentials! 🔥"
}

clean_environment() {
    log "🧹 Stopping and removing development services, their volumes, and orphaned containers..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans
    # This is safer than pruning all networks and volumes globally
    log "✅ Development environment cleaned."
}

start_services() {
    local build_option=""
    local detach_option=""

    # Process arguments for start_services
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --build) build_option="--build"; shift ;;
            -d) detach_option="-d"; shift ;;
            *) log "Unknown option to start_services: $1"; shift ;; # Or error out
        esac
    done

    log "🚀 Starting services (PostgreSQL, Redis, App) using Docker Compose..."
    log "   Compose file: $DOCKER_COMPOSE_FILE"
    log "   Env file: $ENV_FILE"
    if [ -n "$build_option" ]; then log "   Option: Rebuilding images"; fi
    if [ -n "$detach_option" ]; then log "   Option: Running in detached mode"; fi

    # Ensure Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        log "❌ ERROR: Docker daemon is not running. Please start Docker Desktop or Docker service."
        exit 1
    fi
    
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" up $build_option $detach_option

    if [ -z "$detach_option" ]; then
        log "✅ Services started. Press Ctrl+C to stop."
    else
        log "✅ Services started in detached mode."
        log "   Run '$0 logs' or '$0 logs app' to view app logs."
        log "   Run '$0 diagnostics' to check service health after a few moments."
    fi
}

stop_services() {
    log "🛑 Stopping development services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
    log "✅ Development services stopped."
}

show_logs() {
    local service_name="${1:-app}" # Default service to log
    log "👀 Tailing logs for service: $service_name..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service_name"
}

run_diagnostics() {
    log "🔍 Running diagnostic checks..."

    log "--- Container Status ---"
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" ps
    echo "" # Newline for readability

    # Define your app service name as it appears in docker-compose.yml
    local app_service_name="app" # Adjust if your service name is different

    # Check database connectivity from within the app container
    log "--- Database Connectivity (from app container) ---"
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$app_service_name" python /app/check_docker_services_simple.py || {
        log "⚠️ Database connectivity check failed! Copying diagnostic script to container..."
        # Try to copy the script if not found in container
        docker cp "$PROJECT_ROOT/check_docker_services_simple.py" "redbarsushi-app:/app/" 2>/dev/null
        docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$app_service_name" python /app/check_docker_services_simple.py
    }
    echo ""

    # Check OpenAI API connectivity from within the app container
    log "--- OpenAI API Connectivity (from app container) ---"
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$app_service_name" python /app/verify_openai_api_simple.py || {
        log "⚠️ OpenAI API check failed! Copying verification script to container..."
        # Try to copy the script if not found in container
        docker cp "$PROJECT_ROOT/verify_openai_api_simple.py" "redbarsushi-app:/app/" 2>/dev/null
        docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$app_service_name" python /app/verify_openai_api_simple.py
    }
    echo ""
    log "✅ Diagnostics completed."
}

start_ngrok_tunnel() {
    if ! command -v ngrok &>/dev/null; then
        log "❌ ngrok not found! Please install ngrok first."
        log "   Visit https://ngrok.com/download to download and install ngrok, then authenticate it."
        exit 1
    fi

    # Get APP_PORT from .env.development, default to 8080 if not set
    local port="8080" # Default
    if [ -f "$ENV_FILE" ]; then
        app_port_from_env=$(grep '^APP_PORT=' "$ENV_FILE" | cut -d '=' -f2)
        if [ -n "$app_port_from_env" ]; then
            port="$app_port_from_env"
        fi
    fi
    # Allow overriding with an argument
    port="${1:-$port}"

    log "🚇 Starting ngrok tunnel for localhost:$port..."
    log "   Make sure your app service in Docker Compose maps to host port $port."
    
    # Run ngrok
    ngrok http "$port"
}

show_help() {
    echo "RedBarSushiAI Development Environment Manager"
    echo "=============================================="
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Manages the Docker Compose environment defined in '$DOCKER_COMPOSE_FILE'"
    echo "using environment variables from '$ENV_FILE'."
    echo ""
    echo "Commands:"
    echo "  up [--build] [-d]   Start services. --build to rebuild images. -d for detached mode."
    echo "                        (Default action if no command is given: runs 'up --build')"
    echo "  down                Stop all running services defined in the compose file."
    echo "  restart [--build]   Restart all services. --build to rebuild images."
    echo "  build               Build or rebuild all service images."
    echo "  logs [service]      View logs for 'app' (default) or a specified service."
    echo "  clean               Stop and REMOVE all containers, project-specific volumes, and networks."
    echo "  diagnostics         Run diagnostic checks (container status, DB/OpenAI connectivity from app)."
    echo "  ngrok [port]        Start an ngrok tunnel. Uses APP_PORT from .env.development or defaults to 8080."
    echo "                      (Requires ngrok installed and authenticated)."
    echo "  help                Show this help message."
    echo ""
    echo "Examples:"
    echo "  $0                    (Defaults to: $0 up --build)"
    echo "  $0 up --build -d      Rebuild and start services in detached mode."
    echo "  $0 logs postgres      View logs for the postgres service."
    echo ""
    echo "Ensure '$ENV_FILE' is present and correctly configured before running."
}

# --- Main Execution ---

# Default action if no command is given
if [ $# -eq 0 ]; then
    log "No command provided. Defaulting to 'up --build'."
    check_files
    start_services "--build"
    exit 0
fi

# Process commands
case "$1" in
"up")
    shift
    check_files
    start_services "$@"
    ;;
"down")
    check_files
    stop_services
    ;;
"restart")
    shift
    check_files
    stop_services
    start_services "$@"
    ;;
"build")
    check_files
    log "🛠️ Building images..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" build
    log "✅ Images built."
    ;;
"logs")
    shift
    show_logs "$@"
    ;;
"clean")
    check_files
    clean_environment
    ;;
"diagnostics")
    check_files
    run_diagnostics
    ;;
"ngrok")
    shift
    start_ngrok_tunnel "$@"
    ;;
"help")
    show_help
    ;;
*)
    log "❌ Unknown command: $1"
    show_help
    exit 1
    ;;
esac

exit 0
