#!/bin/bash
# Script to install Playwright using pip (for any Linux distribution)

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}RedBarSushiAI Playwright Installation${NC}"
echo -e "${BOLD}===========================================${NC}"

# Skip validation of host requirements (needed for Arch Linux)
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

# Create screenshots directory
mkdir -p screenshots
mkdir -p tests/e2e/test-data

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}Creating virtual environment...${NC}"
  python -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install playwright pytest pytest-playwright python-dotenv

# Install Playwright browsers
echo -e "${YELLOW}Installing Playwright browsers...${NC}"
python -m playwright install chromium

# Create default .env.test file if it doesn't exist
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
USE_REAL_API_KEYS=false
RUN_EXTERNAL_API_TESTS=false
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
BYPASS_AUTH_FOR_TESTING=true
ENVTEST
fi

# Check if run-e2e-tests.sh is executable
if [ -f "./run-e2e-tests.sh" ]; then
  chmod +x run-e2e-tests.sh
fi

echo -e "${GREEN}Installation completed successfully!${NC}"
echo -e "${YELLOW}To run tests, use ./run-e2e-tests.sh${NC}"
echo -e "${BOLD}===========================================${NC}"
echo ""
echo -e "Or run tests directly:"
echo -e "${YELLOW}source venv/bin/activate${NC}"
echo -e "${YELLOW}export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1${NC}"
echo -e "${YELLOW}python tests/e2e/direct_test.py${NC}"
echo -e "${BOLD}===========================================${NC}"
echo -e "${YELLOW}For more information, read ARCH_LINUX_TESTING.md${NC}"

exit 0