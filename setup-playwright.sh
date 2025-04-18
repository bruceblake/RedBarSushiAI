#!/bin/bash
# Script to install and verify Playwright
# Works on both Ubuntu (GitHub Actions) and Arch Linux

# Constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}RedBarSushiAI Playwright Setup${NC}"
echo -e "${BOLD}===========================================${NC}"

# Detect OS
if [ -f /etc/arch-release ]; then
    OS="arch"
    echo -e "${BLUE}Detected Arch Linux${NC}"
elif [ -f /etc/lsb-release ] && grep -q "Ubuntu" /etc/lsb-release; then
    OS="ubuntu"
    echo -e "${BLUE}Detected Ubuntu${NC}"
else
    OS="unknown"
    echo -e "${YELLOW}Unknown OS, assuming Ubuntu-compatible${NC}"
    OS="ubuntu"
fi

# Install system dependencies
if [ "$OS" = "ubuntu" ]; then
    echo -e "${YELLOW}Installing system dependencies for Ubuntu...${NC}"
    sudo apt-get update
    sudo apt-get install -y xvfb libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm-dev libasound2 python3-venv
elif [ "$OS" = "arch" ]; then
    echo -e "${YELLOW}Installing system dependencies for Arch Linux...${NC}"
    sudo pacman -Sy --noconfirm xorg-server-xvfb mesa libcups nss at-spi2-core \
        alsa-lib xorg-server-xvfb libxss libxrandr 
fi

# Create and activate virtual environment (if not already in one)
if [ -z "$VIRTUAL_ENV" ]; then
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python -m venv venv
    fi
    
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

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
python -m playwright install-deps chromium 2>/dev/null || true

# Create directories
mkdir -p screenshots
mkdir -p tests/e2e/test-data

# Run verification script
echo -e "${YELLOW}Verifying Playwright installation...${NC}"
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
python verify-playwright.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Playwright setup completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Playwright setup verification failed${NC}"
    exit 1
fi