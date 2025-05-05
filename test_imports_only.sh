#!/bin/bash

# Simple script to test just the imports without requiring a full Flask app

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}     REFACTORED IMPORTS TEST       ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Add the current directory to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run the simplified test
echo -e "\n${YELLOW}Running import tests...${NC}"
python test_refactored_imports.py

exit_code=$?

# Summary
echo -e "\n${YELLOW}====================================${NC}"
echo -e "${YELLOW}             TEST SUMMARY           ${NC}"
echo -e "${YELLOW}====================================${NC}"

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✅ All import tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some import tests failed!${NC}"
    echo -e "${YELLOW}Recommendations:${NC}"
    echo -e "1. Check for missing dependencies"
    echo -e "2. Look for circular imports"
    echo -e "3. Ensure all modules can be imported individually"
    echo -e "4. Fix any import errors before pushing to GitHub"
    exit 1
fi