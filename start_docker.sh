#!/bin/bash
# Docker startup script for RedBarSushiAI

echo "===== Starting RedBarSushiAI with Docker ====="

# Set the path to the docker-compose.yml file
COMPOSE_FILE="./docker/compose/docker-compose.yml"

# Check if the docker-compose.yml file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi
echo "✅ Using docker-compose.yml from: $COMPOSE_FILE"

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

# Verify OPENAI_API_KEY is present in the environment file
if ! grep -q "OPENAI_API_KEY" "$ENV_FILE"; then
    echo "❌ Error: OPENAI_API_KEY not found in $ENV_FILE"
    echo "Please add your OpenAI API key to the environment file."
    exit 1
fi

# Check if we need to stop running containers first
if [ "$1" == "--restart" ] || [ "$1" == "-r" ]; then
    echo "Stopping existing containers..."
    docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE down
    shift
fi

# Check if we need to rebuild
if [ "$1" == "--rebuild" ] || [ "$1" == "-b" ]; then
    echo "Rebuilding containers..."
    docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE down
    docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE build --no-cache
    BUILD_ONLY=$2
elif [ "$1" == "--build" ]; then
    echo "Building containers without cache..."
    docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE build
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
    docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE down -v
fi

# Create a docker-compose override file to explicitly pass environment variables
OVERRIDE_FILE="./docker/compose/docker-compose.override.yml"
echo "Creating $OVERRIDE_FILE..."
cat > $OVERRIDE_FILE << EOF
services:
  app:
    environment:
      - OPENAI_API_KEY=$(grep OPENAI_API_KEY $ENV_FILE | cut -d= -f2)
      - TWILIO_ACCOUNT_SID=$(grep TWILIO_ACCOUNT_SID $ENV_FILE | cut -d= -f2)
      - TWILIO_AUTH_TOKEN=$(grep TWILIO_AUTH_TOKEN $ENV_FILE | cut -d= -f2)
      - TWILIO_PHONE_NUMBER=$(grep TWILIO_PHONE_NUMBER $ENV_FILE | cut -d= -f2)
      - DELIVERECT_CHANNEL_NAME=$(grep DELIVERECT_CHANNEL_NAME $ENV_FILE | cut -d= -f2)
      - DELIVERECT_API_KEY=$(grep DELIVERECT_API_KEY $ENV_FILE | cut -d= -f2)
      - DELIVERECT_BASE_URL=$(grep DELIVERECT_BASE_URL $ENV_FILE | cut -d= -f2)
      - FLASK_ENV=$(grep FLASK_ENV $ENV_FILE | cut -d= -f2)
      - FLASK_DEBUG=$(grep FLASK_DEBUG $ENV_FILE | cut -d= -f2)
      - LOG_LEVEL=$(grep LOG_LEVEL $ENV_FILE | cut -d= -f2)
      - VOICE_HANDLER=realtime
      - FORCE_HEADLESS=true
      - IS_STAGING=true
    volumes:
      - ../../logs:/app/logs
      - ../../app:/app/app
      - ../../init_database.py:/app/init_database.py
      - ../../menu_data.json:/app/menu_data.json
    command: ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "--bind", "0.0.0.0:8080", "--timeout", "120", "--log-level", "debug"]
EOF
echo "✅ $OVERRIDE_FILE created"

# Start the containers
echo "Starting containers with $ENV_FILE environment..."
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d

# Wait for containers to initialize
echo "Waiting for containers to initialize..."
sleep 10

# Verify API keys are passed correctly
echo "Verifying environment configuration..."
docker-compose -f $COMPOSE_FILE exec app bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."; echo "FLASK_ENV: $FLASK_ENV"; echo "LOG_LEVEL: $LOG_LEVEL"'

# Initialize database structure
echo "Initializing database..."
docker-compose -f $COMPOSE_FILE exec app bash -c 'python -c "from app import create_app, db; app = create_app(); with app.app_context(): db.create_all(); print(\"Database initialized successfully\")" || echo "Database initialization failed"'

# Display status
echo
echo "===== Container Status ====="
docker-compose -f $COMPOSE_FILE ps

echo
echo "===== Environment ====="
echo "Using: $ENV_FILE"
echo "Mode: $(grep FLASK_ENV $ENV_FILE | cut -d= -f2 || echo 'development')"

echo
echo "===== Startup Completed ====="
echo "RedBarSushiAI is now running in Docker containers."
echo
echo "Commands you can use:"
echo "- View logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "- Stop services: docker-compose -f $COMPOSE_FILE down"
echo "- Restart services: ./start_docker.sh --restart"
echo "- Shell access: docker-compose -f $COMPOSE_FILE exec app bash"
echo
echo "To access the app, visit: http://localhost:8080"
echo

# Run health check if it exists
if [ -f "./scripts/check_docker_health.sh" ]; then
    echo "Running health check..."
    ./scripts/check_docker_health.sh
elif [ -f "./check_docker_health.sh" ]; then
    echo "Running health check..."
    ./check_docker_health.sh
fi