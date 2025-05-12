#!/bin/bash
# Script to fix PostgreSQL authentication issues in Docker

set -e

echo "===== Fixing PostgreSQL Authentication Issues ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Cleaned up existing containers"

# Step 2: Clean up postgres volume to ensure fresh DB initialization
echo "Step 2: Removing PostgreSQL volume..."
docker volume rm postgres-dev-data 2>/dev/null || true
echo "✅ PostgreSQL volume removed"

# Step 3: Create .env.development.postgres with correct database credentials
echo "Step 3: Creating .env.development.postgres file..."
cat > .env.development.postgres << 'EOF'
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
EOF
echo "✅ .env.development.postgres file created"

# Step 4: Create postgres-init.sh script
echo "Step 4: Creating postgres initialization script..."
mkdir -p db/init
cat > db/init/postgres-init.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Beginning PostgreSQL initialization ==="

# Create user and database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL
  CREATE USER postgres WITH PASSWORD 'postgres' SUPERUSER;
  CREATE DATABASE redbarsushi;
  GRANT ALL PRIVILEGES ON DATABASE redbarsushi TO postgres;
EOSQL

echo "=== User and database created successfully ==="
echo "=== PostgreSQL initialization complete ==="
EOF
chmod +x db/init/postgres-init.sh
echo "✅ postgres-init.sh created and made executable"

# Step 5: Create a modified docker-compose file
echo "Step 5: Creating docker-compose.postgres-fixed.yml..."
cat > docker-compose.postgres-fixed.yml << 'EOF'
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
      - .env.development.postgres
    environment:
      - PYTHONUNBUFFERED=1
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
    command: ["/bin/bash", "-c", "cd /app && python fix_pydantic.py && echo '📦 Using Pydantic:' && pip show pydantic | grep Version && echo '🔍 Database credentials:' && echo 'DB_USER:' $DB_USER && echo 'DB_PASSWORD:' $DB_PASSWORD && echo 'DATABASE_URL:' $DATABASE_URL && sleep 3 && python check_db_enhanced.py && python init_db_improved.py && echo 'Starting server...' && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug"]

  postgres:
    image: postgres:14
    container_name: redbarsushi-postgres-dev
    env_file:
      - .env.development.postgres
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
echo "✅ docker-compose.postgres-fixed.yml created"

# Step 6: Create enhanced database check script
echo "Step 6: Creating enhanced database check script..."
cat > check_db_enhanced.py << 'EOF'
#!/usr/bin/env python3
"""Enhanced script to check database connection with detailed diagnostics."""

import os
import sys
import time
import socket
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

def check_environment_variables():
    """Check if necessary environment variables are set."""
    variables = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DATABASE_URL"
    ]
    
    logger.info("Checking environment variables...")
    all_set = True
    
    for var in variables:
        value = os.environ.get(var)
        if value:
            logger.info(f"✅ {var} is set: {value}")
        else:
            logger.error(f"❌ {var} is NOT set!")
            all_set = False
    
    return all_set

