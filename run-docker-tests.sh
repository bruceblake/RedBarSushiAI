#!/bin/bash
# Script to run tests using Docker Compose

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 RedBarSushiAI Docker Test Runner${NC}"
echo "==================================="

# Parse arguments
TEST_TYPE=${1:-all}
COMPOSE_FILE="docker-compose.test.yml"
COMPOSE_OVERRIDE=""
DOCKER_ARGS=""
KEEP_RUNNING=false

# Handle additional arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev|--development)
            COMPOSE_OVERRIDE="-f docker-compose.test.override.yml"
            shift
            ;;
        --keep-running|-k)
            KEEP_RUNNING=true
            shift
            ;;
        --build|-b)
            DOCKER_ARGS="--build"
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Function to cleanup containers
cleanup() {
    if [ "$KEEP_RUNNING" = "false" ]; then
        echo -e "${YELLOW}🧹 Cleaning up containers...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE down -v
    else
        echo -e "${YELLOW}📦 Keeping containers running for debugging${NC}"
        echo "Run 'docker-compose -f $COMPOSE_FILE down -v' to clean up"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    exit 1
fi

# Build and start services
echo -e "${YELLOW}🔨 Building test containers...${NC}"
docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE build $DOCKER_ARGS

echo -e "${YELLOW}🚀 Starting test services...${NC}"
docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE up -d postgres-test redis-test

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be healthy...${NC}"
timeout 60 bash -c 'until docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 1; done' || {
    echo -e "${RED}❌ Services failed to become healthy${NC}"
    docker-compose -f $COMPOSE_FILE logs
    exit 1
}

# Run tests based on type
case $TEST_TYPE in
    unit)
        echo -e "${BLUE}🧪 Running unit tests in Docker...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE run --rm app-test ./run-tests.sh unit "$@"
        ;;
    integration)
        echo -e "${BLUE}🧪 Running integration tests in Docker...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE run --rm app-test ./run-tests.sh integration "$@"
        ;;
    e2e)
        echo -e "${BLUE}🧪 Running E2E tests in Docker...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE run --rm app-test ./run-tests.sh e2e "$@"
        ;;
    all)
        echo -e "${BLUE}🧪 Running all tests in Docker...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE run --rm app-test ./run-tests.sh all "$@"
        ;;
    shell)
        echo -e "${BLUE}🐚 Starting test shell...${NC}"
        KEEP_RUNNING=true
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE run --rm app-test /bin/bash
        ;;
    logs)
        echo -e "${BLUE}📋 Showing test logs...${NC}"
        docker-compose -f $COMPOSE_FILE $COMPOSE_OVERRIDE logs -f
        ;;
    *)
        echo -e "${RED}❌ Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|integration|e2e|all|shell|logs] [options]"
        echo ""
        echo "Test Types:"
        echo "  unit         - Run unit tests"
        echo "  integration  - Run integration tests"
        echo "  e2e          - Run E2E tests"
        echo "  all          - Run all tests (default)"
        echo "  shell        - Start interactive shell in test container"
        echo "  logs         - Show test container logs"
        echo ""
        echo "Options:"
        echo "  --dev        - Use development override file"
        echo "  --keep-running - Keep containers running after tests"
        echo "  --build      - Force rebuild containers"
        exit 1
        ;;
esac

EXIT_CODE=$?

# Copy test results to host
if [ -d "test-results" ]; then
    echo -e "${YELLOW}📋 Copying test results...${NC}"
    docker cp $(docker-compose -f $COMPOSE_FILE ps -q app-test):/app/test-results ./test-results 2>/dev/null || true
    docker cp $(docker-compose -f $COMPOSE_FILE ps -q app-test):/app/coverage ./coverage 2>/dev/null || true
    docker cp $(docker-compose -f $COMPOSE_FILE ps -q app-test):/app/htmlcov ./htmlcov 2>/dev/null || true
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Docker tests completed successfully!${NC}"
else
    echo -e "${RED}❌ Docker tests failed with exit code $EXIT_CODE${NC}"
fi

exit $EXIT_CODE