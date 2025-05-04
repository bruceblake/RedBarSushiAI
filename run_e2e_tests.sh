#!/bin/bash
# Comprehensive E2E test runner for RedBarSushiAI
# This script sets up the entire testing environment and runs all E2E tests

# Exit immediately if any command fails
set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_TEST_MODE="local"  # local, docker, or staging
DEFAULT_TEST_PATTERN="tests/e2e/*.py"
DEFAULT_SKIP_SETUP=false
DEFAULT_RUN_CLEANUP=true
DEFAULT_VERBOSE=false
DEFAULT_PARALLEL=false

# Timestamp function
timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Print with timestamp
log() {
  echo -e "$(timestamp) - $1"
}

# Print a section header
section() {
  echo -e "\n${BLUE}=======================================================${NC}"
  echo -e "${BLUE}   $1${NC}"
  echo -e "${BLUE}=======================================================${NC}\n"
}

# Print error and exit
error() {
  echo -e "\n${RED}ERROR: $1${NC}" >&2
  exit 1
}

# Display usage information
usage() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -m, --mode MODE         Test mode: local, docker, or staging (default: $DEFAULT_TEST_MODE)"
  echo "  -p, --pattern PATTERN   Test file pattern (default: $DEFAULT_TEST_PATTERN)"
  echo "  -s, --skip-setup        Skip setup steps"
  echo "  -c, --skip-cleanup      Skip cleanup steps"
  echo "  -v, --verbose           Verbose output"
  echo "  -j, --parallel          Run tests in parallel"
  echo "  -h, --help              Display this help message"
  echo ""
  echo "Examples:"
  echo "  $0 --mode docker                    # Run all E2E tests in Docker environment"
  echo "  $0 --pattern 'tests/e2e/test_*_order_*.py' # Run order-related tests only"
  echo "  $0 --mode staging --skip-setup      # Run against staging, skip setup"
  echo ""
  exit 0
}

# Parse command line arguments
TEST_MODE=$DEFAULT_TEST_MODE
TEST_PATTERN=$DEFAULT_TEST_PATTERN
SKIP_SETUP=$DEFAULT_SKIP_SETUP
RUN_CLEANUP=$DEFAULT_RUN_CLEANUP
VERBOSE=$DEFAULT_VERBOSE
PARALLEL=$DEFAULT_PARALLEL

while [[ $# -gt 0 ]]; do
  case $1 in
    -m|--mode)
      TEST_MODE="$2"
      shift 2
      ;;
    -p|--pattern)
      TEST_PATTERN="$2"
      shift 2
      ;;
    -s|--skip-setup)
      SKIP_SETUP=true
      shift
      ;;
    -c|--skip-cleanup)
      RUN_CLEANUP=false
      shift
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -j|--parallel)
      PARALLEL=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      error "Unknown option: $1"
      ;;
  esac
done

# Validate test mode
if [[ "$TEST_MODE" != "local" && "$TEST_MODE" != "docker" && "$TEST_MODE" != "staging" ]]; then
  error "Invalid test mode: $TEST_MODE. Must be 'local', 'docker', or 'staging'."
fi

# Set verbose flag for pytest
PYTEST_VERBOSE=""
if [[ "$VERBOSE" == true ]]; then
  PYTEST_VERBOSE="-v"
fi

# Set parallel flag for pytest
PYTEST_PARALLEL=""
if [[ "$PARALLEL" == true ]]; then
  PYTEST_PARALLEL="-xvs"
fi

# Get absolute path to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Create reports directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/tests/e2e/reports"

