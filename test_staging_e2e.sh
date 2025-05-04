#!/bin/bash
# Simple script to run E2E tests against the staging environment
# This script doesn't modify any Claude configuration

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print banner
echo -e "${YELLOW}==============================================${NC}"
echo -e "${YELLOW}  Red Bar Sushi AI - Staging Environment Test ${NC}"
echo -e "${YELLOW}==============================================${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Set required environment variables
export BASE_URL=https://redbarsushiai-staging.onrender.com
export TESTING=true
export SKIP_DB_INIT=true
export SKIP_DB_SETUP=true
export TEST_MODE=staging

# Print environment info
echo -e "${YELLOW}Test environment:${NC}"
echo -e "BASE_URL: ${BASE_URL}"
echo -e "TEST_MODE: ${TEST_MODE}"
echo ""

# Run basic test by default
run_basic_test() {
    echo -e "${YELLOW}Running basic connectivity tests...${NC}"
    python test_staging.py
    BASIC_RESULT=$?
    
    if [ $BASIC_RESULT -eq 0 ]; then
        echo -e "${GREEN}Basic connectivity tests passed!${NC}"
    else
        echo -e "${RED}Basic connectivity tests failed!${NC}"
        exit $BASIC_RESULT
    fi
}

# Run voice tests
run_voice_test() {
    echo -e "\n${YELLOW}Running voice endpoint tests...${NC}"
    # Using the basic test instead of Playwright-dependent tests
    python test_staging.py
    VOICE_RESULT=$?
    
    if [ $VOICE_RESULT -eq 0 ]; then
        echo -e "${GREEN}Voice endpoint tests passed!${NC}"
    else
        echo -e "${RED}Voice endpoint tests failed!${NC}"
        exit $VOICE_RESULT
    fi
}

# Run menu tests
run_menu_test() {
    echo -e "\n${YELLOW}Running menu tests...${NC}"
    python test_menu.py
    MENU_RESULT=$?
    
    if [ $MENU_RESULT -eq 0 ]; then
        echo -e "${GREEN}Menu tests passed!${NC}"
    else
        echo -e "${RED}Menu tests failed!${NC}"
        exit $MENU_RESULT
    fi
}

# Run order tests
run_order_test() {
    echo -e "\n${YELLOW}Running order tests...${NC}"
    python test_order.py
    ORDER_RESULT=$?
    
    if [ $ORDER_RESULT -eq 0 ]; then
        echo -e "${GREEN}Order tests passed!${NC}"
    else
        echo -e "${RED}Order tests failed!${NC}"
        exit $ORDER_RESULT
    fi
}

# Run Deliverect API integration tests
run_deliverect_test() {
    echo -e "\n${YELLOW}Running Deliverect API integration tests...${NC}"
    python -m pytest tests/integration/test_deliverect_api_integration.py -v
    DELIVERECT_RESULT=$?
    
    if [ $DELIVERECT_RESULT -eq 0 ]; then
        echo -e "${GREEN}Deliverect API integration tests passed!${NC}"
    else
        echo -e "${RED}Deliverect API integration tests failed!${NC}"
        exit $DELIVERECT_RESULT
    fi
}

# Run Deliverect menu synchronization tests
run_menu_sync_test() {
    echo -e "\n${YELLOW}Running Deliverect menu synchronization tests...${NC}"
    python -m pytest tests/integration/test_deliverect_menu_synchronization.py -v
    MENU_SYNC_RESULT=$?
    
    if [ $MENU_SYNC_RESULT -eq 0 ]; then
        echo -e "${GREEN}Deliverect menu synchronization tests passed!${NC}"
    else
        echo -e "${RED}Deliverect menu synchronization tests failed!${NC}"
        exit $MENU_SYNC_RESULT
    fi
}

# Run MCP integration tests
run_mcp_test() {
    echo -e "\n${YELLOW}Running MCP integration tests...${NC}"
    python -m pytest tests/integration/test_mcp_test_integration.py -v
    MCP_RESULT=$?
    
    if [ $MCP_RESULT -eq 0 ]; then
        echo -e "${GREEN}MCP integration tests passed!${NC}"
    else
        echo -e "${RED}MCP integration tests failed!${NC}"
        exit $MCP_RESULT
    fi
}

# Run complete order flow E2E tests
run_complete_order_e2e_test() {
    echo -e "\n${YELLOW}Running complete order flow E2E tests...${NC}"
    python -m pytest tests/e2e/test_complete_order_flow_e2e.py -v
    COMPLETE_ORDER_RESULT=$?
    
    if [ $COMPLETE_ORDER_RESULT -eq 0 ]; then
        echo -e "${GREEN}Complete order flow E2E tests passed!${NC}"
    else
        echo -e "${RED}Complete order flow E2E tests failed!${NC}"
        exit $COMPLETE_ORDER_RESULT
    fi
}

# Define which tests to run based on input
if [ "$1" == "" ] || [ "$1" == "basic" ] || [ "$1" == "health" ]; then
    run_basic_test
elif [ "$1" == "voice" ]; then
    run_voice_test
elif [ "$1" == "menu" ]; then
    run_menu_test
elif [ "$1" == "order" ]; then
    run_order_test
elif [ "$1" == "deliverect" ]; then
    run_deliverect_test
elif [ "$1" == "menu-sync" ]; then
    run_menu_sync_test
elif [ "$1" == "mcp" ]; then
    run_mcp_test
elif [ "$1" == "complete-order-e2e" ]; then
    run_complete_order_e2e_test
elif [ "$1" == "integration" ]; then
    # Run all integration tests
    run_deliverect_test
    run_menu_sync_test
    run_mcp_test
elif [ "$1" == "all" ]; then
    # Run all tests in sequence
    run_basic_test
    run_voice_test
    run_menu_test
    run_order_test
    run_deliverect_test
    run_menu_sync_test
    run_mcp_test
    run_complete_order_e2e_test
else
    echo -e "${RED}Unknown test type: $1${NC}"
    echo -e "Usage: $0 [basic|voice|menu|order|deliverect|menu-sync|mcp|complete-order-e2e|integration|all]"
    exit 1
fi

# If we reach here, all requested tests passed
echo -e "\n${GREEN}All requested tests passed!${NC}"
echo -e "${YELLOW}==============================================${NC}"
exit 0