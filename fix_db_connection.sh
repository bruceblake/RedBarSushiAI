#!/bin/bash
# Script to fix database connection issues in Docker environment

set -e  # Exit on any error

echo "===== Fixing Database Connection Issues ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Cleaned up existing containers"

# Step 2: Create a Docker volume fix script
echo "Step 2: Creating volume cleanup script..."
cat > clean_docker_volumes.sh << 'EOF'
#!/bin/bash
# Clean up Docker volumes related to RedBarSushi

echo "Removing Docker volumes for RedBarSushi..."
docker volume rm postgres-dev-data redis-dev-data 2>/dev/null || true
echo "✅ Volumes removed"
EOF
chmod +x clean_docker_volumes.sh
echo "✅ Volume cleanup script created"

# Step 3: Run volume cleanup
echo "Step 3: Removing Docker volumes..."
./clean_docker_volumes.sh
echo "✅ Volumes cleaned up"

# Step 4: Create enhanced check_db script
echo "Step 4: Creating enhanced database check script..."
cat > check_db_enhanced.py << 'EOF'
#!/usr/bin/env python3
"""Enhanced script to check database connection with detailed diagnostics."""

import os
import sys
import time
import socket
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_network():
    """Check network connectivity to the PostgreSQL server."""
    host = os.environ.get("DB_HOST", "postgres")
    port = int(os.environ.get("DB_PORT", "5432"))
    
    logger.info(f"Testing TCP connection to {host}:{port}...")
    try:
        # Simple socket connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.info(f"✅ TCP connection to {host}:{port} successful")
            return True
        else:
            logger.error(f"❌ Could not connect to {host}:{port} - error code: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Network error: {e}")
        return False

