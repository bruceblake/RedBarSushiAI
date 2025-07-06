#!/bin/bash
# E2E Test Execution Script for RedBarSushiAI Docker Container
# This script runs comprehensive end-to-end tests inside the Docker container
# against the running application and its dependencies.

set -e  # Exit on any error

echo "🚀 Starting E2E Tests for RedBarSushiAI in Docker Container"
echo "============================================================="

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Docker containers are running
echo -e "${BLUE}📋 Checking Docker container status...${NC}"
if ! docker ps | grep -q "redbarsushi-app"; then
    echo -e "${RED}❌ RedBarSushi app container is not running!${NC}"
    echo "Please start the application with: docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q "redbarsushi-redis"; then
    echo -e "${RED}❌ Redis container is not running!${NC}"
    echo "Please start Redis with: docker-compose up -d"
    exit 1
fi

echo -e "${GREEN}✅ Docker containers are running${NC}"

# Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Set environment variables for E2E testing
export E2E_BASE_URL="http://redbarsushi-app:8000"
export E2E_REDIS_URL="redis://redbarsushi-redis:6379/1"

# Function to run tests inside the app container
run_tests_in_container() {
    local test_category="$1"
    local test_file="$2"
    local test_class="$3"
    
    echo -e "${BLUE}🧪 Running $test_category tests...${NC}"
    
    # Execute pytest inside the app container
    if [ -n "$test_class" ]; then
        docker exec -i redbarsushi-app python -m pytest \
            tests/e2e/$test_file::$test_class \
            -v \
            --tb=short \
            --durations=10 \
            --color=yes \
            -x  # Stop on first failure
    else
        docker exec -i redbarsushi-app python -m pytest \
            tests/e2e/$test_file \
            -v \
            --tb=short \
            --durations=10 \
            --color=yes \
            -x  # Stop on first failure
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $test_category tests passed!${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_category tests failed!${NC}"
        return 1
    fi
}

# Function to run all comprehensive tests
run_comprehensive_tests() {
    echo -e "${YELLOW}🎯 Running Comprehensive E2E Test Suite${NC}"
    echo "========================================"
    
    # Track test results
    local total_categories=4
    local passed_categories=0
    
    # Category 1: Core Ordering Flow
    if run_tests_in_container "Category 1: Core Ordering Flow" "test_comprehensive_e2e.py" "TestCategory1CoreOrderingFlow"; then
        ((passed_categories++))
    fi
    
    echo ""
    
    # Category 2: Item Customization
    if run_tests_in_container "Category 2: Item Customization" "test_comprehensive_e2e.py" "TestCategory2ItemCustomization"; then
        ((passed_categories++))
    fi
    
    echo ""
    
    # Category 3: State Management
    if run_tests_in_container "Category 3: State Management" "test_comprehensive_e2e.py" "TestCategory3StateManagement"; then
        ((passed_categories++))
    fi
    
    echo ""
    
    # Category 4: Validation & Error Recovery
    if run_tests_in_container "Category 4: Validation & Error Recovery" "test_comprehensive_e2e.py" "TestCategory4ValidationAndErrorRecovery"; then
        ((passed_categories++))
    fi
    
    echo ""
    echo "================================================"
    echo -e "${BLUE}📊 Test Results Summary:${NC}"
    echo -e "   Passed Categories: ${GREEN}$passed_categories${NC}/$total_categories"
    
    if [ $passed_categories -eq $total_categories ]; then
        echo -e "${GREEN}🎉 ALL E2E TESTS PASSED! System is ready for production.${NC}"
        return 0
    else
        echo -e "${RED}❌ Some test categories failed. Please review the output above.${NC}"
        return 1
    fi
}

# Function to run specific test category
run_specific_category() {
    local category="$1"
    
    case $category in
        "1"|"core")
            run_tests_in_container "Category 1: Core Ordering Flow" "test_comprehensive_e2e.py" "TestCategory1CoreOrderingFlow"
            ;;
        "2"|"customization")
            run_tests_in_container "Category 2: Item Customization" "test_comprehensive_e2e.py" "TestCategory2ItemCustomization"
            ;;
        "3"|"state")
            run_tests_in_container "Category 3: State Management" "test_comprehensive_e2e.py" "TestCategory3StateManagement"
            ;;
        "4"|"validation")
            run_tests_in_container "Category 4: Validation & Error Recovery" "test_comprehensive_e2e.py" "TestCategory4ValidationAndErrorRecovery"
            ;;
        "basic")
            echo -e "${BLUE}🧪 Running basic E2E tests...${NC}"
            run_tests_in_container "Basic E2E Tests" "test_basic_e2e.py" ""
            ;;
        "robust")
            echo -e "${BLUE}🧪 Running robust E2E tests...${NC}"
            run_tests_in_container "Robust E2E Tests" "test_robust_e2e.py" ""
            ;;
        *)
            echo -e "${RED}❌ Unknown test category: $category${NC}"
            echo "Available categories: 1|core, 2|customization, 3|state, 4|validation, basic, robust"
            exit 1
            ;;
    esac
}

