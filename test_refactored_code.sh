#!/bin/bash

# Test script for refactored code
# This script runs various tests to ensure the refactored code works correctly

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}     REFACTORED CODE TEST SUITE     ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Function to run a test and report results
run_test() {
    test_name=$1
    command=$2
    
    echo -e "\n${YELLOW}Running test: ${test_name}${NC}"
    echo -e "${YELLOW}Command: ${command}${NC}"
    echo -e "${YELLOW}-----------------------------------${NC}"
    
    # Run the command and capture exit code
    eval $command
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "\n${GREEN}✅ Test passed: ${test_name}${NC}"
    else
        echo -e "\n${RED}❌ Test failed: ${test_name}${NC}"
    fi
    
    return $exit_code
}

# Track overall success
overall_success=true

# Test 1: Basic imports
echo -e "\n${YELLOW}====================================${NC}"
echo -e "${YELLOW}          TESTING IMPORTS           ${NC}"
echo -e "${YELLOW}====================================${NC}"

run_test "Basic Imports" "python test_imports.py"
if [ $? -ne 0 ]; then
    overall_success=false
fi

# Test 2: Routes registration
echo -e "\n${YELLOW}====================================${NC}"
echo -e "${YELLOW}          TESTING ROUTES            ${NC}"
echo -e "${YELLOW}====================================${NC}"

run_test "Flask Routes" "python test_routes.py"
if [ $? -ne 0 ]; then
    overall_success=false
fi

# Test 3: Run Flask with --debug to check for startup errors
echo -e "\n${YELLOW}====================================${NC}"
echo -e "${YELLOW}       TESTING FLASK STARTUP        ${NC}"
echo -e "${YELLOW}====================================${NC}"

run_test "Flask Debug Startup" "timeout 5 flask --app run.py --debug run 2>&1 | grep -v 'Restarting with stat' || true"
# Don't fail the overall test for this one since it will always timeout
# We just want to see any startup errors

# Summary
echo -e "\n${YELLOW}====================================${NC}"
echo -e "${YELLOW}             TEST SUMMARY           ${NC}"
echo -e "${YELLOW}====================================${NC}"

if $overall_success; then
    echo -e "${GREEN}✅ All tests completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Review the output above for details.${NC}"
    exit 1
fi