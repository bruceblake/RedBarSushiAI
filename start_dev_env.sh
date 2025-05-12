#!/usr/bin/env bash

# Unified script to manage the RedBarSushiAI Docker development environment

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR" # Assuming this script is in the project root
ENV_FILE="$PROJECT_ROOT/.env.development"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.fixed.yml" # Default Docker Compose file

# Log function for consistent output
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] - $1"
}

# --- Helper Functions ---
check_files() {
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        log "❌ ERROR: Docker Compose file not found at $DOCKER_COMPOSE_FILE"
        exit 1
    fi
    log "✅ Using Docker Compose file: $DOCKER_COMPOSE_FILE"

    if [ ! -f "$ENV_FILE" ]; then
        log "⚠️ WARNING: Environment file not found at $ENV_FILE."
        log "⚠️ Creating basic environment file with default values."
        create_default_env_file
    else
        log "✅ Using environment file: $ENV_FILE"
    fi
}

create_default_env_file() {
    log "Creating default .env.development file..."
    cat > "$ENV_FILE" << 'EOF'
# Database configuration
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=redbarsushi

# Redis configuration
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# OpenAI API configuration
OPENAI_API_KEY=sk-mytestapikey
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Twilio configuration
TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
TWILIO_PHONE_NUMBER=+17036467799

# Deliverect configuration
DELIVERECT_API_KEY=dummy-key-for-development
DELIVERECT_CLIENT_ID=dummy-id-for-development
DELIVERECT_CLIENT_SECRET=dummy-secret-for-development

# Application configuration
STRIPE_API_KEY=dummy-key-for-development
SECRET_KEY=supersecretkey123
FASTAPI_ENV=development
FLASK_ENV=development
LOG_LEVEL=DEBUG
VOICE_HANDLER=realtime
EOF
    log "✅ Default .env.development file created"
}

clean_environment() {
    log "🧹 Stopping and removing all existing containers, volumes, and networks..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans
    docker network prune -f
    docker volume prune -f
    log "✅ Development environment cleaned"
}

start_services() {
    local build_option=""
    local detach_option=""

    if [ "$1" == "--build" ]; then
        build_option="--build"
        shift # Consume the --build argument
    fi

    if [ "$1" == "-d" ]; then
        detach_option="-d"
        shift # Consume the -d argument
    fi
    
    log "🚀 Starting services with Docker Compose..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" up $build_option $detach_option
    
    if [ -z "$detach_option" ]; then
        log "✅ Services started. Press Ctrl+C to stop."
    else
        log "✅ Services started in detached mode."
        log "   Use './start_dev_env.sh logs' to view app logs."
    fi
}

stop_services() {
    log "🛑 Stopping services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" down
    log "✅ Services stopped."
}

show_logs() {
    local service_name="app" # Default service to log
    if [ -n "$1" ]; then
        service_name="$1"
    fi
    log "👀 Tailing logs for service: $service_name..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service_name"
}

run_diagnostics() {
    log "🔍 Running diagnostic checks..."
    
    # Check if all services are running
    log "Checking container status..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" ps
    
    # Check database connectivity
    log "Checking database connectivity..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec app python /app/check_docker_services_simple.py || {
        log "⚠️ Database connectivity check failed! Copying diagnostic script to container..."
        docker cp "$PROJECT_ROOT/check_docker_services_simple.py" "redbarsushi-app:/app/"
        docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec app python /app/check_docker_services_simple.py
    }
    
    # Check OpenAI API
    log "Checking OpenAI API connectivity..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec app python /app/verify_openai_api_simple.py || {
        log "⚠️ OpenAI API check failed! Copying verification script to container..."
        docker cp "$PROJECT_ROOT/verify_openai_api_simple.py" "redbarsushi-app:/app/"
        docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$ENV_FILE" exec app python /app/verify_openai_api_simple.py
    }
    
    log "✅ Diagnostics completed"
}

start_ngrok_tunnel() {
    # Check if ngrok is installed
    if ! command -v ngrok &> /dev/null; then
        log "❌ ngrok not found! Please install ngrok first."
        log "   Visit https://ngrok.com/download to download and install ngrok."
        exit 1
    fi
    
    local port="${1:-8080}" # Default to port 8080 if not specified
    
    log "🚇 Starting ngrok tunnel for localhost:$port..."
    ngrok http "$port" &
    
    log "✅ ngrok tunnel started"
    log "⚠️ Note: You will need to update your Twilio webhook URL with the ngrok URL."
    log "   The ngrok URL can be found in the ngrok console or at http://localhost:4040"
}

show_help() {
    echo "RedBarSushiAI Development Environment Manager"
    echo "=============================================="
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  up [--build] [-d]   Start services. --build to rebuild images, -d for detached mode."
    echo "  down                Stop all running services"
    echo "  restart [--build]   Restart all services. --build to rebuild images."
    echo "  build               Build or rebuild all images without starting services"
    echo "  logs [service]      View logs for services (default: app)"
    echo "  clean               Remove all containers, volumes, and networks"
    echo "  diagnostics         Run diagnostic checks on running containers"
    echo "  ngrok [port]        Start an ngrok tunnel to expose local services to the internet"
    echo "                      Default port is 8080 if not specified"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 up               Start all services in interactive mode"
    echo "  $0 up --build -d    Rebuild images, start services in detached mode"
    echo "  $0 logs postgres    View logs for the postgres service"
    echo "  $0 ngrok 8080       Start an ngrok tunnel for port 8080"
    echo ""
}

# --- Main Execution ---
# Check command
if [ $# -eq 0 ]; then
    log "❓ No command specified. Use './start_dev_env.sh help' for usage information."
    show_help
    exit 1
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
        check_files
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