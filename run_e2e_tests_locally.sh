#!/bin/bash
# Simple script to run E2E tests against the staging environment

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print banner
echo -e "${YELLOW}==============================================${NC}"
echo -e "${YELLOW}  Red Bar Sushi AI - E2E Tests for Staging  ${NC}"
echo -e "${YELLOW}==============================================${NC}"

# Set environment variables
export BASE_URL=${BASE_URL:-"https://redbarsushiai-staging.onrender.com"}
export TESTING=true
export PYTHONPATH=$(pwd)

echo -e "${YELLOW}Test environment:${NC}"
echo -e "BASE_URL: ${BASE_URL}"
echo -e "PYTHONPATH: ${PYTHONPATH}"
echo ""

# Run simplified endpoint tests
echo -e "${YELLOW}Running simplified endpoint tests...${NC}"
python -m pytest tests/e2e/test_simple_endpoints.py -v

SIMPLE_RESULT=$?

if [ $SIMPLE_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Simplified endpoint tests passed!${NC}"
    
    # Run the more complex voice flow tests
    echo -e "\n${YELLOW}Running voice flow tests...${NC}"
    python -m pytest tests/e2e/test_voice_flow.py -v
    
    VOICE_RESULT=$?
    
    if [ $VOICE_RESULT -eq 0 ]; then
        echo -e "${GREEN}✅ Voice flow tests passed!${NC}"
    else
        echo -e "${RED}❌ Voice flow tests failed.${NC}"
        echo -e "${YELLOW}This is expected if the staging environment isn't fully configured.${NC}"
    fi
else
    echo -e "${RED}❌ Simplified endpoint tests failed!${NC}"
    echo -e "${YELLOW}Fix these basic tests first before attempting more complex tests.${NC}"
    exit $SIMPLE_RESULT
fi

echo -e "\n${YELLOW}==============================================${NC}"
echo -e "E2E Test Run Complete!"
echo -e "${YELLOW}==============================================${NC}"