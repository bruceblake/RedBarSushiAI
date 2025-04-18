#!/bin/bash
# Comprehensive test runner script for RedBarSushiAI

# Text formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}==============================================${NC}"
echo -e "${BOLD}RedBarSushiAI Comprehensive Testing Suite${NC}"
echo -e "${BOLD}==============================================${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
  echo -e "${RED}Error: Virtual environment not found${NC}"
  echo "Please run './install-playwright-pip.sh' first to set up Playwright."
  exit 1
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Check for environment file
if [ ! -f ".env.test" ]; then
  echo -e "${RED}Error: .env.test file not found${NC}"
  echo "Creating a default .env.test file..."
  
  cat > .env.test << 'ENVTEST'
# Test Environment Configuration
# Replace these with your actual API keys for full integration testing

# Basic Settings
TESTING=true
FLASK_ENV=testing
DEBUG=true

# Database
DATABASE_URL=sqlite:///:memory:

# OpenAI
# Set DISABLE_OPENAI=false and provide real API key for full integration tests
DISABLE_OPENAI=true  
OPENAI_API_KEY=sk-your-actual-openai-key

# Twilio
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_NUMBER=+15551234567

# Deliverect
DELIVERECT_CLIENT_ID=your-deliverect-client-id
DELIVERECT_CLIENT_SECRET=your-deliverect-client-secret
DELIVERECT_ACCOUNT_ID=your-deliverect-account-id

# Test Configuration
RUN_EXTERNAL_API_TESTS=false
BYPASS_AUTH_FOR_TESTING=true
ENVTEST
fi

# Ask for API key confirmation
echo -e "${YELLOW}This test suite will use real API keys if provided in .env.test${NC}"
read -p "Do you want to run tests with real API keys? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  # Set environment to use mocks instead
  echo "Setting DISABLE_OPENAI=true to use mocks instead of real API keys"
  sed -i 's/DISABLE_OPENAI=false/DISABLE_OPENAI=true/g' .env.test
  sed -i 's/RUN_EXTERNAL_API_TESTS=true/RUN_EXTERNAL_API_TESTS=false/g' .env.test
fi

# Create test data directory if it doesn't exist
mkdir -p tests/e2e/test-data

# Start the application in the background
echo -e "${GREEN}Starting application...${NC}"
export $(grep -v '^#' .env.test | xargs) # Load env variables
flask run --port=5000 &
APP_PID=$!

# Wait for the application to start
echo -e "${GREEN}Waiting for application to start...${NC}"
sleep 5

# Run the Playwright tests
echo -e "${GREEN}Running simple test to verify setup...${NC}"
python -m pytest tests/e2e/custom-test.py -v

echo -e "${GREEN}Running comprehensive E2E tests...${NC}"
python -m pytest tests/e2e/comprehensive_test.py -v

# Capture the exit code
TEST_RESULT=$?

# Clean up - kill the application process
echo -e "${GREEN}Cleaning up...${NC}"
kill $APP_PID

# Print summary
echo -e "${BOLD}==============================================${NC}"
if [ $TEST_RESULT -eq 0 ]; then
  echo -e "${GREEN}All tests passed successfully!${NC}"
else
  echo -e "${RED}Some tests failed. Check the output above for details.${NC}"
fi
echo -e "${BOLD}==============================================${NC}"

# Exit with the test result code
exit $TEST_RESULT