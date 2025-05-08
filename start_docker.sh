#!/bin/bash
# Docker startup script for RedBarSushiAI

echo "===== Starting RedBarSushiAI with Docker ====="

# Check if docker-compose exists
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose not found! Please install Docker Compose first."
    exit 1
fi

# Parse environment option
ENV_FILE=".env.development"  # Default to development environment
if [ "$1" == "--env" ] || [ "$1" == "-e" ]; then
    if [ -n "$2" ]; then
        case "$2" in
            "dev"|"development")
                ENV_FILE=".env.development"
                ;;
            "staging")
                ENV_FILE=".env.staging"
                ;;
            "prod"|"production")
                ENV_FILE=".env.production"
                ;;
            *)
                ENV_FILE=".env.$2"
                ;;
        esac
        shift 2
    else
        echo "❌ Error: No environment specified after --env"
        exit 1
    fi
fi

# Check if the environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️ Warning: Environment file $ENV_FILE not found."
    if [ "$ENV_FILE" != ".env.development" ]; then
        echo "Falling back to .env.development..."
        ENV_FILE=".env.development"
    fi
    
    # If development file also doesn't exist, suggest creating it
    if [ ! -f "$ENV_FILE" ]; then
        echo "❌ Error: $ENV_FILE not found."
        echo "Please create an environment file first or use an existing one."
        exit 1
    fi
fi

echo "🔧 Using environment file: $ENV_FILE"

# Ensure the logs directory exists
mkdir -p logs/agent logs/database logs/openai logs/stream logs/twilio logs/voice logs/websocket

# Check if we need to rebuild
if [ "$1" == "--rebuild" ] || [ "$1" == "-r" ]; then
    echo "Rebuilding containers..."
    docker-compose --env-file $ENV_FILE down
    docker-compose --env-file $ENV_FILE build --no-cache
    BUILD_ONLY=$2
elif [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    echo "Building containers..."
    docker-compose --env-file $ENV_FILE build
    BUILD_ONLY=$2
fi

# If build only flag is present, exit after building
if [ "$BUILD_ONLY" == "--only" ]; then
    echo "Build completed. Exiting without starting containers."
    exit 0
fi

# Check if we need to clean volumes
if [ "$1" == "--clean" ] || [ "$1" == "-c" ]; then
    echo "Removing all containers and volumes..."
    docker-compose --env-file $ENV_FILE down -v
fi

# Start the containers
echo "Starting containers with $ENV_FILE environment..."
docker-compose --env-file $ENV_FILE up -d

# Wait for containers to initialize
echo "Waiting for containers to initialize..."
sleep 5

# Display status
echo
echo "===== Container Status ====="
docker-compose ps

echo
echo "===== Environment ====="
echo "Using: $ENV_FILE"
echo "Mode: $(grep FLASK_ENV $ENV_FILE | cut -d= -f2 || echo 'development')"

echo
echo "===== Startup Completed ====="
echo "RedBarSushiAI is now running in Docker containers."
echo
echo "Commands you can use:"
echo "- View logs: docker-compose --env-file $ENV_FILE logs -f"
echo "- Stop services: docker-compose --env-file $ENV_FILE down"
echo "- Check health: ./check_docker_health.sh"
echo "- Shell access: docker-compose --env-file $ENV_FILE exec app bash"
echo
echo "To access the app, visit: http://localhost:8080"
echo

# Run health check if it exists
if [ -f "./check_docker_health.sh" ]; then
    echo "Running health check..."
    ./check_docker_health.sh
fi