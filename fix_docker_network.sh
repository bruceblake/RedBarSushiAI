#!/bin/bash
# Script to fix Docker networking and environment issues

set -e

echo "===== Fixing Docker Environment Issues ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop $(docker ps -a -q) 2>/dev/null || true
docker rm -f $(docker ps -a -q) 2>/dev/null || true
echo "✅ All containers stopped and removed"

# Step 2: Clean up all volumes and networks
echo "Step 2: Cleaning up Docker volumes and networks..."
docker volume rm $(docker volume ls -q) 2>/dev/null || true
docker network prune -f
echo "✅ All volumes and networks cleaned up"

# Step 3: Create a simplified docker-compose file
echo "Step 3: Creating simplified docker-compose file..."
cat > docker-compose.simple.yml << 'EOF'
version: '3.8'

services:
  db:
    image: postgres:14
    container_name: redbarsushi-db
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=redbarsushi
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    networks:
      - app_network

  redis:
    image: redis:7
    container_name: redbarsushi-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: always
    networks:
      - app_network

  app:
    build: .
    container_name: redbarsushi-app
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/redbarsushi
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - OPENAI_API_KEY=sk-mytestapikey
      - TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
      - TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
      - TWILIO_PHONE_NUMBER=+17036467799
      - STRIPE_API_KEY=dummy-key-for-development
      - FASTAPI_ENV=development
      - FLASK_ENV=development
      - LOG_LEVEL=DEBUG
      - VOICE_HANDLER=realtime
      - SECRET_KEY=supersecretkey123
    ports:
      - "8080:8080"
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    networks:
      - app_network
    command: >
      sh -c "
        echo '🔍 Checking environment variables...' &&
        echo 'DATABASE_URL: ' $DATABASE_URL &&
        echo 'TWILIO_ACCOUNT_SID: ' $TWILIO_ACCOUNT_SID &&
        echo 'OPENAI_API_KEY: ' $OPENAI_API_KEY &&
        echo '⏳ Waiting for database...' &&
        sleep 10 &&
        echo '🚀 Starting server...' &&
        uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug
      "
    restart: always

networks:
  app_network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
EOF
echo "✅ docker-compose.simple.yml created"

# Step 4: Create app.py file to test database connection
echo "Step 4: Creating database test script..."
cat > test_db_connection.py << 'EOF'
#!/usr/bin/env python3
"""Test script for database connection."""

import os
import sys
import time
import psycopg2

def test_connection():
    """Test database connection with retry logic."""
    print("\n===== Testing Database Connection =====")
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        print(f"Using DATABASE_URL: {db_url}")
    else:
        print(f"Using connection parameters: {user}@{host}:{port}/{dbname}")
    
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"\nAttempt {attempt}/{max_attempts}...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=5
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            
            print(f"\n✅ Connection successful!")
            print(f"PostgreSQL version: {version[0]}")
            
            cursor.close()
            conn.close()
            return True
        
        except Exception as e:
            print(f"\n❌ Connection failed: {e}")
            if attempt < max_attempts:
                print(f"Retrying in 3 seconds...")
                time.sleep(3)
    
    return False

if __name__ == "__main__":
    if test_connection():
        print("\n✅ DATABASE CONNECTION: SUCCESS")
        sys.exit(0)
    else:
        print("\n❌ DATABASE CONNECTION: FAILED after multiple attempts")
        sys.exit(1)
EOF
chmod +x test_db_connection.py
echo "✅ Database test script created"

# Step 5: Start the environment
echo "Step 5: Starting Docker environment..."
docker compose -f docker-compose.simple.yml up -d
echo "✅ Docker environment started"

# Step 6: Wait for containers to start
echo "Step 6: Waiting for containers to start..."
sleep 10
echo "✅ Waited for containers to start"

# Step 7: Check container status
echo
echo "===== Container Status ====="
docker ps
echo

# Step 8: Check app container logs
echo "===== Application Container Logs ====="
docker logs redbarsushi-app
echo

# Step 9: Test database connection
echo "Step 9: Testing database connection..."
docker cp test_db_connection.py redbarsushi-app:/app/
docker exec redbarsushi-app python /app/test_db_connection.py || true
echo

echo
echo "===== Docker Environment Setup Complete ====="
echo "If there are still connection issues, here are additional troubleshooting steps:"
echo
echo "1. Check container networking:"
echo "   docker network inspect app_network"
echo
echo "2. Verify environment variables:"
echo "   docker exec redbarsushi-app env | grep -E 'DATABASE|REDIS|TWILIO|OPENAI|STRIPE'"
echo
echo "3. Test database connection manually:"
echo "   docker exec -it redbarsushi-db psql -U postgres -d redbarsushi -c 'SELECT 1'"
echo
echo "4. Restart with the following command if issues persist:"
echo "   ./fix_docker_network.sh"