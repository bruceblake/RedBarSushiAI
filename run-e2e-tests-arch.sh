#!/bin/bash
# Run end-to-end tests on Arch Linux with Xvfb for GUI tests

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Check for xvfb
if ! command -v xvfb-run &> /dev/null; then
    echo -e "${RED}xvfb-run not found. Please install xorg-server-xvfb package:${NC}"
    echo -e "${YELLOW}sudo pacman -S xorg-server-xvfb${NC}"
    exit 1
fi

echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}RedBarSushiAI Arch Linux E2E Testing${NC}"
echo -e "${BOLD}===========================================${NC}"

# Create log directory
LOG_DIR="$HOME/redbar_test_logs"
mkdir -p "$LOG_DIR"

# Set timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEST_LOG="$LOG_DIR/arch_test_${TIMESTAMP}.log"
FLASK_LOG="$LOG_DIR/arch_flask_${TIMESTAMP}.log"

# Ensure we have virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    ./install-playwright-pip.sh
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Set environment variables
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
export DISPLAY=:99  # Virtual display 
export PYTHONUNBUFFERED=1

# Clean up function
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    # Kill any Flask servers
    pkill -f "flask run" || true
    # Kill Xvfb
    pkill -f "Xvfb" || true
}

# Register cleanup on exit
trap cleanup EXIT

# Menu of tests to run
echo -e "${YELLOW}Choose a test to run:${NC}"
echo "1. Direct test (most reliable)"
echo "2. API test (tests API endpoints)"
echo "3. Full UI test (with virtual display)"
echo "4. Exit"
read -p "> " test_choice

# Clean up any existing processes first
cleanup

# Run the selected test
case $test_choice in
    1)
        echo -e "${BOLD}Running Direct Test${NC}"
        echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
        
        # Run the direct test with headless browser (most reliable)
        python tests/e2e/direct_test.py 2>&1 | tee -a "$TEST_LOG"
        ;;
    2)
        echo -e "${BOLD}Running API Tests${NC}"
        echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
        
        # Start a Flask server
        echo -e "${YELLOW}Starting Flask server...${NC}"
        FLASK_APP=run.py FLASK_ENV=testing TESTING=true DATABASE_URL="sqlite:///:memory:" \
            python -m flask run --port=5000 > "$FLASK_LOG" 2>&1 &
        FLASK_PID=$!
        
        # Wait for server to start
        echo -e "${YELLOW}Waiting for Flask server to start...${NC}"
        sleep 3
        
        # Test API connectivity
        echo -e "${YELLOW}Testing API connectivity...${NC}"
        if ! curl -s http://localhost:5000/ > /dev/null; then
            echo -e "${RED}Flask server not responding. Check logs.${NC}"
            cat "$FLASK_LOG"
            # Kill the Flask server
            kill $FLASK_PID 2>/dev/null || true
            exit 1
        fi
        
        echo -e "${GREEN}Flask server running. Running API tests...${NC}"
        
        # Run just the API tests
        python tests/e2e/test_api.py 2>&1 | tee -a "$TEST_LOG"
        
        # Kill the Flask server
        kill $FLASK_PID 2>/dev/null || true
        ;;
    3)
        echo -e "${BOLD}Running Full UI Tests with Xvfb${NC}"
        echo -e "${YELLOW}Logging to $TEST_LOG${NC}"
        
        # Start Xvfb
        echo -e "${YELLOW}Starting Xvfb...${NC}"
        Xvfb :99 -screen 0 1280x1024x24 > /dev/null 2>&1 &
        XVFB_PID=$!
        
        # Wait for Xvfb to start
        sleep 2
        
        if ! ps -p $XVFB_PID > /dev/null; then
            echo -e "${RED}Failed to start Xvfb. Is xorg-server-xvfb installed?${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Xvfb started. Running UI tests...${NC}"
        
        # Set browser to visible mode since we have Xvfb running
        export HEADED=true
        
        # Run the test with virtual display
        python tests/e2e/basic_ui_test.py 2>&1 | tee -a "$TEST_LOG"
        
        # Kill Xvfb
        kill $XVFB_PID 2>/dev/null || true
        ;;
    4)
        echo -e "${GREEN}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

# Show results
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Tests completed successfully!${NC}"
else
    echo -e "${RED}Tests failed. Check log files:${NC}"
    echo -e "  ${YELLOW}$TEST_LOG${NC}"
    echo -e "  ${YELLOW}$FLASK_LOG${NC}"
fi

echo -e "${BOLD}===========================================${NC}"
echo -e "${YELLOW}Screenshots saved to project directory and screenshots/${NC}"
ls -la *.png 2>/dev/null || echo "No screenshots in root directory"
ls -la screenshots/*.png 2>/dev/null || echo "No screenshots in screenshots directory" 
echo -e "${BOLD}===========================================${NC}"