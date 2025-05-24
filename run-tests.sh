#!/bin/bash

# run-tests.sh - Run E2E tests for RedBarSushiAI
# This script runs tests against the Docker Compose stack

set -e  # Exit on error

echo "======================================"
echo "RedBarSushiAI E2E Test Runner"
echo "======================================"

# Check if Docker services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "ERROR: Docker services are not running!"
    echo "Please run ./docker-init.sh first"
    exit 1
fi

# Set test environment variables
export TESTING=true
export TEST_BASE_URL=http://localhost:8000
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/redbarsushi
export REDIS_URL=redis://localhost:6379/0

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Loading environment from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Create test results directory
mkdir -p test-results

echo "Running E2E tests..."
echo "Test URL: $TEST_BASE_URL"

# Run the tests inside the container with proper environment
docker-compose exec -T app pytest tests/e2e/ \
    -v \
    --tb=short \
    --junit-xml=/app/test-results/junit.xml \
    --html=/app/test-results/report.html \
    --self-contained-html \
    || TEST_FAILED=1

# Copy test results to host
docker cp redbarsushi-app:/app/test-results/. ./test-results/

if [ "$TEST_FAILED" = "1" ]; then
    echo ""
    echo "======================================"
    echo "❌ Some tests failed!"
    echo "======================================"
    echo "Check test-results/report.html for details"
    exit 1
else
    echo ""
    echo "======================================"
    echo "✅ All tests passed!"
    echo "======================================"
    echo "Test results saved to test-results/"
fi