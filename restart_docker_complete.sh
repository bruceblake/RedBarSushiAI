#!/bin/bash
# Complete script to restart Docker environment for RedBarSushiAI

set -e  # Exit on any error

echo "===== Restarting RedBarSushiAI Docker Environment ====="

# Step 1: Clean up existing containers
echo "Step 1: Stopping and removing existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker network rm redbarsushi-dev-network 2>/dev/null || true
echo "✅ Containers and network cleaned up"

# Step 2: Create necessary directories
echo "Step 2: Creating required directories..."
mkdir -p docker/images
mkdir -p logs
mkdir -p db/init
echo "✅ Directories created"

# Step 3: Create .env.development file if it doesn't exist
if [ ! -f .env.development ]; then
    echo "Step 3: Creating .env.development file..."
    cat > .env.development << 'EOF'
# RedBarSushi Development Environment Variables

# Server Configuration
FASTAPI_ENV=development
FLASK_ENV=development
LOG_LEVEL=DEBUG
VOICE_HANDLER=realtime
FORCE_HEADLESS=true
IS_STAGING=true
OPENAI_REALTIME_VAD_SILENCE_MS=1000

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=redbarsushi
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi

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

# OpenAI Configuration
OPENAI_API_KEY=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

# Twilio Configuration
TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
TWILIO_PHONE_NUMBER=+17036467799

# Deliverect Configuration
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=your_deliverect_api_key_here
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Docker Ports (host:container)
APP_PORT=8080
POSTGRES_PORT=5433
REDIS_PORT=6380
EOF
    echo "✅ .env.development file created"
else
    echo "Step 3: .env.development file already exists"
fi

# Step 4: Create Pydantic fix script
echo "Step 4: Creating Pydantic fix script..."
cat > fix_pydantic.py << 'EOF'
#!/usr/bin/env python3
"""
Script to fix Pydantic version issues by downgrading to v1.10.13 if v2 is detected.
"""
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_pydantic_version():
    try:
        import pydantic
        return pydantic.__version__
    except ImportError:
        logger.warning("Pydantic not found")
        return None

def install_pydantic_v1():
    logger.info("Installing Pydantic v1.10.13...")
    cmd = [sys.executable, "-m", "pip", "install", "pydantic==1.10.13", "--force-reinstall"]
    try:
        subprocess.check_call(cmd)
        logger.info("Successfully installed Pydantic v1.10.13")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Pydantic v1.10.13: {e}")
        return False

def fix_pydantic():
    version = check_pydantic_version()
    if version:
        logger.info(f"Detected Pydantic version: {version}")
        if version.startswith("2."):
            logger.info("Detected Pydantic v2, installing v1.10.13 for compatibility")
            return install_pydantic_v1()
        elif version.startswith("1."):
            logger.info("Pydantic v1 already installed, no action needed")
            return True
    else:
        logger.info("Pydantic not found, installing v1.10.13")
        return install_pydantic_v1()

if __name__ == "__main__":
    logger.info("Running Pydantic version fix")
    if fix_pydantic():
        logger.info("✅ Pydantic setup is now correct")
        sys.exit(0)
    else:
        logger.error("❌ Failed to fix Pydantic setup")
        sys.exit(1)
EOF
chmod +x fix_pydantic.py
echo "✅ Pydantic fix script created"

# Step 5: Create docker-compose.yml file
echo "Step 5: Creating docker-compose file..."
cat > docker-compose.development.yml << 'EOF'
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: redbarsushi-app-dev
    ports:
      - "${APP_PORT:-8080}:8080"
    env_file:
      - .env.development
    environment:
      - PYTHONUNBUFFERED=1
      - TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
      - TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
      - TWILIO_PHONE_NUMBER=+17036467799
      - STRIPE_API_KEY=dummy-key-for-development
      - POSTGRES_PASSWORD=postgres
      - DB_PASSWORD=postgres
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthcheck"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
      - ./:/app/
    networks:
      - redbarsushi-dev-network
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: ["/bin/bash", "-c", "cd /app && python fix_pydantic.py && echo '📦 Using Pydantic:' && pip show pydantic | grep Version && export POSTGRES_PASSWORD=postgres && export DB_PASSWORD=postgres && echo 'Database credentials set' && sleep 5 && python check_db.py && python init_db.py && echo 'Starting server...' && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug"]

  postgres:
    image: postgres:14
    container_name: redbarsushi-postgres-dev
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=redbarsushi
    ports:
      - "${POSTGRES_PORT:-5433}:5432"
    volumes:
      - postgres-dev-data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - redbarsushi-dev-network
    extra_hosts:
      - "host.docker.internal:host-gateway"

  redis:
    image: redis:6
    container_name: redbarsushi-redis-dev
    ports:
      - "${REDIS_PORT:-6380}:6379"
    volumes:
      - redis-dev-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - redbarsushi-dev-network
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  redbarsushi-dev-network:
    driver: bridge

volumes:
  postgres-dev-data:
  redis-dev-data:
EOF
echo "✅ docker-compose.development.yml file created"

# Step 6: Start Docker services
echo "Step 6: Starting Docker services..."
# Using --force-recreate to ensure we get fresh containers
docker compose -f docker-compose.development.yml up -d --build --force-recreate
echo "✅ Docker services started"

# Step 7: Wait for services to be ready
echo "Step 7: Waiting for services to be ready..."
attempts=0
max_attempts=30
all_healthy=false

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-app-dev" | grep -q "(healthy)"; then
        all_healthy=true
        break
    fi
    
    echo "⏳ Waiting for containers to be healthy... ($attempts/$max_attempts)"
    sleep 2
done

if [ "$all_healthy" = true ]; then
    echo "✅ All containers are healthy!"
else
    echo "⚠️ Containers may not be fully healthy yet. Check with 'docker ps'"
fi

# Step 8: Display status and useful commands
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Development Environment ====="
echo "• API: http://localhost:8080"
echo "• WebSocket Test: ws://localhost:8080/ws-test/test"
echo "• Health Check: http://localhost:8080/healthcheck"
echo

echo "You can manage the environment with these commands:"
echo "• View logs: docker logs -f redbarsushi-app-dev"
echo "• Enter container: docker exec -it redbarsushi-app-dev bash"
echo "• Restart: ./restart_docker_complete.sh"
echo "• Stop all: docker compose -f docker-compose.development.yml down"
echo "• Clean restart: docker compose -f docker-compose.development.yml down -v && ./restart_docker_complete.sh"
echo
echo "===== Setup Complete ====="