# Set up Test Environment
setup_environment() {
  section "Setting up test environment: $TEST_MODE mode"
  
  case $TEST_MODE in
    local)
      # Activate virtualenv if it exists
      if [[ -d "venv" ]]; then
        log "Activating virtual environment..."
        source venv/bin/activate
      fi
      
      # Set environment variables for local testing
      export TEST_MODE="local"
      export TESTING=true
      export FLASK_ENV=testing
      
      # Use local PostgreSQL and Redis if available (else fallback to SQLite and in-memory)
      if command -v pg_isready &> /dev/null; then
        if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
          log "PostgreSQL is running, using it for tests..."
          export DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
        else
          log "PostgreSQL not available, falling back to SQLite..."
          export DATABASE_URL="sqlite:///test_db.sqlite"
        fi
      else
        log "PostgreSQL client not installed, falling back to SQLite..."
        export DATABASE_URL="sqlite:///test_db.sqlite"
      fi
      
      # Check if Redis is available
      if command -v redis-cli &> /dev/null; then
        if redis-cli ping > /dev/null 2>&1; then
          log "Redis is running, using it for tests..."
          export REDIS_URL="redis://localhost:6379/0"
          export CELERY_BROKER_URL="redis://localhost:6379/1"
          export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
        else
          log "Redis not available, falling back to in-memory..."
          export REDIS_URL=""
        fi
      else
        log "Redis client not installed, falling back to in-memory..."
        export REDIS_URL=""
      fi
      
      # Initialize database for testing
      log "Initializing database..."
      python -c "from flask import Flask; from app import db; from app.models import location, menu, order; app = Flask(__name__); app.config['SQLALCHEMY_DATABASE_URI'] = '$DATABASE_URL'; app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False; db.init_app(app); with app.app_context(): db.create_all()" || log "Warning: Error initializing database"
      
      # Load test fixtures
      log "Loading test fixtures..."
      python -c "from flask import Flask; from app import db; from tests.e2e.fixtures import setup_test_data; app = Flask(__name__); app.config['SQLALCHEMY_DATABASE_URI'] = '$DATABASE_URL'; app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False; db.init_app(app); with app.app_context(): setup_test_data()" || log "Warning: Error loading test fixtures"
      ;;
      
    docker)
      # Make sure Docker is running
      if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker to run tests in docker mode."
      fi
      
      if ! docker info > /dev/null 2>&1; then
        error "Docker daemon is not running. Please start Docker to run tests in docker mode."
      fi
      
      log "Starting Docker containers..."
      docker-compose -f docker-compose-e2e.yml down -v > /dev/null 2>&1 || true
      docker-compose -f docker-compose-e2e.yml up -d
      
      # Wait for containers to be healthy
      log "Waiting for containers to be healthy..."
      sleep 5
      max_retries=30
      retry_count=0
      
      while ! docker-compose -f docker-compose-e2e.yml ps | grep web-app | grep -q "Up"; do
        retry_count=$((retry_count+1))
        if [ $retry_count -eq $max_retries ]; then
          error "Timed out waiting for web-app container to start."
        fi
        log "Waiting for web-app container... ($retry_count/$max_retries)"
        sleep 2
      done
      
      # Use Docker containers for testing
      export TEST_MODE="docker"
      export TESTING=true
      export DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
      export REDIS_URL="redis://localhost:6379/0"
      export CELERY_BROKER_URL="redis://localhost:6379/1"
      export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
      export BASE_URL="http://localhost:5000"
      ;;
      
    staging)
      # Set environment variables for staging tests
      export TEST_MODE="staging"
      export TESTING=true
      export SKIP_DB_INIT=true
      export SKIP_DB_SETUP=true
      export BASE_URL="https://redbarsushiai-staging.onrender.com"
      
      # Check if staging environment is reachable
      log "Checking if staging environment is reachable..."
      if ! curl -s --head "${BASE_URL}/health" | head -n 1 | grep -q "200"; then
        error "Staging environment is not reachable. Please check if it's running."
      fi
      
      log "Staging environment is ready for testing."
      ;;
  esac
  
  log "Environment setup complete."
}

