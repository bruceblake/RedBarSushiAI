#!/bin/bash
# Direct fix for PostgreSQL user issue in Docker

set -e

echo "===== Direct Fix for PostgreSQL User Issue ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Containers stopped and removed"

# Step 2: Force removal of volumes
echo "Step 2: Removing volumes..."
docker volume rm postgres-data redis-data 2>/dev/null || true
echo "✅ Volumes removed"

# Step 3: Create init script directory
echo "Step 3: Creating PostgreSQL init script..."
mkdir -p pg_init
cat > pg_init/init-db.sh << 'EOF'
#!/bin/bash
set -e

echo "*** Creating database schema and users ***"

# Create database and roles
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL
  CREATE DATABASE redbarsushi;
  GRANT ALL PRIVILEGES ON DATABASE redbarsushi TO postgres;
EOSQL

# Connect to the redbarsushi database and create tables
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "redbarsushi" << EOSQL
  CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    plu VARCHAR(50) UNIQUE,
    is_available BOOLEAN DEFAULT TRUE
  );
  
  INSERT INTO menu_items (name, description, price, plu)
  VALUES 
    ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
    ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICYTUNA')
  ON CONFLICT (plu) DO NOTHING;
EOSQL

echo "*** Database initialization completed ***"
EOF
chmod +x pg_init/init-db.sh
echo "✅ PostgreSQL init script created"

# Step 4: Create docker-compose file
echo "Step 4: Creating docker-compose.direct.yml..."
cat > docker-compose.direct.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:14
    container_name: redbarsushi-postgres-dev
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    ports:
      - "5433:5432"
    volumes:
      - ./pg_init:/docker-entrypoint-initdb.d
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - redbarsushi-network
    restart: always

  redis:
    image: redis:6
    container_name: redbarsushi-redis-dev
    ports:
      - "6380:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - redbarsushi-network
    restart: always

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: redbarsushi-app-dev
    ports:
      - "8080:8080"
    environment:
      - PYTHONUNBUFFERED=1
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
      - DB_USER=postgres
      - DB_PASSWORD=postgres
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=redbarsushi
      - REDIS_URL=redis://redis:6379/0
      - TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
      - TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
      - TWILIO_PHONE_NUMBER=+17036467799
      - STRIPE_API_KEY=dummy-key-for-development
      - OPENAI_API_KEY=sk-mytestapikey
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    networks:
      - redbarsushi-network
    restart: always
    command: ["/bin/bash", "-c", "echo 'Waiting for database...' && sleep 10 && echo 'Starting server...' && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug"]

networks:
  redbarsushi-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
EOF
echo "✅ docker-compose.direct.yml created"

# Step 5: Start the database containers first
echo "Step 5: Starting PostgreSQL and Redis containers..."
docker compose -f docker-compose.direct.yml up -d postgres redis
echo "✅ PostgreSQL and Redis containers started"

# Step 6: Wait for PostgreSQL to be ready
echo "Step 6: Waiting for PostgreSQL to be healthy..."
attempts=0
max_attempts=30

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
        echo "✅ PostgreSQL is healthy"
        break
    fi
    
    echo "⏳ Waiting for PostgreSQL to be healthy... (${attempts}/${max_attempts})"
    sleep 2
done

# Step 7: Verify PostgreSQL is working
echo "Step 7: Verifying PostgreSQL connection..."
docker exec -it redbarsushi-postgres-dev psql -U postgres -c "SELECT 1 AS test" || {
    echo "❌ PostgreSQL connection failed"
    exit 1
}
echo "✅ PostgreSQL connection verified"

# Step 8: Check if the redbarsushi database exists
echo "Step 8: Checking if redbarsushi database exists..."
docker exec -it redbarsushi-postgres-dev psql -U postgres -c "\l" | grep -q "redbarsushi" && {
    echo "✅ redbarsushi database exists"
} || {
    echo "⚠️ redbarsushi database not found, the initialization script may have failed"
    exit 1
}

# Step 9: Start the app container
echo "Step 9: Starting app container..."
docker compose -f docker-compose.direct.yml up -d app
echo "✅ App container started"

# Step 10: Print status
echo
echo "===== Docker Environment Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== PostgreSQL Fix Completed ====="
echo "Your Docker environment should now be running with the correct PostgreSQL configuration."
echo
echo "The application should be available at: http://localhost:8080"
echo
echo "To verify the database connection, you can run:"
echo "docker exec -it redbarsushi-app-dev python -c \"import psycopg2; print('Connected successfully' if psycopg2.connect(dbname='redbarsushi', user='postgres', password='postgres', host='postgres') else 'Failed to connect')\""
echo
echo "To view logs:"
echo "- App logs: docker logs redbarsushi-app-dev"
echo "- PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "- Redis logs: docker logs redbarsushi-redis-dev"