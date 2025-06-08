#!/bin/bash
# Main test runner script for RedBarSushiAI

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 RedBarSushiAI Test Runner${NC}"
echo "=========================="

# Parse test type
TEST_TYPE=${1:-all}
shift || true

# Set environment variables for testing
export PYTHONPATH="/app:$PYTHONPATH"
export TESTING=true
export DATABASE_URL="postgresql+asyncpg://redbarsushi:redbarsushi@postgres-test:5432/redbarsushi_test"
export REDIS_URL="redis://redis-test:6379/0"

echo -e "${YELLOW}🔧 Environment configured for testing${NC}"
echo "Test Type: $TEST_TYPE"
echo "Database: $DATABASE_URL"
echo "Redis: $REDIS_URL"

# Wait for database to be ready
echo -e "${YELLOW}⏳ Waiting for database...${NC}"
until pg_isready -h postgres-test -p 5432 -U redbarsushi; do
    echo "Waiting for PostgreSQL to start..."
    sleep 1
done

echo -e "${YELLOW}⏳ Waiting for Redis...${NC}"
until redis-cli -h redis-test ping; do
    echo "Waiting for Redis to start..."
    sleep 1
done

echo -e "${GREEN}✅ Services are ready${NC}"

# Run tests based on type
case $TEST_TYPE in
    unit)
        echo -e "${BLUE}🧪 Running unit tests...${NC}"
        python -m pytest tests/unit/ -v --tb=short "$@"
        ;;
    integration)
        echo -e "${BLUE}🧪 Running integration tests...${NC}"
        python -m pytest tests/integration/ -v --tb=short "$@"
        ;;
    e2e)
        echo -e "${BLUE}🧪 Running E2E tests...${NC}"
        python -m pytest tests/e2e/ -v --tb=short "$@"
        ;;
    all)
        echo -e "${BLUE}🧪 Running all tests...${NC}"
        python -m pytest tests/ -v --tb=short "$@"
        ;;
    *)
        echo -e "${RED}❌ Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|integration|e2e|all] [additional pytest args]"
        exit 1
        ;;
esac

echo -e "${GREEN}✅ Tests completed${NC}"