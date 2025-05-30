#!/bin/bash
# Script for running tests in CI/CD environment

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# CI environment setup
export CI=true
export FORCE_COLOR=1
export PYTHONUNBUFFERED=1

# Colors for output (force colors in CI)
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🤖 RedBarSushiAI CI Test Runner${NC}"
echo "================================"
echo "Environment: CI/CD"
echo "Branch: ${GITHUB_REF:-${CI_COMMIT_BRANCH:-unknown}}"
echo "Commit: ${GITHUB_SHA:-${CI_COMMIT_SHA:-unknown}}"
echo ""

# Source manage-test-secrets.sh for CI environment
if [ -f "$PROJECT_ROOT/scripts/manage-test-secrets.sh" ]; then
    echo -e "${YELLOW}🔐 Setting up CI test environment...${NC}"
    source "$PROJECT_ROOT/scripts/manage-test-secrets.sh" setup
fi

# Wait for services with extended timeout for CI
if [ -f "$PROJECT_ROOT/scripts/wait-for-services.sh" ]; then
    echo -e "${YELLOW}⏳ Waiting for services (CI mode)...${NC}"
    "$PROJECT_ROOT/scripts/wait-for-services.sh" --extended
fi

# Clean artifacts before test
if [ -f "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" ]; then
    "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" clean
fi

# Run tests based on CI stage
TEST_STAGE=${1:-all}

case $TEST_STAGE in
    lint)
        echo -e "${BLUE}🔍 Running linting checks...${NC}"
        # Add linting commands here if needed
        echo "Linting not yet configured"
        ;;
    
    unit)
        echo -e "${BLUE}🧪 Running unit tests...${NC}"
        SKIP_HEALTH_CHECK=true pytest tests/unit/ \
            -v \
            --color=yes \
            --junit-xml=test-results/unit-junit.xml \
            --cov=app \
            --cov-report=xml:coverage/unit-coverage.xml \
            --cov-report=term
        ;;
    
    integration)
        echo -e "${BLUE}🧪 Running integration tests...${NC}"
        pytest tests/integration/ \
            -v \
            --color=yes \
            --junit-xml=test-results/integration-junit.xml \
            --cov=app \
            --cov-report=xml:coverage/integration-coverage.xml \
            --cov-report=term \
            --cov-append
        ;;
    
    e2e)
        echo -e "${BLUE}🧪 Running E2E tests...${NC}"
        pytest tests/e2e/ \
            -v \
            --color=yes \
            --junit-xml=test-results/e2e-junit.xml \
            --maxfail=5
        ;;
    
    all)
        echo -e "${BLUE}🧪 Running all tests...${NC}"
        pytest tests/ \
            -v \
            --color=yes \
            --junit-xml=test-results/junit.xml \
            --html=test-results/report.html \
            --self-contained-html \
            --cov=app \
            --cov-report=xml:coverage/coverage.xml \
            --cov-report=html:htmlcov \
            --cov-report=term \
            --cov-fail-under=${COVERAGE_THRESHOLD:-80}
        ;;
    
    *)
        echo -e "${RED}❌ Unknown test stage: $TEST_STAGE${NC}"
        exit 1
        ;;
esac

EXIT_CODE=$?

# Mask secrets in logs
if [ -f "$PROJECT_ROOT/scripts/manage-test-secrets.sh" ]; then
    find test-results -name "*.xml" -exec "$PROJECT_ROOT/scripts/manage-test-secrets.sh" mask {} \;
    find test-logs -name "*.log" -exec "$PROJECT_ROOT/scripts/manage-test-secrets.sh" mask {} \;
fi

# Archive test artifacts
if [ -f "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" ] && [ $EXIT_CODE -eq 0 ]; then
    "$PROJECT_ROOT/scripts/clean-test-artifacts.sh" archive
fi

# Print summary
echo ""
echo -e "${BLUE}📊 Test Summary:${NC}"
echo "================================"

if [ -f "test-results/junit.xml" ]; then
    # Parse junit results if xmllint is available
    if command -v xmllint > /dev/null; then
        TESTS=$(xmllint --xpath "string(/testsuites/@tests)" test-results/junit.xml 2>/dev/null || echo "?")
        FAILURES=$(xmllint --xpath "string(/testsuites/@failures)" test-results/junit.xml 2>/dev/null || echo "?")
        ERRORS=$(xmllint --xpath "string(/testsuites/@errors)" test-results/junit.xml 2>/dev/null || echo "?")
        TIME=$(xmllint --xpath "string(/testsuites/@time)" test-results/junit.xml 2>/dev/null || echo "?")
        
        echo "Total tests: $TESTS"
        echo "Failures: $FAILURES"
        echo "Errors: $ERRORS"
        echo "Time: ${TIME}s"
    fi
fi

if [ -f "coverage/coverage.xml" ]; then
    # Show coverage summary
    coverage report --skip-covered || true
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ CI tests passed!${NC}"
else
    echo -e "${RED}❌ CI tests failed with exit code $EXIT_CODE${NC}"
fi

exit $EXIT_CODE