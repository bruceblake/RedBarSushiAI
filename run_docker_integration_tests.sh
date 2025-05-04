#!/bin/bash
# Run integration tests using Docker containers

# Set execution flags
set -e

# Directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

# Define colored output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Display header
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}   RedBarSushiAI Docker Integration Tests  ${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# Accept command-line flags for non-interactive mode
INTERACTIVE=true
STOP_CONTAINERS=false

while getopts ":ns" opt; do
  case ${opt} in
    n )
      INTERACTIVE=false
      ;;
    s )
      STOP_CONTAINERS=true
      ;;
    \? )
      echo "Usage: $0 [-n] [-s] [test_file]"
      echo "  -n  Non-interactive mode"
      echo "  -s  Stop containers after tests"
      exit 1
      ;;
  esac
done
shift $((OPTIND -1))

# Ensure Docker containers are running
echo -e "${YELLOW}Ensuring Docker containers are running...${NC}"
docker-compose -f tests/docker-compose-test.yml up -d

# Wait for containers to be healthy
echo -e "${YELLOW}Waiting for containers to be healthy...${NC}"
sleep 3

# Check if the containers are healthy
POSTGRES_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' tests-postgres-test-1 2>/dev/null || echo "not running")
REDIS_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' tests-redis-test-1 2>/dev/null || echo "not running")

if [ "$POSTGRES_HEALTH" != "healthy" ] || [ "$REDIS_HEALTH" != "healthy" ]; then
    echo -e "${RED}Containers are not healthy. Please check docker logs.${NC}"
    echo -e "PostgreSQL: $POSTGRES_HEALTH, Redis: $REDIS_HEALTH"
    
    # Give containers more time to become healthy
    echo -e "${YELLOW}Waiting 10 more seconds for containers to become healthy...${NC}"
    sleep 10
    
    # Check again
    POSTGRES_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' tests-postgres-test-1 2>/dev/null || echo "not running")
    REDIS_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' tests-redis-test-1 2>/dev/null || echo "not running")
    
    if [ "$POSTGRES_HEALTH" != "healthy" ] || [ "$REDIS_HEALTH" != "healthy" ]; then
        echo -e "${RED}Containers still not healthy after waiting. Exiting.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}All containers are healthy!${NC}"

# Set environment variables for tests
export TEST_MODE=docker
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_redbarsushi"
export TEST_REDIS_URL="redis://localhost:6379/0"

# Run the integration tests
echo -e "${YELLOW}Running integration tests...${NC}"

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements if needed
if [ ! -f "venv/.requirements_installed" ]; then
    echo -e "${YELLOW}Installing requirements...${NC}"
    
    # Install PostgreSQL dev packages if needed (for CI environments)
    if [ "$CI" = "true" ]; then
        echo -e "${YELLOW}CI environment detected. Installing PostgreSQL dependencies...${NC}"
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y libpq-dev
        fi
    fi
    
    # Install psycopg2-binary separately first to avoid build issues
    pip install --no-build-isolation psycopg2-binary==2.9.9
    
    # Then install the rest
    pip install -r requirements.txt
    
    # Mark as installed
    touch venv/.requirements_installed
fi

# Determine which tests to run
TEST_EXIT_CODE=0
if [ -z "$1" ]; then
    # Run all integration tests if no argument is provided
    echo -e "${YELLOW}Running all integration tests...${NC}"
    python -m pytest tests/integration/ -v || TEST_EXIT_CODE=$?
else
    # Run specific test if argument is provided
    echo -e "${YELLOW}Running specific test: $1...${NC}"
    python -m pytest tests/integration/$1 -v || TEST_EXIT_CODE=$?
fi

# Display completion message
echo -e "${BLUE}==========================================${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Integration tests completed successfully!${NC}"
else
    echo -e "${RED}Integration tests failed with exit code: $TEST_EXIT_CODE${NC}"
fi
echo -e "${BLUE}==========================================${NC}"

# Check if we should stop containers
if [ "$INTERACTIVE" = true ]; then
    # Ask if containers should be stopped in interactive mode
    read -p "Do you want to stop the test containers? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        STOP_CONTAINERS=true
    fi
fi

if [ "$STOP_CONTAINERS" = true ]; then
    echo -e "${YELLOW}Stopping containers...${NC}"
    docker-compose -f tests/docker-compose-test.yml down
    echo -e "${GREEN}Containers stopped.${NC}"
fi

exit $TEST_EXIT_CODE