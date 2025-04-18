#!/bin/bash
# Comprehensive E2E Test Runner for RedBarSushiAI
# Provides different testing modes, debugging, and log collection

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Create log directories
LOG_DIR="$HOME/redbar_test_logs"
SCREENSHOT_DIR="screenshots"
mkdir -p "$LOG_DIR"
mkdir -p "$SCREENSHOT_DIR"

# Environment configuration
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
export PYTHONUNBUFFERED=1

# Test timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEST_LOG="$LOG_DIR/e2e_test_${TIMESTAMP}.log"
FLASK_LOG="$LOG_DIR/flask_${TIMESTAMP}.log"

# Function to activate virtual environment
activate_venv() {
  if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating it now...${NC}"
    ./install-playwright-pip.sh
  fi
  
  echo -e "${YELLOW}Activating virtual environment...${NC}"
  source venv/bin/activate
}

# Function to clean up processes
cleanup() {
  echo -e "${YELLOW}Cleaning up processes...${NC}"
  pkill -f "python -m flask run" || true
  pkill -f "playwright" || true
  
  echo -e "${YELLOW}Killing any remaining Flask instances...${NC}"
  for pid in $(ps aux | grep "flask run" | grep -v grep | awk '{print $2}'); do
    kill -9 $pid 2>/dev/null || true
  done
  
  echo -e "${GREEN}Cleanup complete.${NC}"
}

# Register cleanup function to run on exit
trap cleanup EXIT

# Display the menu
display_menu() {
  echo -e "${BOLD}===========================================${NC}"
  echo -e "${BOLD}RedBarSushiAI E2E Testing Suite${NC}"
  echo -e "${BOLD}===========================================${NC}"
  echo -e "Choose a testing mode:"
  echo -e "${BLUE}1. Basic Test${NC} - Run the most reliable direct test"
  echo -e "${BLUE}2. Comprehensive Test${NC} - Run the full test suite"
  echo -e "${BLUE}3. Debug Mode${NC} - Run tests with visible browser for debugging"
  echo -e "${BLUE}4. API Test${NC} - Test API endpoints only"
  echo -e "${BLUE}5. Performance Mode${NC} - Run tests with performance tracing"
  echo -e "${BLUE}6. Single File Test${NC} - Run a specific test file"
  echo -e "${BLUE}7. Kill Flask Instances${NC} - Kill any running Flask servers"
  echo -e "${BLUE}8. Exit${NC}"
  echo -e "${BOLD}===========================================${NC}"
  echo -e "Enter your choice (1-8): "
}

# Function to run basic test
run_basic_test() {
  echo -e "${BOLD}Running Basic Test${NC}"
  echo -e "${YELLOW}This is the most reliable test for Arch Linux${NC}"
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  
  # Run the test
  python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
  
  # Check exit status
  if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}Basic test passed successfully!${NC}"
  else
    echo -e "${RED}Basic test failed. Check logs for details.${NC}"
  fi
  
  # Show screenshot location
  echo -e "${YELLOW}Screenshots saved in project root directory${NC}"
  ls -la *.png 2>/dev/null || echo "No screenshots found"
}

