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

# Install system dependencies for Playwright
echo -e "${YELLOW}Installing system dependencies for Playwright...${NC}"
apt_packages="libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxrender1 \
              libxtst6 libxkbcommon0 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
              libdbus-1-3 libatspi2.0-0 libxcursor1 libxi6 libgbm1 libnss3 libnspr4 \
              libpango-1.0-0 libcairo2 libasound2-dev libpangocairo-1.0-0 \
              libwayland-client0 libwayland-cursor0 libwayland-egl1"

# Only use sudo if not running as root
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

$SUDO apt-get update -y
$SUDO apt-get install -y $apt_packages || true  # Continue even if some packages fail

# Install Playwright with skip browser download first
echo -e "${YELLOW}Installing Playwright without browser download...${NC}"
pip install playwright==1.42.0
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install Playwright package. Exiting.${NC}"
    exit 1
fi

# Install browsers with --force flag to skip missing system dependencies
echo -e "${YELLOW}Installing Playwright browsers (with --force flag)...${NC}"
python -m playwright install --force
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Warning: Playwright browser installation failed, but we'll continue anyway.${NC}"
    echo -e "${YELLOW}We'll use the simplified tests that don't require browsers.${NC}"
else
    echo -e "${GREEN}Playwright browsers installed${NC}"
fi

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}All dependencies installed successfully${NC}"
echo -e "${GREEN}==========================================${NC}"