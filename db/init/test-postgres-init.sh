#!/bin/bash
# PostgreSQL initialization script for test database
# This script runs when the test PostgreSQL container starts

set -e

# Function to log messages
log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting test database initialization..."

# Wait for PostgreSQL to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
  log_message "PostgreSQL is unavailable - sleeping"
  sleep 1
done

log_message "PostgreSQL is ready - executing initialization scripts"

# Execute SQL files in order
for sql_file in /docker-entrypoint-initdb.d/*.sql; do
    if [ -f "$sql_file" ]; then
        log_message "Executing $sql_file"
        PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$sql_file"
    fi
done

# Create additional test utilities
PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Create test helper procedures
    
    -- Procedure to snapshot current data
    CREATE OR REPLACE PROCEDURE create_test_snapshot(snapshot_name VARCHAR)
    LANGUAGE plpgsql
    AS \$\$
    BEGIN
        -- Create snapshot tables
        EXECUTE format('CREATE TABLE menu_items_%s AS SELECT * FROM menu_items', snapshot_name);
        EXECUTE format('CREATE TABLE orders_%s AS SELECT * FROM orders', snapshot_name);
        EXECUTE format('CREATE TABLE conversation_sessions_%s AS SELECT * FROM conversation_sessions', snapshot_name);
        
        RAISE NOTICE 'Test snapshot % created', snapshot_name;
    END;
    \$\$;
    
    -- Procedure to restore from snapshot
    CREATE OR REPLACE PROCEDURE restore_test_snapshot(snapshot_name VARCHAR)
    LANGUAGE plpgsql
    AS \$\$
    BEGIN
        -- Clear current data
        PERFORM reset_test_data();
        
        -- Restore from snapshot
        EXECUTE format('INSERT INTO menu_items SELECT * FROM menu_items_%s', snapshot_name);
        EXECUTE format('INSERT INTO orders SELECT * FROM orders_%s', snapshot_name);
        EXECUTE format('INSERT INTO conversation_sessions SELECT * FROM conversation_sessions_%s', snapshot_name);
        
        RAISE NOTICE 'Test snapshot % restored', snapshot_name;
    END;
    \$\$;
    
    -- Function to check database health
    CREATE OR REPLACE FUNCTION check_database_health()
    RETURNS TABLE(
        check_name VARCHAR,
        status VARCHAR,
        details TEXT
    )
    LANGUAGE plpgsql
    AS \$\$
    BEGIN
        -- Check table existence
        RETURN QUERY
        SELECT 
            'Tables exist'::VARCHAR,
            CASE 
                WHEN COUNT(*) >= 10 THEN 'PASS'::VARCHAR
                ELSE 'FAIL'::VARCHAR
            END,
            'Found ' || COUNT(*) || ' tables'::TEXT
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        
        -- Check for test data
        RETURN QUERY
        SELECT 
            'Test data loaded'::VARCHAR,
            CASE 
                WHEN COUNT(*) > 0 THEN 'PASS'::VARCHAR
                ELSE 'FAIL'::VARCHAR
            END,
            'Found ' || COUNT(*) || ' menu items'::TEXT
        FROM menu_items;
        
        -- Check indexes
        RETURN QUERY
        SELECT 
            'Indexes created'::VARCHAR,
            CASE 
                WHEN COUNT(*) >= 5 THEN 'PASS'::VARCHAR
                ELSE 'FAIL'::VARCHAR
            END,
            'Found ' || COUNT(*) || ' indexes'::TEXT
        FROM pg_indexes
        WHERE schemaname = 'public';
        
        -- Check functions
        RETURN QUERY
        SELECT 
            'Functions created'::VARCHAR,
            CASE 
                WHEN COUNT(*) >= 3 THEN 'PASS'::VARCHAR
                ELSE 'FAIL'::VARCHAR
            END,
            'Found ' || COUNT(*) || ' functions'::TEXT
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public';
    END;
    \$\$;
    
    -- Run health check
    SELECT * FROM check_database_health();
EOSQL

# Set up permissions
PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Grant permissions to test user
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON SCHEMA public TO $POSTGRES_USER;
    
    -- Enable query logging for tests
    ALTER DATABASE $POSTGRES_DB SET log_statement = 'all';
    ALTER DATABASE $POSTGRES_DB SET log_duration = on;
EOSQL

# Create marker file to indicate successful initialization
touch /var/lib/postgresql/data/.initialized

log_message "Test database initialization completed successfully"

# Output summary
PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM test_statistics;"