# Function to setup test environment
setup_test_environment() {
    echo -e "${BLUE}🔧 Setting up test environment...${NC}"
    
    # Install any missing dependencies
    docker exec -i redbarsushi-app pip install pytest-asyncio httpx sentence-transformers
    
    # Check if Redis test database is accessible
    echo -e "${BLUE}🔍 Testing Redis connection...${NC}"
    if docker exec -i redbarsushi-redis redis-cli -p 6379 ping | grep -q "PONG"; then
        echo -e "${GREEN}✅ Redis connection successful${NC}"
    else
        echo -e "${RED}❌ Redis connection failed${NC}"
        exit 1
    fi
    
    # Clear test Redis database
    echo -e "${BLUE}🧹 Clearing test Redis database...${NC}"
    docker exec -i redbarsushi-redis redis-cli -p 6379 SELECT 1
    docker exec -i redbarsushi-redis redis-cli -p 6379 FLUSHDB
    
    echo -e "${GREEN}✅ Test environment setup complete${NC}"
}

# Function to cleanup after tests
cleanup_test_environment() {
    echo -e "${BLUE}🧹 Cleaning up test environment...${NC}"
    
    # Clear test Redis database
    docker exec -i redbarsushi-redis redis-cli -p 6379 SELECT 1
    docker exec -i redbarsushi-redis redis-cli -p 6379 FLUSHDB
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [command] [category]"
    echo ""
    echo "Commands:"
    echo "  run [category]    Run specific test category"
    echo "  all              Run all comprehensive E2E tests (default)"
    echo "  setup            Setup test environment only"
    echo "  cleanup          Cleanup test environment only"
    echo "  help             Show this help message"
    echo ""
    echo "Test Categories:"
    echo "  1, core          Category 1: Core Ordering Flow"
    echo "  2, customization Category 2: Item Customization" 
    echo "  3, state         Category 3: State Management"
    echo "  4, validation    Category 4: Validation & Error Recovery"
    echo "  basic            Basic E2E tests"
    echo "  robust           Robust E2E tests"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all comprehensive tests"
    echo "  $0 all               # Run all comprehensive tests"
    echo "  $0 run core          # Run only core ordering flow tests"
    echo "  $0 run 2             # Run only customization tests"
    echo "  $0 setup             # Setup test environment only"
}

# Main execution logic
main() {
    local command="${1:-all}"
    local category="$2"
    
    case $command in
        "run")
            if [ -z "$category" ]; then
                echo -e "${RED}❌ Please specify a test category to run${NC}"
                show_usage
                exit 1
            fi
            setup_test_environment
            run_specific_category "$category"
            cleanup_test_environment
            ;;
        "all"|"")
            setup_test_environment
            run_comprehensive_tests
            cleanup_test_environment
            ;;
        "setup")
            setup_test_environment
            ;;
        "cleanup")
            cleanup_test_environment
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $command${NC}"
            show_usage
            exit 1
            ;;
    esac
}

# Set trap to cleanup on script exit
trap cleanup_test_environment EXIT

# Execute main function with all arguments
main "$@"