# Function to run comprehensive test
run_comprehensive_test() {
  echo -e "${BOLD}Running Comprehensive Tests${NC}"
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  
  # Run direct test first (most reliable)
  echo -e "${YELLOW}Running direct test first...${NC}"
  python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
  
  # Run pytest-based tests
  echo -e "${YELLOW}Running pytest-based tests...${NC}"
  echo -e "${YELLOW}Flask logs will be saved to $FLASK_LOG${NC}"
  
  # Set up the environment for real API testing if requested
  read -p "Use real API keys for testing? (y/n): " use_real_api
  if [[ $use_real_api =~ ^[Yy]$ ]]; then
    export USE_REAL_API_KEYS=true
    export RUN_EXTERNAL_API_TESTS=true
    echo "Using real API keys for testing"
  else
    export USE_REAL_API_KEYS=false
    export RUN_EXTERNAL_API_TESTS=false
    echo "Using mock APIs for testing"
  fi
  
  # Run pytest with logging Flask output to a separate file
  python -m pytest tests/e2e/ -v 2>&1 | tee -a "$TEST_LOG"
  
  # Display results summary
  echo -e "${BOLD}===========================================${NC}"
  echo -e "${YELLOW}Test Results Summary:${NC}"
  grep -E "PASSED|FAILED|SKIPPED" "$TEST_LOG" | sort | uniq -c
  echo -e "${BOLD}===========================================${NC}"
  
  # Show log locations
  echo -e "${YELLOW}Full logs saved to:${NC}"
  echo -e "  Test log: $TEST_LOG"
  echo -e "  Flask log: $FLASK_LOG"
  
  # Show screenshots
  echo -e "${YELLOW}Screenshots saved to $SCREENSHOT_DIR directory${NC}"
  ls -la "$SCREENSHOT_DIR"/*.png 2>/dev/null || echo "No screenshots found in $SCREENSHOT_DIR"
}

# Function to run debug mode
run_debug_mode() {
  echo -e "${BOLD}Running Debug Mode Tests${NC}"
  echo -e "${YELLOW}Debug mode with enhanced logging${NC}"
  
  # Check if we have a display
  if [ -z "$DISPLAY" ]; then
    echo -e "${YELLOW}No X display detected. Running in headless mode with debug info.${NC}"
    export HEADED=false
  else
    echo -e "${YELLOW}X display detected. Running with visible browser.${NC}"
    export HEADED=true
  fi
  
  # Set debug environment variables
  export DEBUG=pw:api
  export DEBUG_LEVEL=debug
  
  # Prompt for test file
  echo -e "${YELLOW}Which test would you like to debug?${NC}"
  echo "1. Direct test (most reliable)"
  echo "2. Basic UI test"
  echo "3. Menu test"
  echo "4. Order test"
  echo "5. API test"
  echo "6. Comprehensive test"
  read -p "Enter your choice (1-6): " debug_choice
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  
  case $debug_choice in
    1)
      echo -e "${YELLOW}Debugging direct test...${NC}"
      python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
      ;;
    2)
      echo -e "${YELLOW}Debugging basic UI test...${NC}"
      python tests/e2e/basic_ui_test.py 2>&1 | tee -a "$TEST_LOG"
      ;;
    3)
      echo -e "${YELLOW}Debugging menu test...${NC}"
      python -m pytest tests/e2e/test_menu.py -v 2>&1 | tee -a "$TEST_LOG"
      ;;
    4)
      echo -e "${YELLOW}Debugging order test...${NC}"
      python -m pytest tests/e2e/test_order.py -v 2>&1 | tee -a "$TEST_LOG"
      ;;
    5)
      echo -e "${YELLOW}Debugging API test...${NC}"
      python -m pytest tests/e2e/test_api.py -v 2>&1 | tee -a "$TEST_LOG"
      ;;
    6)
      echo -e "${YELLOW}Debugging comprehensive test...${NC}"
      python -m pytest tests/e2e/comprehensive_test.py -v 2>&1 | tee -a "$TEST_LOG"
      ;;
    *)
      echo -e "${RED}Invalid option${NC}"
      return 1
      ;;
  esac
  
  echo -e "${YELLOW}Debug logs saved to $TEST_LOG${NC}"
  echo -e "${YELLOW}Check screenshots in the project directory and $SCREENSHOT_DIR${NC}"
}

# Function to run API tests
run_api_test() {
  echo -e "${BOLD}Running API Tests${NC}"
  
  # Ask about real API keys
  read -p "Use real API keys for testing? (y/n): " use_real_api
  if [[ $use_real_api =~ ^[Yy]$ ]]; then
    export USE_REAL_API_KEYS=true
    export RUN_EXTERNAL_API_TESTS=true
    echo "Using real API keys for testing"
  else
    export USE_REAL_API_KEYS=false
    export RUN_EXTERNAL_API_TESTS=false
    echo "Using mock APIs for testing"
  fi
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  
  # Create a test Flask server first to ensure server is running
  echo -e "${YELLOW}Starting Flask server in direct mode...${NC}"
  flask_output="$LOG_DIR/flask_${TIMESTAMP}.log"
  
  # Start Flask in its own process
  FLASK_APP=run.py FLASK_ENV=testing TESTING=true DATABASE_URL="sqlite:///:memory:" \
    python -m flask run --port=5000 > "$flask_output" 2>&1 &
  FLASK_PID=$!
  
  # Wait for server to start
  echo -e "${YELLOW}Waiting for Flask server to start...${NC}"
  sleep 3
  
  # Check if server is running
  if ! curl -s http://localhost:5000/ > /dev/null; then
    echo -e "${RED}Flask server failed to start. Check logs.${NC}"
    cat "$flask_output"
    return 1
  fi
  
  echo -e "${GREEN}Flask server started and running on port 5000${NC}"
  
  # Run simple direct test first to verify API connectivity
  echo -e "${YELLOW}Running direct API test...${NC}"
  python - <<EOF
import requests
import sys

try:
    response = requests.get('http://localhost:5000/api/health', timeout=2)
    print(f"API health check: {response.status_code}")
    if response.status_code == 200:
        print("✅ API connection successful")
        sys.exit(0)
    else:
        print(f"❌ API returned status code: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"❌ API connection failed: {e}")
    sys.exit(1)
EOF

  # Save exit code
  API_TEST_STATUS=$?
  
  if [ $API_TEST_STATUS -ne 0 ]; then
    echo -e "${RED}API direct test failed. Skipping pytest tests.${NC}"
    
    # Stop the Flask server
    echo -e "${YELLOW}Stopping Flask server...${NC}"
    kill $FLASK_PID
    wait $FLASK_PID 2>/dev/null || true
    
    return 1
  fi
  
  # Run the pytest-based API tests
  echo -e "${YELLOW}Running pytest API tests...${NC}"
  PYTHONUNBUFFERED=1 python -m pytest tests/e2e/test_api.py tests/e2e/api_tests.py -v 2>&1 | tee -a "$TEST_LOG"
  
  # Stop the Flask server
  echo -e "${YELLOW}Stopping Flask server...${NC}"
  kill $FLASK_PID
  wait $FLASK_PID 2>/dev/null || true
  
  echo -e "${YELLOW}API test logs saved to $TEST_LOG${NC}"
  echo -e "${YELLOW}Flask server logs saved to $flask_output${NC}"
}

# Function to run performance tests
run_performance_mode() {
  echo -e "${BOLD}Running Performance Tests${NC}"
  
  # Create trace directory
  TRACE_DIR="$LOG_DIR/traces"
  mkdir -p "$TRACE_DIR"
  TRACE_FILE="$TRACE_DIR/trace_${TIMESTAMP}.zip"
  
  # Set performance tracing variables
  export PWTRACING=1
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  echo -e "${YELLOW}Performance trace will be saved to $TRACE_FILE${NC}"
  
  # Run the test with tracing
  python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
  
  # Use Playwright CLI to view traces
  echo -e "${YELLOW}To view traces, run:${NC}"
  echo -e "  source venv/bin/activate"
  echo -e "  python -m playwright show-trace $TRACE_FILE"
}

# Function to run a single test file
run_single_file_test() {
  echo -e "${BOLD}Running Single Test File${NC}"
  
  # List available test files
  echo -e "${YELLOW}Available test files:${NC}"
  echo "direct_test.py (standalone, most reliable)"
  echo "basic_ui_test.py (standalone)"
  ls -1 tests/e2e/test_*.py | sed 's|tests/e2e/||'
  echo "comprehensive_test.py"
  echo "api_tests.py"
  
  # Prompt for file name
  echo -e "${YELLOW}Enter the test file name:${NC}"
  read -p "> " test_file
  
  # Start logging
  echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
  
  # Run the selected test
  if [ "$test_file" = "direct_test.py" ]; then
    echo -e "${YELLOW}Running direct standalone test...${NC}"
    python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
  elif [ "$test_file" = "basic_ui_test.py" ]; then
    echo -e "${YELLOW}Running standalone basic UI test...${NC}"
    python tests/e2e/basic_ui_test.py 2>&1 | tee -a "$TEST_LOG"
  elif [ -f "tests/e2e/$test_file" ]; then
    echo -e "${YELLOW}Running $test_file with pytest...${NC}"
    python -m pytest tests/e2e/$test_file -v 2>&1 | tee -a "$TEST_LOG"
  else
    echo -e "${RED}Test file not found: $test_file${NC}"
    return 1
  fi
  
  echo -e "${YELLOW}Test logs saved to $TEST_LOG${NC}"
}

# Function to kill all Flask instances
kill_flask_instances() {
  echo -e "${BOLD}Killing All Flask Instances${NC}"
  
  # Find and kill Flask processes
  flask_pids=$(ps aux | grep "flask run" | grep -v grep | awk '{print $2}')
  
  if [ -z "$flask_pids" ]; then
    echo -e "${GREEN}No Flask instances running.${NC}"
    return 0
  fi
  
  echo -e "${YELLOW}Found Flask instances:${NC}"
  ps aux | grep "flask run" | grep -v grep
  
  # Kill each process
  for pid in $flask_pids; do
    echo -e "${YELLOW}Killing process $pid...${NC}"
    kill -9 $pid 2>/dev/null || true
  done
  
  echo -e "${GREEN}All Flask instances terminated.${NC}"
}

# Main execution
main() {
  # Activate virtual environment
  activate_venv
  
  # First clean up any existing processes
  cleanup
  
  # Display menu and get choice
  display_menu
  read -p "> " test_mode
  
  case $test_mode in
    1)
      run_basic_test
      ;;
    2)
      run_comprehensive_test
      ;;
    3)
      run_debug_mode
      ;;
    4)
      run_api_test
      ;;
    5)
      run_performance_mode
      ;;
    6)
      run_single_file_test
      ;;
    7)
      kill_flask_instances
      ;;
    8)
      echo -e "${GREEN}Exiting...${NC}"
      exit 0
      ;;
    *)
      echo -e "${RED}Invalid option${NC}"
      exit 1
      ;;
  esac
  
  # Show log locations at the end
  echo -e "${BOLD}===========================================${NC}"
  echo -e "${YELLOW}Test run completed.${NC}"
  echo -e "${YELLOW}Logs saved to:${NC}"
  echo -e "  Test log: $TEST_LOG"
  if [ -f "$FLASK_LOG" ]; then
    echo -e "  Flask log: $FLASK_LOG"
  fi
  echo -e "${BOLD}===========================================${NC}"
}

# Run the main function
main