# Run tests
run_tests() {
  section "Running E2E tests: $TEST_PATTERN"
  
  # Install required dependencies first
  log "Installing required dependencies for E2E tests..."
  pip install -q --no-cache-dir -r requirements.e2e.txt
  
  # Install playwright browsers
  if ! python -c "import playwright" &> /dev/null; then
    log "Installing Playwright browsers..."
    python -m playwright install --with-deps chromium
  fi
  
  # Extra arguments based on test mode
  EXTRA_ARGS=""
  case $TEST_MODE in
    local)
      # Setup Xvfb for headless browser testing in local mode
      log "Setting up Xvfb for browser testing..."
      if ! command -v Xvfb &> /dev/null; then
        log "Xvfb not found, trying to install it..."
        if command -v apt-get &> /dev/null; then
          sudo apt-get update && sudo apt-get install -y xvfb
        elif command -v yum &> /dev/null; then
          sudo yum install -y xorg-x11-server-Xvfb
        else
          log "WARNING: Could not install Xvfb, browser tests may fail"
        fi
      fi
      
      # Start Xvfb if available
      if command -v Xvfb &> /dev/null; then
        Xvfb :99 -screen 0 1280x720x24 > /dev/null 2>&1 &
        XVFB_PID=$!
        export DISPLAY=:99.0
        log "Started Xvfb with PID: $XVFB_PID"
      fi
      ;;
      
    docker)
      # For Docker, run tests inside the test-runner container
      log "Running tests in Docker container..."
      docker-compose -f docker-compose-e2e.yml run --rm test-runner
      return $?
      ;;
      
    staging)
      # For staging, set additional flags and setup Xvfb
      EXTRA_ARGS="--no-db-setup"
      
      # Setup Xvfb for headless browser testing in staging mode
      log "Setting up Xvfb for browser testing..."
      if ! command -v Xvfb &> /dev/null; then
        log "Xvfb not found, trying to install it..."
        if command -v apt-get &> /dev/null; then
          sudo apt-get update && sudo apt-get install -y xvfb
        elif command -v yum &> /dev/null; then
          sudo yum install -y xorg-x11-server-Xvfb
        else
          log "WARNING: Could not install Xvfb, browser tests may fail"
        fi
      fi
      
      # Start Xvfb if available
      if command -v Xvfb &> /dev/null; then
        Xvfb :99 -screen 0 1280x720x24 > /dev/null 2>&1 &
        XVFB_PID=$!
        export DISPLAY=:99.0
        log "Started Xvfb with PID: $XVFB_PID"
      fi
      ;;
  esac
  
  # Run tests locally for local and staging modes
  if [[ "$TEST_MODE" != "docker" ]]; then
    log "Running tests locally..."
    export PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
    
    # First run a basic test to make sure the environment is sane
    if [[ "$TEST_PATTERN" == "tests/e2e/*.py" || "$TEST_PATTERN" == "tests/e2e/test_*.py" ]]; then
      log "Running basic tests first to verify setup..."
      python -m pytest tests/e2e/test_basic.py -v
    fi
    
    # Then run the main tests
    log "Running main tests..."
    python -m pytest $TEST_PATTERN $PYTEST_VERBOSE $PYTEST_PARALLEL $EXTRA_ARGS --junitxml=tests/e2e/reports/test-results.xml
    TEST_EXIT_CODE=$?
    
    # Kill Xvfb if it was started
    if [[ -n "$XVFB_PID" ]]; then
      log "Stopping Xvfb process with PID: $XVFB_PID"
      kill $XVFB_PID || true
    fi
    
    return $TEST_EXIT_CODE
  fi
}

# Clean up resources
cleanup() {
  section "Cleaning up resources"
  
  case $TEST_MODE in
    local)
      # Clean up local resources
      log "Cleaning up local test database..."
      # Only clean up if SQLite
      if [[ "$DATABASE_URL" == sqlite* ]]; then
        rm -f test_db.sqlite || true
      fi
      ;;
      
    docker)
      # Clean up Docker resources
      log "Stopping and removing Docker containers..."
      docker-compose -f docker-compose-e2e.yml down -v
      ;;
      
    staging)
      # Nothing to clean up for staging
      log "No cleanup needed for staging environment."
      ;;
  esac
  
  log "Cleanup complete."
}

# Main function
main() {
  section "Starting E2E Tests for RedBarSushiAI"
  log "Test mode: $TEST_MODE"
  log "Test pattern: $TEST_PATTERN"
  
  # Record start time
  start_time=$(date +%s)
  
  # Set up test environment unless skipped
  if [[ "$SKIP_SETUP" == false ]]; then
    setup_environment
  else
    log "Skipping environment setup as requested."
  fi
  
  # Run the tests
  run_tests
  test_exit_code=$?
  
  # Clean up resources unless skipped
  if [[ "$RUN_CLEANUP" == true ]]; then
    cleanup
  else
    log "Skipping cleanup as requested."
  fi
  
  # Calculate duration
  end_time=$(date +%s)
  duration=$((end_time - start_time))
  duration_minutes=$((duration / 60))
  duration_seconds=$((duration % 60))
  
  # Report test results
  section "Test Results"
  if [[ $test_exit_code -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
  else
    echo -e "${RED}Tests failed with exit code: $test_exit_code${NC}"
  fi
  
  echo -e "Test execution time: ${YELLOW}${duration_minutes}m ${duration_seconds}s${NC}"
  echo -e "Test report saved to: ${BLUE}tests/e2e/reports/test-results.xml${NC}"
  
  return $test_exit_code
}

# Execute main function
main
exit $?