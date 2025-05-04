#!/bin/bash
# Script to install dependencies for E2E tests with proper version compatibility

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Installing compatible dependencies for E2E tests...${NC}"

# Upgrade pip
python -m pip install --upgrade pip
echo -e "${GREEN}Pip upgraded${NC}"

# Install core testing packages with specific versions first to avoid conflicts
echo -e "${YELLOW}Installing core testing packages...${NC}"
pip install 'pytest>=7.0.0,<8.0.0' 'pytest-asyncio>=0.21.0,<0.23.0' 'pytest-playwright==0.4.0'
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install core testing packages. Exiting.${NC}"
    exit 1
fi
echo -e "${GREEN}Core testing packages installed${NC}"

# Install other requirements (skipping pytest and pytest-playwright)
echo -e "${YELLOW}Installing remaining dependencies...${NC}"
grep -v "pytest=\|pytest-playwright=\|pytest-asyncio=" requirements.txt > temp_requirements.txt
pip install -r temp_requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install remaining dependencies. Exiting.${NC}"
    rm temp_requirements.txt
    exit 1
fi
rm temp_requirements.txt
echo -e "${GREEN}All dependencies installed${NC}"

# Install Playwright browsers
echo -e "${YELLOW}Installing Playwright browsers...${NC}"
python -m playwright install --with-deps
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install Playwright browsers. Exiting.${NC}"
    exit 1
fi
echo -e "${GREEN}Playwright browsers installed${NC}"

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}All dependencies installed successfully${NC}"
echo -e "${GREEN}==========================================${NC}"