def check_db_connection():
    """Check if database connection works with detailed error handling."""
    logger.info("\nDatabase Connection Diagnostics:")
    logger.info("-" * 40)
    
    # Check environment variables first
    if not check_environment_variables():
        logger.error("❌ Some required environment variables are missing")
    
    # Check network connectivity
    if not check_network():
        logger.error("❌ Network connection to database server failed")
        return False
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    try:
        import psycopg2
        # Try connection
        logger.info("Attempting database connection...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        # Check connection
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        
        logger.info("\n✅ Connection successful!")
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
            logger.info("\nExisting tables:")
            for table in tables:
                logger.info(f"- {table[0]}")
        else:
            logger.warning("\n⚠️ No tables found in the database.")
        
        cursor.close()
        conn.close()
        
        return True
    except ImportError:
        logger.error("❌ psycopg2 module not found. Please install it with: pip install psycopg2-binary")
        return False
    except psycopg2.OperationalError as e:
        if "password authentication" in str(e):
            logger.error(f"\n❌ Password authentication failed: {e}")
            logger.error("\nDetailed troubleshooting:")
            logger.error(f"1. Using username: '{user}'")
            logger.error(f"2. Using password: '{'*' * len(password)}'")
            logger.error(f"3. Database name: '{dbname}'")
            logger.error(f"4. Host: '{host}'")
            logger.error(f"5. Port: '{port}'")
            logger.error("\nPossible solutions:")
            logger.error("- Ensure PostgreSQL environment variables are correctly set")
            logger.error("- Try running 'docker exec -it redbarsushi-postgres-dev psql -U postgres' to test login")
            logger.error("- Check if database initialization scripts ran successfully")
        elif "could not connect" in str(e) or "could not translate" in str(e):
            logger.error(f"\n❌ Connection error: {e}")
            logger.error("🔌 Ensure the postgres container is running and healthy")
            logger.error("🔌 Check network connectivity between containers")
        else:
            logger.error(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        return False

def retry_check_db(max_attempts=3, delay=5):
    """Retry the database connection check multiple times with delay."""
    for attempt in range(1, max_attempts + 1):
        logger.info(f"\nConnection attempt {attempt}/{max_attempts}...")
        
        if check_db_connection():
            logger.info(f"\n✅ Connection successful on attempt {attempt}")
            return True
            
        if attempt < max_attempts:
            logger.info(f"\n⏱️ Waiting {delay} seconds before next attempt...")
            time.sleep(delay)
            
    logger.error(f"\n❌ All {max_attempts} connection attempts failed")
    return False

if __name__ == "__main__":
    logger.info("Starting enhanced database connection check...")
    if retry_check_db():
        logger.info("\n✅ DATABASE CONNECTION CHECK: SUCCESS")
        sys.exit(0)
    else:
        logger.error("\n❌ DATABASE CONNECTION CHECK: FAILED")
        sys.exit(1)
EOF
chmod +x check_db_enhanced.py
echo "✅ check_db_enhanced.py created and made executable"

# Step 7: Create improved database initialization script
echo "Step 7: Creating improved database initialization script..."
cat > init_db_improved.py << 'EOF'
#!/usr/bin/env python3
"""Initialize database for RedBarSushiAI with improved error handling."""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def connect_with_retry(max_attempts=3, delay=5):
    """Attempt to connect to PostgreSQL with retries."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    logger.info(f"Connecting to PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    try:
        import psycopg2
    except ImportError:
        logger.error("❌ psycopg2 module not found. Please install it with: pip install psycopg2-binary")
        sys.exit(1)
    
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
echo "✅ init_db_improved.py created and made executable"

# Step 8: Create restart script
echo "Step 8: Creating restart script..."
cat > restart_docker_postgres_fixed.sh << 'EOF'
#!/bin/bash
# Script to restart Docker with fixed PostgreSQL configuration

set -e

echo "===== Starting RedBarSushiAI with Fixed PostgreSQL Configuration ====="

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

# Step 3: Starting the containers with fixed configuration
echo "Step 3: Starting the containers with fixed PostgreSQL configuration..."
docker compose -f docker-compose.postgres-fixed.yml up -d --build --force-recreate
echo "✅ Containers started"

# Step 4: Wait for PostgreSQL to be healthy
echo "Step 4: Waiting for PostgreSQL to be healthy..."
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

# Step 5: Check PostgreSQL status
echo "Step 5: Checking PostgreSQL status..."
if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
    echo "✅ PostgreSQL is healthy"
    
    # Test PostgreSQL access with docker exec
    echo "Testing PostgreSQL access directly..."
    docker exec -it redbarsushi-postgres-dev psql -U postgres -c "SELECT 1 as test" || echo "⚠️ Direct PostgreSQL access failed"
    
    # Check application container logs
    echo "App container logs (last 10 lines):"
    docker logs redbarsushi-app-dev --tail 10
    
    # Wait for application to try connecting
    echo "Waiting for application to attempt database connection..."
    sleep 5
    
    # Show database-related logs
    echo "Database-related logs from app container:"
    docker logs redbarsushi-app-dev | grep -i "database\|db\|postgres\|sql" | tail -20
else
    echo "⚠️ PostgreSQL container not healthy after waiting"
    echo "PostgreSQL container logs:"
    docker logs redbarsushi-postgres-dev --tail 20
fi

# Step 6: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Next Steps ====="
echo "1. Check container logs for detailed information:"
echo "   - View PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "   - View application logs: docker logs redbarsushi-app-dev"
echo "2. If issues persist, try restarting with clean volumes:"
echo "   ./restart_docker_postgres_fixed.sh --clean-volumes"
echo "3. Access the application at: http://localhost:8080"
echo
echo "===== Setup Complete ====="
EOF
chmod +x restart_docker_postgres_fixed.sh
echo "✅ restart_docker_postgres_fixed.sh created and made executable"

# Step 9: Run the restart script
echo "Step 9: Running the restart script..."
./restart_docker_postgres_fixed.sh --clean-volumes
echo "✅ Docker environment restarted with fixed PostgreSQL configuration"

echo
echo "===== PostgreSQL Fix Completed ====="
echo "The PostgreSQL authentication issue should now be fixed."
echo "If you still encounter issues, check the logs for more information."
echo "You can use these commands:"
echo "- View app logs: docker logs redbarsushi-app-dev"
echo "- View PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "- Restart with clean volumes: ./restart_docker_postgres_fixed.sh --clean-volumes"
echo
echo "For the OpenAI Realtime API fix, use the deploy_realtime_fix.sh script when ready."