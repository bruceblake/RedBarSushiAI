#!/bin/bash

# Advanced E2E Test Runner for RedBarSushiAI
# Runs production-ready quality assurance tests that push system boundaries

set -e

echo "=================================================="
echo "RedBarSushiAI Advanced E2E Test Suite"
echo "Testing conversational AI, stress, and security"
echo "=================================================="

# Check if Docker containers are running
if ! docker ps | grep -q "redbarsushi-app"; then
    echo "Error: RedBarSushiAI Docker containers are not running!"
    echo "Please start the containers first with: docker-compose up -d"
    exit 1
fi

echo "✓ Docker containers are running"

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

# Check if services are healthy
echo "Checking service health..."
curl -f http://localhost:8000/menu/items > /dev/null 2>&1 || {
    echo "Error: API service is not responding!"
    exit 1
}

echo "✓ Services are healthy"

# Run the advanced test suite
echo ""
echo "Running Advanced E2E Tests..."
echo "================================"

# Test categories to run
CATEGORIES=(
    "TestCategory5ComplexConversationalFluidity"
    "TestCategory6StressLoadAndConcurrency"  
    "TestCategory7IntegrationFailureAndResiliency"
    "TestCategory8SecurityAndRobustness"
)

# Track results
TOTAL_CATEGORIES=${#CATEGORIES[@]}
PASSED_CATEGORIES=0

# Run each category with detailed output
for category in "${CATEGORIES[@]}"; do
    echo ""
    echo "--- Running $category ---"
    
    if docker exec redbarsushi-app python -m pytest tests/e2e/test_advanced_e2e.py::$category -v --tb=short; then
        echo "✅ $category PASSED"
        ((PASSED_CATEGORIES++))
    else
        echo "❌ $category FAILED"
    fi
done

echo ""
echo "=================================================="
echo "Advanced E2E Test Results"
echo "=================================================="
echo "Categories passed: $PASSED_CATEGORIES/$TOTAL_CATEGORIES"

if [ $PASSED_CATEGORIES -eq $TOTAL_CATEGORIES ]; then
    echo "🎉 ALL ADVANCED TESTS PASSED!"
    echo "System is production-ready for conversational AI challenges"
    exit 0
else
    echo "⚠️  Some advanced tests failed"
    echo "Review failures above and fix before production deployment"
    exit 1
fi