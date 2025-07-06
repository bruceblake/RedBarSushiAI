#!/bin/bash

# RedBarSushiAI Docker Test Runner
# Runs tests inside Docker containers for consistency and isolation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    echo "Usage: $0 [TEST_CATEGORY] [OPTIONS]"
    echo ""
    echo "Test Categories:"
    echo "  unit          Run unit tests only"
    echo "  integration   Run integration tests only"
    echo "  e2e          Run basic E2E tests only"
    echo "  advanced     Run advanced E2E tests only"
    echo "  all          Run all tests (default)"
    echo ""
    echo "Options:"
    echo "  -h, --help   Show this help message"
    echo "  -v           Verbose output"
    echo "  -q           Quiet output"
    echo "  --no-build   Skip Docker build step"
    echo "  --cleanup    Clean up test containers after run"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 unit              # Run only unit tests"
    echo "  $0 advanced -v       # Run advanced E2E tests with verbose output"
    echo "  $0 e2e --cleanup     # Run E2E tests and cleanup containers"
    echo ""
}

# Default values
TEST_CATEGORY="all"
VERBOSE=""
QUIET=""
NO_BUILD=false
CLEANUP=false
DOCKER_COMPOSE_FILE="docker-compose.yml"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        unit|integration|e2e|advanced|all)
            TEST_CATEGORY="$1"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -q|--quiet)
            QUIET="-q"
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose file exists
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    print_error "docker-compose.yml not found in current directory"
    exit 1
fi

print_status "Starting Docker test runner for RedBarSushiAI"
print_status "Test category: $TEST_CATEGORY"

# Build containers if not skipped
if [ "$NO_BUILD" = false ]; then
    print_status "Building Docker containers..."
    if ! docker-compose build; then
        print_error "Failed to build Docker containers"
        exit 1
    fi
    print_success "Docker containers built successfully"
fi

# Start services
print_status "Starting Docker services..."
if ! docker-compose up -d; then
    print_error "Failed to start Docker services"
    exit 1
fi

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if main app container is running
if ! docker-compose ps | grep -q "redbarsushi.*Up"; then
    print_error "Application container is not running"
    docker-compose logs
    exit 1
fi

# Function to run tests based on category
run_tests() {
    local category=$1
    local test_command=""
    
    case $category in
        unit)
            test_command="pytest tests/unit/ $VERBOSE $QUIET --tb=short"
            print_status "Running unit tests..."
            ;;
        integration)
            test_command="pytest tests/integration/ $VERBOSE $QUIET --tb=short"
            print_status "Running integration tests..."
            ;;
        e2e)
            test_command="pytest tests/e2e/test_comprehensive_e2e.py tests/e2e/test_basic_e2e.py tests/e2e/test_robust_e2e.py $VERBOSE $QUIET --tb=short"
            print_status "Running basic E2E tests..."
            ;;
        advanced)
            test_command="pytest tests/e2e/test_advanced_*.py tests/e2e/test_stress_*.py tests/e2e/test_integration_failure_*.py tests/e2e/test_security_*.py $VERBOSE $QUIET --tb=short -m 'not slow' --maxfail=3"
            print_status "Running advanced E2E tests..."
            print_warning "This may take several minutes..."
            ;;
        all)
            print_status "Running all tests..."
            
            # Run unit tests
            print_status "Phase 1: Unit tests"
            if ! docker-compose exec -T app pytest tests/unit/ $VERBOSE $QUIET --tb=short; then
                print_error "Unit tests failed"
                return 1
            fi
            print_success "Unit tests passed"
            
            # Run integration tests
            print_status "Phase 2: Integration tests"
            if ! docker-compose exec -T app pytest tests/integration/ $VERBOSE $QUIET --tb=short; then
                print_error "Integration tests failed"
                return 1
            fi
            print_success "Integration tests passed"
            
            # Run basic E2E tests
            print_status "Phase 3: Basic E2E tests"
            if ! docker-compose exec -T app pytest tests/e2e/test_comprehensive_e2e.py tests/e2e/test_basic_e2e.py tests/e2e/test_robust_e2e.py $VERBOSE $QUIET --tb=short; then
                print_error "Basic E2E tests failed"
                return 1
            fi
            print_success "Basic E2E tests passed"
            
            # Run advanced E2E tests (quick subset)
            print_status "Phase 4: Advanced E2E tests (quick subset)"
            if ! docker-compose exec -T app pytest tests/e2e/test_advanced_conversational_fluidity.py::TestCategory5ConversationalFluidity::test_5_1_mid_conversation_correction_and_ambiguity tests/e2e/test_security_robustness.py::TestCategory8SecurityRobustness::test_8_1_prompt_injection_prevention $VERBOSE $QUIET --tb=short; then
                print_warning "Some advanced E2E tests failed - this is acceptable for quick validation"
            else
                print_success "Advanced E2E tests (subset) passed"
            fi
            
            print_success "All test phases completed"
            return 0
            ;;
        *)
            print_error "Unknown test category: $category"
            return 1
            ;;
    esac
    
    # Execute the test command for non-"all" categories
    if [ "$category" != "all" ]; then
        if docker-compose exec -T app $test_command; then
            print_success "$category tests passed"
            return 0
        else
            print_error "$category tests failed"
            return 1
        fi
    fi
}

# Run the tests
test_exit_code=0
if ! run_tests "$TEST_CATEGORY"; then
    test_exit_code=1
fi

# Show logs if tests failed
if [ $test_exit_code -ne 0 ]; then
    print_warning "Showing application logs for debugging:"
    docker-compose logs --tail=50 app
fi

# Cleanup if requested
if [ "$CLEANUP" = true ]; then
    print_status "Cleaning up Docker containers..."
    docker-compose down
    print_success "Cleanup completed"
fi

# Final status
if [ $test_exit_code -eq 0 ]; then
    print_success "Test run completed successfully!"
else
    print_error "Test run failed!"
    print_status "To debug:"
    print_status "  - View logs: docker-compose logs app"
    print_status "  - Access container: docker-compose exec app bash"
    print_status "  - Run specific test: docker-compose exec app pytest tests/path/to/test.py -v"
fi

exit $test_exit_code