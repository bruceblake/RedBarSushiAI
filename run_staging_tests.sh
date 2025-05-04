#!/bin/bash
# Script to run tests against the staging environment

# Activate virtual environment
source venv/bin/activate

# Set required environment variables
export BASE_URL=https://redbarsushiai-staging.onrender.com
export TESTING=true
export SKIP_DB_INIT=true
export SKIP_DB_SETUP=true
export TEST_MODE=staging
export HEADLESS=1
export PYNPUT_HEADLESS=1
export NO_X11=1
export OPENAI_REALTIME_NO_DISPLAY=1

# Define test categories
if [ "$1" == "" ]; then
    # If no argument provided, run basic tests
    TEST_PATH="test_staging.py"
else
    # Use provided argument as test path
    TEST_PATH="$1"
fi

# Run the tests
echo "Running tests: $TEST_PATH"
python $TEST_PATH

# Return the exit code
exit $?