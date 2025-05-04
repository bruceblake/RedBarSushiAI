#!/bin/bash
# Script to run just the voice flow tests

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print banner
echo -e "${YELLOW}==============================================${NC}"
echo -e "${YELLOW}  Red Bar Sushi AI - Voice Flow E2E Tests  ${NC}"
echo -e "${YELLOW}==============================================${NC}"

# Set environment variables
export BASE_URL=${BASE_URL:-"https://redbarsushiai-staging.onrender.com"}
export TESTING=true
export PYTHONPATH=$(pwd)

echo -e "${YELLOW}Test environment:${NC}"
echo -e "BASE_URL: ${BASE_URL}"
echo ""

# First run just the homepage test
echo -e "${YELLOW}Running basic homepage test...${NC}"
python -m pytest tests/e2e/test_voice_flow.py::test_homepage_responds_with_twiml -v

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Basic homepage test passed!${NC}"
    
    # Run the more complete voice flow tests
    echo -e "\n${YELLOW}Running complete voice flow test...${NC}"
    python -m pytest tests/e2e/test_voice_flow.py::test_complete_voice_order_flow -v
    
    echo -e "\n${YELLOW}Running silence handling test...${NC}"
    python -m pytest tests/e2e/test_voice_flow.py::test_voice_silence_handling_flow -v
    
    echo -e "\n${YELLOW}Running menu query test...${NC}"
    python -m pytest tests/e2e/test_voice_flow.py::test_voice_menu_query_flow -v
    
    # Run all tests together if needed
    # echo -e "\n${YELLOW}Running all voice flow tests together...${NC}"
    # python -m pytest tests/e2e/test_voice_flow.py -v
else
    echo -e "${RED}❌ Basic homepage test failed!${NC}"
    echo -e "${YELLOW}Please fix the basic test first before trying the more complex tests.${NC}"
    exit 1
fi

echo -e "\n${GREEN}==============================================${NC}"
echo -e "${GREEN}Voice tests completed!${NC}"
echo -e "${GREEN}==============================================${NC}"