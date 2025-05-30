#!/bin/bash

# Exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Source test environment if available
if [ -f "$PROJECT_ROOT/.env.test" ]; then
    source "$PROJECT_ROOT/.env.test"
fi

echo -e "${BLUE}🧪 Starting RedBarSushiAI Test Suite${NC}"
echo "===================================="

# Parse command line arguments
TEST_TYPE=${1:-all}
COVERAGE=${COVERAGE:-true}
VERBOSE=${VERBOSE:-true}
PARALLEL=${PARALLEL:-false}
MARKERS=""
EXTRA_ARGS=""

# Handle additional arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cov|--no-coverage)
            COVERAGE=false
            shift
            ;;
        --parallel|-n)
            PARALLEL=true
            shift
            ;;
        --quiet|-q)
            VERBOSE=false
            shift
            ;;
        --markers|-m)
            MARKERS="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# Use wait-for-services.sh if available
if [ -f "$PROJECT_ROOT/scripts/wait-for-services.sh" ]; then
    echo -e "${YELLOW}⏳ Checking service health...${NC}"
    if ! "$PROJECT_ROOT/scripts/wait-for-services.sh"; then
        echo -e "${RED}❌ Service health check failed${NC}"
        exit 1
    fi
else
    # Fallback to basic checks
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL...${NC}"
    for i in {1..30}; do
        if pg_isready -h postgres-test -U redbarsushi -d redbarsushi_test > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"
            break
        fi
        echo "   Attempt $i/30..."
        sleep 1
    done

    echo -e "${YELLOW}⏳ Waiting for Redis...${NC}"
    for i in {1..30}; do
        if redis-cli -h redis-test ping > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Redis is ready!${NC}"
            break
        fi
        echo "   Attempt $i/30..."
        sleep 1
    done
fi

# Clean test artifacts if requested
if [ -f "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" ]; then
    echo -e "${YELLOW}🧹 Cleaning test artifacts...${NC}"
    "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" prepare
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add verbose flag
if [ "$VERBOSE" = "true" ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add color
PYTEST_CMD="$PYTEST_CMD --color=yes"

# Add parallel execution
if [ "$PARALLEL" = "true" ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add coverage
if [ "$COVERAGE" = "true" ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml"
fi

# Add test result reporting
PYTEST_CMD="$PYTEST_CMD --junit-xml=test-results/junit.xml --html=test-results/report.html --self-contained-html"

# Add markers if specified
if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD -m \"$MARKERS\""
fi

# Add extra arguments
PYTEST_CMD="$PYTEST_CMD $EXTRA_ARGS"

# Run tests based on type

case $TEST_TYPE in
    unit)
        echo -e "${BLUE}🧪 Running unit tests...${NC}"
        SKIP_HEALTH_CHECK=true $PYTEST_CMD tests/unit/
        ;;
    integration)
        echo -e "${BLUE}🧪 Running integration tests...${NC}"
        $PYTEST_CMD tests/integration/
        ;;
    e2e)
        echo -e "${BLUE}🧪 Running E2E tests...${NC}"
        $PYTEST_CMD tests/e2e/
        ;;
    all)
        echo -e "${BLUE}🧪 Running all tests...${NC}"
        $PYTEST_CMD tests/
        ;;
    fast)
        echo -e "${BLUE}🧪 Running fast tests (unit + integration)...${NC}"
        $PYTEST_CMD tests/unit/ tests/integration/ -m "not slow"
        ;;
    smoke)
        echo -e "${BLUE}🧪 Running smoke tests...${NC}"
        $PYTEST_CMD tests/ -m "smoke" --maxfail=1
        ;;
    failed)
        echo -e "${BLUE}🧪 Re-running failed tests...${NC}"
        $PYTEST_CMD --lf
        ;;
    *)
        echo -e "${RED}❌ Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|integration|e2e|all|fast|smoke|failed] [options]"
        echo ""
        echo "Test Types:"
        echo "  unit         - Run unit tests only"
        echo "  integration  - Run integration tests only"
        echo "  e2e          - Run end-to-end tests only"
        echo "  all          - Run all tests (default)"
        echo "  fast         - Run fast tests (unit + integration, no slow)"
        echo "  smoke        - Run smoke tests only"
        echo "  failed       - Re-run only failed tests from last run"
        echo ""
        echo "Options:"
        echo "  --no-cov     - Disable coverage reporting"
        echo "  --parallel   - Run tests in parallel"
        echo "  --quiet      - Less verbose output"
        echo "  --markers    - Run tests matching specific markers"
        echo ""
        echo "Examples:"
        echo "  $0 unit --no-cov"
        echo "  $0 integration --parallel"
        echo "  $0 all --markers \"not slow\""
        exit 1
        ;;
esac

# Check exit code
EXIT_CODE=$?

# Generate coverage report summary if coverage was enabled
if [ "$COVERAGE" = "true" ] && [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${BLUE}📊 Coverage Summary:${NC}"
    coverage report --skip-covered --skip-empty 2>/dev/null || true
fi

# Show test results location
echo ""
if [ -f "test-results/report.html" ]; then
    echo -e "${GREEN}📄 Test report: test-results/report.html${NC}"
fi
if [ -f "htmlcov/index.html" ]; then
    echo -e "${GREEN}📊 Coverage report: htmlcov/index.html${NC}"
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Test suite completed successfully!${NC}"
else
    echo -e "${RED}❌ Test suite failed with exit code $EXIT_CODE${NC}"
fi

exit $EXIT_CODE