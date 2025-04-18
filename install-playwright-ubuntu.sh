#!/bin/bash
# Script to install Playwright for Ubuntu systems (GitHub Actions)

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}RedBarSushiAI Ubuntu Playwright Installation${NC}"
echo -e "${BOLD}===========================================${NC}"

# Install system dependencies 
echo -e "${YELLOW}Installing system dependencies...${NC}"
sudo apt-get update
sudo apt-get install -y xvfb libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm-dev libasound2

# Create and activate virtual environment
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
pip install pytest pytest-playwright

# Install Playwright
echo -e "${YELLOW}Installing Playwright...${NC}"
pip install playwright==1.41.2

# Install Playwright browsers
echo -e "${YELLOW}Installing Playwright browsers...${NC}"
python -m playwright install chromium

# Install Playwright system dependencies
echo -e "${YELLOW}Installing Playwright system dependencies...${NC}"
python -m playwright install-deps chromium

# Create screenshots directory
mkdir -p screenshots
mkdir -p tests/e2e/test-data

echo -e "${GREEN}Installation completed successfully!${NC}"
echo -e "${YELLOW}To run tests, use ./run-full-e2e-tests.sh${NC}"
echo -e "${BOLD}===========================================${NC}"

# Set executable permissions
chmod +x run-full-e2e-tests.sh