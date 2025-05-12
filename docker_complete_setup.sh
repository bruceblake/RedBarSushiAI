#!/bin/bash
# Complete Docker setup script for RedBarSushiAI (with Redis)

set -e

echo "===== Complete Docker Setup for RedBarSushiAI ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop $(docker ps -a -q) 2>/dev/null || true
docker rm $(docker ps -a -q) 2>/dev/null || true
echo "✅ All containers stopped and removed"

# Step 2: Clean volumes if requested
if [ "$1" == "--clean" ]; then
    echo "Step 2: Removing volumes..."
    docker volume rm $(docker volume ls -q) 2>/dev/null || true
    echo "✅ All volumes removed"
else
    echo "Step 2: Keeping existing volumes (use --clean to remove)"
fi

# Step 3: Create a complete docker-compose file
echo "Step 3: Creating docker-compose.complete.yml..."
cat > docker-compose.complete.yml << 'EOF'
services:
  db:
    image: postgres:14
    container_name: redbarsushi-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: redbarsushi
    ports:
      - "5432:5432"
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: always

  redis:
    image: redis:7
    container_name: redbarsushi-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always

  app:
    build: .
    container_name: redbarsushi-app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/redbarsushi
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - OPENAI_API_KEY=sk-mytestapikey
      - TWILIO_ACCOUNT_SID=dummy_sid
      - TWILIO_AUTH_TOKEN=dummy_token
      - TWILIO_PHONE_NUMBER=+15551234567
      - STRIPE_API_KEY=dummy_stripe_key
      - FASTAPI_ENV=development
      - FLASK_ENV=development
      - LOG_LEVEL=DEBUG
      - VOICE_HANDLER=realtime
    ports:
      - "8080:8080"
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    command: >
      sh -c "
        echo 'Waiting for database and Redis...' && 
        sleep 5 && 
        echo 'Starting server...' && 
        uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug
      "
    restart: always

volumes:
  db-data:
  redis-data:
EOF
echo "✅ docker-compose.complete.yml created"

# Step 4: Start containers
echo "Step 4: Starting containers..."
docker compose -f docker-compose.complete.yml up -d
echo "✅ Containers started"

# Step 5: Wait for containers to be healthy
echo "Step 5: Waiting for services to be healthy..."
attempts=0
max_attempts=30

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-app" | grep -q "(healthy)" || docker ps | grep "redbarsushi-app" | grep -q "Up"; then
        echo "✅ Application is running"
        break
    fi
    
    echo "⏳ Waiting for services to be ready... (${attempts}/${max_attempts})"
    sleep 2
done

# Step 6: Check services
echo
echo "===== Docker Environment Status ====="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo
echo "===== Service Connection Test ====="
echo "Database:"
docker exec redbarsushi-db pg_isready -U postgres || echo "⚠️ PostgreSQL is not ready yet"

echo "Redis:"
docker exec redbarsushi-redis redis-cli ping || echo "⚠️ Redis is not ready yet"

echo "Application:"
curl -s http://localhost:8080/healthcheck || echo "⚠️ Application healthcheck failed"

echo
echo "===== Complete Docker Setup Completed ====="
echo "Your Docker environment is now running with a complete setup."
echo
echo "The application should be available at: http://localhost:8080"
echo
echo "To view logs:"
echo "- App logs: docker logs redbarsushi-app"
echo "- Database logs: docker logs redbarsushi-db"
echo "- Redis logs: docker logs redbarsushi-redis"
echo
echo "To restart this environment:"
echo "- Normal restart: ./docker_complete_setup.sh"
echo "- Clean restart (removes volumes): ./docker_complete_setup.sh --clean"