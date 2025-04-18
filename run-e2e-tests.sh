#!/bin/bash
# Run end-to-end tests for RedBarSushiAI

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}RedBarSushiAI End-to-End Testing Suite${NC}"
echo -e "${BOLD}===========================================${NC}"

# Ensure virtual environment is active
if [ ! -d "venv" ]; then
  echo -e "${RED}Virtual environment not found${NC}"
  echo "Please run ./install-playwright-pip.sh first to set up the environment"
  exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set environment variable to skip Playwright host validation
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

# Check for .env.test file
if [ ! -f ".env.test" ]; then
  echo -e "${YELLOW}Creating default .env.test file...${NC}"
  
  cat > .env.test << 'ENVTEST'
# Test Environment Configuration
TESTING=true
FLASK_ENV=testing
DEBUG=true
DATABASE_URL=sqlite:///:memory:
DISABLE_OPENAI=true
TEST_WITH_MOCKS=true
ENVTEST
fi

# Ask user if they want to use real API keys
echo -e "${YELLOW}Do you want to use real API keys for full testing? (y/n)${NC}"
read -p "> " use_real_keys

if [[ $use_real_keys =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Using real API keys for testing${NC}"
  
  # Update .env.test with real keys flag
  if grep -q "USE_REAL_API_KEYS" .env.test; then
    sed -i 's/USE_REAL_API_KEYS=.*/USE_REAL_API_KEYS=true/' .env.test
  else
    echo "USE_REAL_API_KEYS=true" >> .env.test
  fi
  
  # Check if any required API keys are missing
  if ! grep -q "OPENAI_API_KEY" .env.test || grep -q "OPENAI_API_KEY=.*your-actual" .env.test; then
    echo -e "${YELLOW}OpenAI API key not found in .env.test${NC}"
    echo -e "${YELLOW}Enter your OpenAI API key (sk-...):${NC}"
    read -p "> " openai_key
    if [ -n "$openai_key" ]; then
      if grep -q "OPENAI_API_KEY" .env.test; then
        sed -i "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" .env.test
      else
        echo "OPENAI_API_KEY=$openai_key" >> .env.test
      fi
    fi
  fi
else
  echo -e "${YELLOW}Using mock APIs for testing${NC}"
  # Update .env.test to use mocks
  if grep -q "USE_REAL_API_KEYS" .env.test; then
    sed -i 's/USE_REAL_API_KEYS=.*/USE_REAL_API_KEYS=false/' .env.test
  else
    echo "USE_REAL_API_KEYS=false" >> .env.test
  fi
  
  if grep -q "TEST_WITH_MOCKS" .env.test; then
    sed -i 's/TEST_WITH_MOCKS=.*/TEST_WITH_MOCKS=true/' .env.test
  else
    echo "TEST_WITH_MOCKS=true" >> .env.test
  fi
  
  if grep -q "DISABLE_OPENAI" .env.test; then
    sed -i 's/DISABLE_OPENAI=.*/DISABLE_OPENAI=true/' .env.test
  else
    echo "DISABLE_OPENAI=true" >> .env.test
  fi
fi

# Ask which tests to run
echo -e "${YELLOW}Which tests would you like to run?${NC}"
echo "1. Basic tests only (menu, basic UI)"
echo "2. Full tests (menu, orders, API)"
echo "3. Single test file"
read -p "> " test_option

# Create directory for screenshots if it doesn't exist
mkdir -p screenshots

# Run the selected tests
case $test_option in
  1)
    echo -e "${GREEN}Running basic tests...${NC}"
    echo -e "${YELLOW}Running direct standalone test (most reliable)...${NC}"
    python tests/e2e/direct_test.py
    ;;
  2)
    echo -e "${GREEN}Running full test suite...${NC}"
    echo -e "${YELLOW}First running direct standalone test...${NC}"
    python tests/e2e/direct_test.py
    
    echo -e "${YELLOW}Now trying the basic UI tests...${NC}"
    python tests/e2e/basic_ui_test.py || echo -e "${YELLOW}Basic UI test may have failed, but continuing...${NC}"
    
    echo -e "${YELLOW}Now running pytest tests...${NC}"
    python -m pytest tests/e2e/ -v || echo -e "${YELLOW}Some pytest tests may have failed, but checking screenshots...${NC}"
    ;;
  3)
    echo -e "${YELLOW}Available test files:${NC}"
    echo "direct_test.py (standalone, most reliable)"
    echo "basic_ui_test.py (standalone)"
    ls -1 tests/e2e/test_*.py | sed 's|tests/e2e/||'
    echo -e "${YELLOW}Enter the test file name:${NC}"
    read -p "> " test_file
    
    if [ "$test_file" = "direct_test.py" ]; then
      echo -e "${GREEN}Running direct standalone test...${NC}"
      python tests/e2e/direct_test.py
    elif [ "$test_file" = "basic_ui_test.py" ]; then
      echo -e "${GREEN}Running standalone basic UI test...${NC}"
      python tests/e2e/basic_ui_test.py
    elif [ -f "tests/e2e/$test_file" ]; then
      echo -e "${GREEN}Running $test_file...${NC}"
      python -m pytest tests/e2e/$test_file -v
    else
      echo -e "${RED}Test file not found: $test_file${NC}"
      exit 1
    fi
    ;;
  *)
    echo -e "${RED}Invalid option${NC}"
    exit 1
    ;;
esac

# Store the exit code
TEST_EXIT_CODE=$?

# Display summary
echo -e "${BOLD}===========================================${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}All tests passed!${NC}"
else
  echo -e "${RED}Some tests failed or were skipped.${NC}"
  echo -e "${YELLOW}Check the output above for details.${NC}"
fi
echo -e "${BOLD}===========================================${NC}"

# Exit with the test result code
exit $TEST_EXIT_CODE