#!/bin/bash
# Basic Docker setup script for RedBarSushiAI

set -e

echo "===== Basic Docker Setup for RedBarSushiAI ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop $(docker ps -a -q) 2>/dev/null || true
docker rm $(docker ps -a -q) 2>/dev/null || true
echo "✅ All containers stopped and removed"

# Step 2: Remove volumes
echo "Step 2: Removing volumes..."
docker volume rm $(docker volume ls -q) 2>/dev/null || true
echo "✅ All volumes removed"

# Step 3: Create a simple docker-compose file
echo "Step 3: Creating docker-compose.basic.yml..."
cat > docker-compose.basic.yml << 'EOF'
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
    restart: always

  app:
    build: .
    container_name: redbarsushi-app
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/redbarsushi
      - OPENAI_API_KEY=sk-mytestapikey
    ports:
      - "8080:8080"
    command: sh -c "sleep 10 && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1"
    restart: always

volumes:
  db-data:
EOF
echo "✅ docker-compose.basic.yml created"

# Step 4: Start containers
echo "Step 4: Starting containers..."
docker compose -f docker-compose.basic.yml up -d db
sleep 10
docker compose -f docker-compose.basic.yml up -d app
echo "✅ Containers started"

# Step 5: Check PostgreSQL
echo "Step 5: Checking PostgreSQL..."
docker exec redbarsushi-db pg_isready -U postgres || echo "⚠️ PostgreSQL is not ready yet"

# Step 6: Print status
echo
echo "===== Docker Environment Status ====="
docker ps -a

echo
echo "===== Basic Docker Setup Completed ====="
echo "Your Docker environment should now be running with a basic setup."
echo
echo "The application should be available at: http://localhost:8080"
echo
echo "To view logs:"
echo "- App logs: docker logs redbarsushi-app"
echo "- Database logs: docker logs redbarsushi-db"