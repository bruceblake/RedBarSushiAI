#!/bin/bash
# Script to wait for all test services to be healthy before running tests

set -e

# Configuration
MAX_WAIT_TIME=60  # Maximum time to wait for services (seconds)
CHECK_INTERVAL=2  # Time between checks (seconds)

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service configurations
POSTGRES_HOST="${POSTGRES_HOST:-postgres-test}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-redbarsushi}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-redbarsushi}"
POSTGRES_DB="${POSTGRES_DB:-redbarsushi_test}"

REDIS_HOST="${REDIS_HOST:-redis-test}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Output functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

# Progress spinner
spin() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Check PostgreSQL
check_postgres() {
    PGPASSWORD=$POSTGRES_PASSWORD pg_isready \
        -h $POSTGRES_HOST \
        -p $POSTGRES_PORT \
        -U $POSTGRES_USER \
        -d $POSTGRES_DB \
        -t 1 \
        >/dev/null 2>&1
}

# Check PostgreSQL schema
check_postgres_schema() {
    PGPASSWORD=$POSTGRES_PASSWORD psql \
        -h $POSTGRES_HOST \
        -p $POSTGRES_PORT \
        -U $POSTGRES_USER \
        -d $POSTGRES_DB \
        -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" \
        >/dev/null 2>&1
}

# Check Redis
check_redis() {
    redis-cli -h $REDIS_HOST -p $REDIS_PORT ping >/dev/null 2>&1
}

# Check Redis memory
check_redis_memory() {
    local used_memory=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    if [ ! -z "$used_memory" ]; then
        return 0
    else
        return 1
    fi
}

# Wait for a service with timeout
wait_for_service() {
    local service_name=$1
    local check_function=$2
    local start_time=$(date +%s)
    
    print_info "Waiting for $service_name..."
    
    while true; do
        if $check_function; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            print_success "$service_name is ready (${duration}s)"
            return 0
        fi
        
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -ge $MAX_WAIT_TIME ]; then
            print_error "$service_name failed to become ready within ${MAX_WAIT_TIME}s"
            return 1
        fi
        
        sleep $CHECK_INTERVAL
    done
}

# Run comprehensive health checks
run_health_checks() {
    print_info "Running comprehensive health checks..."
    
    # PostgreSQL detailed checks
    if check_postgres; then
        # Check database exists
        if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -lqt | cut -d \| -f 1 | grep -qw $POSTGRES_DB; then
            print_success "PostgreSQL database '$POSTGRES_DB' exists"
        else
            print_error "PostgreSQL database '$POSTGRES_DB' not found"
            return 1
        fi
        
        # Check tables exist
        local table_count=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'" 2>/dev/null || echo "0")
        table_count=$(echo $table_count | tr -d ' ')
        
        if [ "$table_count" -gt "0" ]; then
            print_success "PostgreSQL has $table_count tables"
        else
            print_warn "PostgreSQL has no tables - will be created on first run"
        fi
        
        # Check test data
        local item_count=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM menu_items" 2>/dev/null || echo "0")
        item_count=$(echo $item_count | tr -d ' ')
        
        if [ "$item_count" -gt "0" ]; then
            print_success "PostgreSQL has $item_count menu items"
        else
            print_warn "PostgreSQL has no test data - will be loaded on first run"
        fi
    fi
    
    # Redis detailed checks
    if check_redis; then
        # Check Redis version
        local redis_version=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO server | grep redis_version | cut -d: -f2 | tr -d '\r')
        print_success "Redis version: $redis_version"
        
        # Check Redis memory
        local used_memory=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        print_success "Redis memory usage: $used_memory"
        
        # Test Redis operations
        if redis-cli -h $REDIS_HOST -p $REDIS_PORT SET test_key "test_value" EX 10 >/dev/null 2>&1; then
            if [ "$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET test_key 2>/dev/null)" = "test_value" ]; then
                print_success "Redis read/write operations working"
                redis-cli -h $REDIS_HOST -p $REDIS_PORT DEL test_key >/dev/null 2>&1
            fi
        fi
    fi
    
    return 0
}

# Main execution
main() {
    echo "================================================"
    echo "   Test Services Health Check"
    echo "================================================"
    echo ""
    
    local start_time=$(date +%s)
    local all_services_ready=true
    
    # Check PostgreSQL
    if ! wait_for_service "PostgreSQL" check_postgres; then
        all_services_ready=false
    fi
    
    # Check PostgreSQL schema (if PostgreSQL is ready)
    if $all_services_ready && ! wait_for_service "PostgreSQL Schema" check_postgres_schema; then
        print_warn "PostgreSQL schema not ready - will be created on first run"
    fi
    
    # Check Redis
    if ! wait_for_service "Redis" check_redis; then
        all_services_ready=false
    fi
    
    # If all basic services are ready, run detailed health checks
    if $all_services_ready; then
        echo ""
        run_health_checks
        echo ""
        
        local end_time=$(date +%s)
        local total_duration=$((end_time - start_time))
        
        print_success "All services are healthy! (Total time: ${total_duration}s)"
        echo "================================================"
        exit 0
    else
        echo ""
        print_error "Some services failed to become ready"
        echo "================================================"
        
        # Provide debugging information
        echo ""
        echo "Debugging information:"
        echo "  PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT"
        echo "  Redis: $REDIS_HOST:$REDIS_PORT"
        echo ""
        echo "To check service logs:"
        echo "  docker logs redbarsushiai-postgres-test-1"
        echo "  docker logs redbarsushiai-redis-test-1"
        echo ""
        
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    "--quick")
        # Quick mode - just check basic connectivity
        MAX_WAIT_TIME=10
        ;;
    "--extended")
        # Extended mode - wait longer
        MAX_WAIT_TIME=120
        ;;
    "--help")
        echo "Usage: $0 [--quick|--extended]"
        echo ""
        echo "Options:"
        echo "  --quick    Quick check with 10s timeout"
        echo "  --extended Extended check with 120s timeout"
        echo "  --help     Show this help message"
        exit 0
        ;;
esac

# Run main function
main