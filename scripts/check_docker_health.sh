#!/bin/bash
# Health check script for RedBarSushiAI Docker environment

echo "===== RedBarSushiAI Docker Health Check ====="
echo

# Check for environment file parameter
ENV_FILE=".env.development"  # Default to development
if [ "$1" == "--env" ] || [ "$1" == "-e" ]; then
    if [ -n "$2" ]; then
        ENV_FILE=".env.$2"
        if [ "$2" == "dev" ] || [ "$2" == "development" ]; then
            ENV_FILE=".env.development"
        elif [ "$2" == "prod" ] || [ "$2" == "production" ]; then
            ENV_FILE=".env.production"
        fi
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
    
    if [ ! -f "$ENV_FILE" ]; then
        echo "⚠️ Warning: No environment file found. Proceeding without one."
        ENV_FILE=""
    fi
fi

if [ -n "$ENV_FILE" ]; then
    echo "🔧 Using environment file: $ENV_FILE"
    ENV_OPT="--env-file $ENV_FILE"
else
    ENV_OPT=""
fi

# Check if Docker is running
echo "Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker is not running! Please start Docker first."
    exit 1
else
    echo "✅ Docker is running"
fi

echo
echo "===== Container Status ====="
docker-compose $ENV_OPT ps

echo
echo "===== Container Logs Summary ====="
echo "Last 10 lines from each container:"

echo
echo "--- App Container Logs ---"
docker-compose $ENV_OPT logs --tail=10 app

echo
echo "--- Postgres Container Logs ---"
docker-compose $ENV_OPT logs --tail=10 postgres

echo
echo "--- Redis Container Logs ---"
docker-compose $ENV_OPT logs --tail=10 redis

echo
echo "===== Database Connection Test ====="
echo "Connecting to PostgreSQL..."
docker-compose $ENV_OPT exec postgres psql -U postgres -c "SELECT current_database(), current_user" || {
    echo "❌ Could not connect to PostgreSQL"
    echo "Try manually testing with: docker-compose $ENV_OPT exec postgres psql -U postgres -c '\\l'"
}

echo
echo "===== Redis Connection Test ====="
echo "Connecting to Redis..."
docker-compose $ENV_OPT exec redis redis-cli ping || {
    echo "❌ Could not connect to Redis"
}

echo
echo "===== Container Health ====="
for service in app postgres redis; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $(docker-compose $ENV_OPT ps -q $service) 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$HEALTH" ]; then
        echo "$service: $HEALTH"
    else
        echo "$service: No health information available"
    fi
done

echo
echo "===== Environment Variables ====="
echo "App container environment variables:"
docker-compose $ENV_OPT exec app env | grep -E 'FLASK_ENV|DATABASE_URL|REDIS_URL|POSTGRES_|CONTAINER_MODE|VOICE_HANDLER'

echo
echo "===== Network Information ====="
echo "Container IP addresses:"
docker network inspect redbarsushi-network | grep -A 3 -B 2 '"Name":'

echo
echo "===== Environment Configuration ====="
if [ -n "$ENV_FILE" ]; then
    echo "Current environment file ($ENV_FILE) settings:"
    echo "-------------------------------------------"
    grep -E '^[A-Z_]+=.+' "$ENV_FILE" | grep -v '_KEY\|TOKEN\|PASSWORD\|SECRET' | sort
    echo
    echo "Note: API keys, tokens, and passwords are hidden for security"
fi

echo
echo "===== Healthcheck Done ====="
echo "If you're encountering issues, try the following:"
echo "1. Stop all containers: docker-compose $ENV_OPT down"
echo "2. Remove volumes: docker-compose $ENV_OPT down -v"
echo "3. Rebuild and start: docker-compose $ENV_OPT up -d --build"
echo "4. Check logs with: docker-compose $ENV_OPT logs -f"