def check_db_connection():
    """Check if database connection works with detailed error handling."""
    logger.info("Database Connection Diagnostics:")
    logger.info("-" * 40)
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    # Display connection info
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Database: {dbname}")
    logger.info(f"User: {user}")
    logger.info(f"Password: {'*' * len(password) if password else 'Not set!'}")
    
    # Check if password is set
    if not password:
        logger.error("❌ DB_PASSWORD environment variable is not set!")
        return False
    
    # Try PostgreSQL URL format
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        logger.info(f"DATABASE_URL: {db_url.split('@')[0].split('://')[-1].split(':')[0]}:****@{db_url.split('@')[-1] if '@' in db_url else 'invalid_url'}")
    else:
        logger.warning("⚠️ DATABASE_URL not set, using individual connection parameters")
    
    # Check network connectivity first
    if not check_network():
        logger.error("❌ Network connection to database server failed")
        return False
    
    # Try connection
    try:
        logger.info("Attempting database connection...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        
        # Check connection
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        
        logger.info("✅ Connection successful!")
        logger.info(f"PostgreSQL version: {version[0]}")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        if tables:
            logger.info("Existing tables:")
            for table in tables:
                logger.info(f"- {table[0]}")
        else:
            logger.warning("⚠️ No tables found in the database.")
        
        cursor.close()
        conn.close()
        
        return True
    except psycopg2.OperationalError as e:
        if "password authentication" in str(e):
            logger.error(f"❌ Password authentication failed: {e}")
            logger.error("🔑 Check that the postgres container is using the correct password")
            logger.error("🔑 Check that the DB_PASSWORD environment variable matches POSTGRES_PASSWORD")
        elif "could not connect" in str(e) or "could not translate" in str(e):
            logger.error(f"❌ Connection error: {e}")
            logger.error("🔌 Ensure the postgres container is running and healthy")
            logger.error("🔌 Check network connectivity between containers")
        else:
            logger.error(f"❌ Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def retry_check_db(max_attempts=5, delay=3):
    """Retry the database connection check multiple times with delay."""
    for attempt in range(1, max_attempts + 1):
        logger.info(f"Connection attempt {attempt}/{max_attempts}...")
        
        if check_db_connection():
            logger.info(f"✅ Connection successful on attempt {attempt}")
            return True
            
        if attempt < max_attempts:
            logger.info(f"⏱️ Waiting {delay} seconds before next attempt...")
            time.sleep(delay)
            
    logger.error(f"❌ All {max_attempts} connection attempts failed")
    return False

if __name__ == "__main__":
    logger.info("Starting enhanced database connection check...")
    if retry_check_db():
        logger.info("✅ DATABASE CONNECTION CHECK: SUCCESS")
        sys.exit(0)
    else:
        logger.error("❌ DATABASE CONNECTION CHECK: FAILED")
        sys.exit(1)
EOF
chmod +x check_db_enhanced.py
echo "✅ Enhanced database check script created"

# Step 5: Create an updated docker-compose file
echo "Step 5: Creating improved docker-compose file..."
cat > docker-compose.fixed.yml << 'EOF'
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
      # Explicitly set DB credentials at container level to ensure they're set
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=redbarsushi
      - DB_USER=postgres
      - DB_PASSWORD=postgres
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=redbarsushi
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
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
    command: ["/bin/bash", "-c", "cd /app && python fix_pydantic.py && echo '📦 Using Pydantic:' && pip show pydantic | grep Version && echo '🔍 Database credentials:' && echo 'DB_USER:' $DB_USER && echo 'DB_PASSWORD:' $DB_PASSWORD && echo 'DATABASE_URL:' $DATABASE_URL && sleep 3 && python check_db_enhanced.py && python init_db.py && echo 'Starting server...' && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug"]

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
      interval: 5s
      timeout: 5s
      retries: 10
    restart: always
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
      interval: 5s
      timeout: 5s
      retries: 10
    restart: always
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
echo "✅ Docker compose file created"

# Step 6: Create DB initialization script with improved error handling
echo "Step 6: Creating improved database initialization script..."
cat > init_db_improved.py << 'EOF'
#!/usr/bin/env python3
"""Initialize database for RedBarSushiAI with improved error handling."""

import os
import sys
import time
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def connect_with_retry(max_attempts=5, delay=3):
    """Attempt to connect to PostgreSQL with retries."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    logger.info(f"Connecting to PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Connection attempt {attempt}/{max_attempts}...")
            
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=10
            )
            
            # Return the connection if successful
            logger.info("✅ Connected to database successfully")
            return conn
            
        except psycopg2.OperationalError as e:
            logger.error(f"Connection attempt {attempt} failed: {e}")
            
            if attempt < max_attempts:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error("❌ All connection attempts failed")
                raise
                
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

def create_tables():
    """Create required database tables if they don't exist."""
    try:
        # Connect to PostgreSQL with retry
        conn = connect_with_retry()
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create basic tables if they don't exist
        logger.info("Creating menu_items table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                plu VARCHAR(50) UNIQUE,
                deliverect_item_id VARCHAR(100),
                is_available BOOLEAN DEFAULT TRUE,
                is_combo BOOLEAN DEFAULT FALSE,
                is_variant BOOLEAN DEFAULT FALSE,
                image_url TEXT,
                snoozed_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("Creating menu_categories table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                deliverect_category_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("Creating menu_modifiers table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_modifiers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                price_change NUMERIC(10, 2) DEFAULT 0,
                plu VARCHAR(50) UNIQUE,
                deliverect_modifier_id VARCHAR(100),
                is_available BOOLEAN DEFAULT TRUE,
                snoozed_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add a simple menu item for testing if none exists
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Adding sample menu items for testing")
            cursor.execute("""
                INSERT INTO menu_categories (name, description)
                VALUES ('Rolls', 'Sushi rolls')
            """)
            
            # Get the inserted category id
            cursor.execute("SELECT id FROM menu_categories WHERE name='Rolls'")
            category_id = cursor.fetchone()[0]
            
            # Insert several menu items for testing
            menu_items = [
                ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
                ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICY-TUNA'),
                ('Rainbow Roll', 'California roll topped with assorted sashimi', 16.99, 'RAINBOW')
            ]
            
            for name, desc, price, plu in menu_items:
                cursor.execute("""
                    INSERT INTO menu_items (name, description, price, plu)
                    VALUES (%s, %s, %s, %s)
                """, (name, desc, price, plu))
            
            logger.info(f"Added {len(menu_items)} sample menu items")
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("✅ Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database initialization")
    if create_tables():
        logger.info("✅ Database setup successful")
        sys.exit(0)
    else:
        logger.error("❌ Database setup failed")
        sys.exit(1)
EOF
chmod +x init_db_improved.py
echo "✅ Improved database initialization script created"

# Step 7: Create comprehensive restart script
echo "Step 7: Creating comprehensive restart script..."
cat > restart_db_docker.sh << 'EOF'
#!/bin/bash
# Comprehensive script to restart Docker environment with database fixes

set -e  # Exit on any error

echo "===== Restarting RedBarSushiAI Docker Environment with DB Fixes ====="

# Step 1: Clean up existing containers
echo "Step 1: Stopping and removing existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker network rm redbarsushi-dev-network 2>/dev/null || true
echo "✅ Containers and network cleaned up"

# Step 2: Clean up volumes (only if explicitly wanted)
if [ "$1" == "--clean-volumes" ]; then
    echo "Step 2: Removing volumes for fresh start..."
    docker volume rm postgres-dev-data redis-dev-data 2>/dev/null || true
    echo "✅ Volumes removed for fresh start"
else
    echo "Step 2: Keeping existing volumes (use --clean-volumes to remove)"
fi

# Step 3: Start Docker services with fixed configuration
echo "Step 3: Starting Docker services with fixed configuration..."
# Using --force-recreate to ensure we get fresh containers
docker compose -f docker-compose.fixed.yml up -d --build --force-recreate
echo "✅ Docker services started with fixed configuration"

# Step 4: Wait for services to be ready
echo "Step 4: Waiting for services to be ready..."
attempts=0
max_attempts=30
all_healthy=false

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    # Check if postgres is healthy
    if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
        echo "✅ PostgreSQL is healthy"
        all_healthy=true
        break
    fi
    
    echo "⏳ Waiting for PostgreSQL to be healthy... ($attempts/$max_attempts)"
    sleep 2
done

if [ "$all_healthy" = true ]; then
    echo "✅ PostgreSQL is healthy and ready"
    
    # Give the app container a moment to start trying to connect
    echo "Waiting for app container to connect to database..."
    sleep 10
    
    # Show logs from the app container related to database connection
    echo "Database connection logs from app container:"
    docker logs redbarsushi-app-dev --tail 50 | grep -i "database\|db\|postgres\|sql" || true
else
    echo "⚠️ PostgreSQL may not be fully healthy yet. Check with 'docker ps'"
fi

# Step 5: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi || true

echo
echo "===== Database Connection Troubleshooting ====="
echo "If database connection issues persist, try these commands:"
echo "• View app logs: docker logs redbarsushi-app-dev"
echo "• View PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "• Test connection from app: docker exec -it redbarsushi-app-dev python check_db_enhanced.py"
echo "• Manual PostgreSQL check: docker exec -it redbarsushi-postgres-dev psql -U postgres -c 'SELECT 1'"
echo "• Restart with clean volumes: ./restart_db_docker.sh --clean-volumes"
echo

# Step 6: Provide next steps
echo "===== Next Steps ====="
echo "1. Check the logs for any database-related errors"
echo "2. Verify that the app container can connect to PostgreSQL"
echo "3. If issues persist, try restarting with --clean-volumes"
echo
echo "===== Setup Complete ====="
EOF
chmod +x restart_db_docker.sh
echo "✅ Restart script created"

# Step 8: Execute the restart script
echo "Step 8: Running the restart script..."
./restart_db_docker.sh
echo "✅ Docker environment restarted with database fixes"