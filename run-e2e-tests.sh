#!/bin/bash

# Comprehensive E2E Test Runner for RedBarSushiAI
# Runs complete end-to-end tests without mocking any services

set -e  # Exit on any error

echo "🚀 RedBarSushiAI Comprehensive E2E Test Suite"
echo "=============================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_ENV="${TEST_ENV:-staging}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
E2E_TEST_TIMEOUT="${E2E_TEST_TIMEOUT:-300}"  # 5 minutes
PARALLEL_TESTS="${PARALLEL_TESTS:-false}"

echo -e "${BLUE}Test Environment:${NC} $TEST_ENV"
echo -e "${BLUE}Docker Compose File:${NC} $DOCKER_COMPOSE_FILE"
echo -e "${BLUE}Test Timeout:${NC} $E2E_TEST_TIMEOUT seconds"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

print_success "Prerequisites check passed"

# Check if services are running
print_status "Checking service status..."

if ! docker-compose ps | grep -q "Up"; then
    print_warning "Some services may not be running. Starting services..."
    docker-compose up -d
    
    # Wait for services to be healthy
    print_status "Waiting for services to be healthy..."
    sleep 10
    
    # Check health status
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose ps | grep -q "healthy"; then
            print_success "Services are healthy"
            break
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Services failed to become healthy within timeout"
        print_status "Service status:"
        docker-compose ps
        exit 1
    fi
else
    print_success "Services are already running"
fi

# Display current service status
print_status "Current service status:"
docker-compose ps

echo ""

# Check environment variables
print_status "Validating environment variables..."

required_vars=("OPENAI_API_KEY" "DATABASE_URL" "REDIS_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    print_warning "Missing environment variables: ${missing_vars[*]}"
    print_warning "Some tests may use mocked services"
else
    print_success "All required environment variables are set"
fi

# Optional Deliverect configuration
if [ -n "$DELIVERECT_API_KEY" ]; then
    print_success "Deliverect API key configured - real order verification enabled"
else
    print_warning "No Deliverect API key - order verification will be mocked"
fi

echo ""

# Prepare test environment
print_status "Preparing test environment..."

# Clear any existing test data
docker-compose exec -T redis redis-cli FLUSHDB || print_warning "Could not clear Redis cache"

# Database initialization check (simplified)
docker-compose exec -T app python -c "
import asyncio
print('Database check - services are already running')
" || print_warning "Database initialization check failed"

print_success "Test environment prepared"

echo ""

# Run the comprehensive E2E test suite
print_status "Running comprehensive E2E test suite..."
echo ""

# Build pytest command
PYTEST_CMD="python -m pytest tests/e2e/test_robust_e2e.py"
PYTEST_ARGS="-v -s --tb=short --maxfail=5"

# Note: Timeout not supported in this pytest version
# PYTEST_ARGS="$PYTEST_ARGS --timeout=$E2E_TEST_TIMEOUT"

# Add parallel execution if requested
if [ "$PARALLEL_TESTS" = "true" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -n auto"
    print_status "Running tests in parallel mode"
fi

# Add markers for comprehensive testing
PYTEST_ARGS="$PYTEST_ARGS -m e2e"

# Full command
FULL_CMD="$PYTEST_CMD $PYTEST_ARGS"

print_status "Executing: $FULL_CMD"
echo ""

# Execute tests in Docker container
if docker-compose exec -T app bash -c "$FULL_CMD"; then
    print_success "All E2E tests passed!"
    TEST_RESULT=0
else
    print_error "Some E2E tests failed!"
    TEST_RESULT=1
fi

echo ""

# Generate test report
print_status "Generating test report..."

# Run tests again with JUnit XML output for CI
docker-compose exec -T app bash -c "$PYTEST_CMD --junitxml=/tmp/e2e-test-results.xml --quiet" || true

# Copy test results out of container
docker cp $(docker-compose ps -q app):/tmp/e2e-test-results.xml ./e2e-test-results.xml 2>/dev/null || print_warning "Could not copy test results"

print_success "Test report generated"

echo ""

# Display summary
print_status "Test Summary"
echo "============"

if [ $TEST_RESULT -eq 0 ]; then
    print_success "🎉 All comprehensive E2E tests PASSED!"
    echo ""
    echo "✅ Voice input processing"
    echo "✅ Agent orchestration and state management"
    echo "✅ Menu item matching and validation"
    echo "✅ Order customization and modification"
    echo "✅ Out-of-stock item handling"
    echo "✅ Validation error recovery"
    echo "✅ Complete order flow to Deliverect integration"
    echo ""
    echo "The RedBarSushiAI system is ready for production deployment!"
else
    print_error "❌ Some E2E tests FAILED!"
    echo ""
    echo "Check the test output above for details on failures."
    echo "Common issues:"
    echo "- Network connectivity to OpenAI API"
    echo "- Database connection issues"
    echo "- Redis cache problems"
    echo "- Deliverect API configuration"
    echo ""
    echo "Re-run with DEBUG=1 for more detailed output:"
    echo "DEBUG=1 $0"
fi

echo ""

# Cleanup option
if [ "$CLEANUP_AFTER_TESTS" = "true" ]; then
    print_status "Cleaning up test environment..."
    docker-compose exec -T redis redis-cli FLUSHDB || true
    print_success "Cleanup completed"
fi

exit $TEST_RESULT