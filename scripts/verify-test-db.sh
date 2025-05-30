#!/bin/bash
# Script to verify test database setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Load test environment
if [ -f "$PROJECT_ROOT/.env.test" ]; then
    source "$PROJECT_ROOT/.env.test"
else
    print_error "Test environment file not found"
    exit 1
fi

# Extract database connection details
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*\/\/[^:]*:\([^@]*\)@.*/\1/p')

print_info "Verifying test database setup..."
print_info "Database: $DB_NAME on $DB_HOST:$DB_PORT"

# Function to run SQL query
run_query() {
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "$1" 2>/dev/null
}

# Check database connection
print_info "Checking database connection..."
if run_query "SELECT 1" > /dev/null; then
    print_info "✓ Database connection successful"
else
    print_error "✗ Failed to connect to database"
    exit 1
fi

# Check tables
print_info "Checking database tables..."
table_count=$(run_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
if [ $table_count -gt 0 ]; then
    print_info "✓ Found $table_count tables"
    
    # List tables
    echo "Tables:"
    run_query "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name" | sed 's/^/  - /'
else
    print_error "✗ No tables found"
fi

# Check test data
print_info "Checking test data..."
if [ $table_count -gt 0 ]; then
    item_count=$(run_query "SELECT COUNT(*) FROM menu_items" 2>/dev/null || echo "0")
    category_count=$(run_query "SELECT COUNT(*) FROM menu_categories" 2>/dev/null || echo "0")
    location_count=$(run_query "SELECT COUNT(*) FROM locations" 2>/dev/null || echo "0")
    
    print_info "Data summary:"
    echo "  - Menu Categories: $category_count"
    echo "  - Menu Items: $item_count"
    echo "  - Locations: $location_count"
    
    if [ $item_count -gt 0 ]; then
        print_info "✓ Test data is loaded"
    else
        print_warn "⚠ No test data found"
    fi
fi

# Check functions
print_info "Checking database functions..."
func_count=$(run_query "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public'")
if [ $func_count -gt 0 ]; then
    print_info "✓ Found $func_count functions"
    
    # List functions
    echo "Functions:"
    run_query "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public' ORDER BY proname" | sed 's/^/  - /'
else
    print_warn "⚠ No custom functions found"
fi

# Check indexes
print_info "Checking database indexes..."
index_count=$(run_query "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public'")
if [ $index_count -gt 0 ]; then
    print_info "✓ Found $index_count indexes"
else
    print_warn "⚠ No indexes found"
fi

# Run health check if available
print_info "Running database health check..."
if run_query "SELECT 1 FROM pg_proc WHERE proname = 'check_database_health'" > /dev/null; then
    echo "Health check results:"
    run_query "SELECT * FROM check_database_health()" | column -t -s '|'
else
    print_warn "⚠ Health check function not available"
fi

# Test reset function
print_info "Testing reset function..."
if run_query "SELECT 1 FROM pg_proc WHERE proname = 'reset_test_data'" > /dev/null; then
    print_info "✓ Reset function available"
else
    print_warn "⚠ Reset function not available"
fi

print_info "Database verification complete!"