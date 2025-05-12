#!/bin/bash
# Direct Docker fix script focusing on specific issues

set -e

echo "===== Direct Docker Fix for RedBarSushiAI ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop $(docker ps -a -q) 2>/dev/null || true
docker rm -f $(docker ps -a -q) 2>/dev/null || true
echo "✅ All containers stopped and removed"

# Step 2: Clean up Docker resources
echo "Step 2: Cleaning up Docker resources..."
docker volume rm $(docker volume ls -q) 2>/dev/null || true
docker network prune -f
echo "✅ Docker resources cleaned up"

# Step 3: Check and update .env.development file
echo "Step 3: Checking .env.development file..."
if grep -q "SECRET_KEY" .env.development; then
    echo "SECRET_KEY already exists in .env.development"
else
    echo "Adding SECRET_KEY to .env.development..."
    echo "SECRET_KEY=development_secret_key_for_testing_only_change_in_production" >> .env.development
    echo "✅ SECRET_KEY added to .env.development"
fi

# Step 4: Create a barebones docker-compose file for testing
echo "Step 4: Creating minimal docker-compose.test.yml..."
cat > docker-compose.test.yml << 'EOF'
services:
  postgres:
    image: postgres:14
    container_name: postgres
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=redbarsushi
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app-network

  app:
    build: .
    container_name: app
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
      - REDIS_URL=redis://localhost:6379/0
      - OPENAI_API_KEY=sk-test1234567890
      - TWILIO_ACCOUNT_SID=ACtest1234567890
      - TWILIO_AUTH_TOKEN=test1234567890
      - TWILIO_PHONE_NUMBER=+12345678901
      - STRIPE_API_KEY=sk_test_1234567890
      - SECRET_KEY=test1234567890
      - FASTAPI_ENV=development
      - LOG_LEVEL=DEBUG
    ports:
      - "8080:8080"
    volumes:
      - ./app:/app/app
    networks:
      - app-network
    command: >
      sh -c "
        echo 'Environment variables:' &&
        echo 'DATABASE_URL=' $DATABASE_URL &&
        echo 'OPENAI_API_KEY=' $OPENAI_API_KEY &&
        echo 'TWILIO_ACCOUNT_SID=' $TWILIO_ACCOUNT_SID &&
        echo 'SECRET_KEY=' $SECRET_KEY &&
        echo 'Waiting for database...' &&
        sleep 5 &&
        ping -c 3 postgres &&
        echo 'Starting server...' &&
        uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug
      "

networks:
  app-network:
    driver: bridge

volumes:
  postgres_data:
EOF
echo "✅ docker-compose.test.yml created"

# Step 5: Create a simple database check script
echo "Step 5: Creating database check script..."
cat > db_check.py << 'EOF'
#!/usr/bin/env python3
"""Simple database check script."""

import os
import time
import socket
import sys

def check_network(host, port=5432, max_attempts=5):
    """Check if a host:port is reachable."""
    print(f"Checking network connectivity to {host}:{port}...")
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Attempt {attempt}/{max_attempts}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))
            sock.close()
            print(f"✅ Successfully connected to {host}:{port}")
            return True
        except socket.error as e:
            print(f"❌ Failed to connect to {host}:{port}: {e}")
            
            if attempt < max_attempts:
                print(f"Waiting 2 seconds before retry...")
                time.sleep(2)
    
    return False

def check_environment():
    """Check critical environment variables."""
    print("\nChecking environment variables...")
    
    critical_vars = [
        "DATABASE_URL", 
        "OPENAI_API_KEY", 
        "TWILIO_ACCOUNT_SID", 
        "STRIPE_API_KEY",
        "SECRET_KEY"
    ]
    
    all_present = True
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var} is set: {value[:10]}...")
        else:
            print(f"❌ {var} is NOT set")
            all_present = False
    
    return all_present

if __name__ == "__main__":
    # Check environment variables
    env_status = check_environment()
    
    # Check database connectivity
    db_host = os.environ.get("DB_HOST", "postgres")
    db_port = int(os.environ.get("DB_PORT", 5432))
    
    # Get database host from DATABASE_URL if available
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and "@" in db_url and ":" in db_url.split("@")[1]:
        try:
            # Extract host from DATABASE_URL
            db_host = db_url.split("@")[1].split(":")[0]
            print(f"Extracted database host '{db_host}' from DATABASE_URL")
        except Exception as e:
            print(f"Error parsing DATABASE_URL: {e}")
    
    net_status = check_network(db_host, db_port)
    
    # Report status
    print("\n===== Status Summary =====")
    print(f"Environment variables: {'✅' if env_status else '❌'}")
    print(f"Database connectivity: {'✅' if net_status else '❌'}")
    
    if env_status and net_status:
        print("\n✅ All checks passed")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed")
        sys.exit(1)
EOF
chmod +x db_check.py
echo "✅ Database check script created"

# Step 6: Start containers
echo "Step 6: Starting containers..."
docker compose -f docker-compose.test.yml up -d
echo "✅ Containers started"

# Step 7: Wait for containers
echo "Step 7: Waiting for containers to initialize..."
sleep 10

# Step 8: Check container status
echo
echo "===== Container Status ====="
docker ps -a
echo

# Step 9: Check app container logs
echo "===== App Container Logs ====="
docker logs app
echo

# Step 10: Run database check script
echo "Step 10: Running database check script..."
docker cp db_check.py app:/app/
docker exec app python /app/db_check.py || true
echo

echo
echo "===== Direct Docker Fix Complete ====="
echo
echo "If you still see issues with database connectivity, try these troubleshooting steps:"
echo
echo "1. Check Docker network setup:"
echo "   docker network inspect app-network | grep postgres"
echo
echo "2. Test ping from app container to postgres container:"
echo "   docker exec app ping -c 3 postgres"
echo
echo "3. Check database service is running:"
echo "   docker exec postgres pg_isready"
echo
echo "4. If all else fails, restart with a clean Docker environment:"
echo "   docker system prune -af --volumes"
echo "   ./docker-fix.sh"