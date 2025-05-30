#!/bin/bash
# Script to run tests in watch mode for development

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}👁️  Starting test watcher...${NC}"
echo "================================"
echo "Press Ctrl+C to stop"
echo ""

# Check if pytest-watch is installed
if ! python -c "import pytest_watch" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-watch...${NC}"
    pip install pytest-watch
fi

# Default to watching unit tests for speed
WATCH_PATH=${1:-tests/unit}
shift || true

# Skip health check for unit tests
if [[ "$WATCH_PATH" == *"unit"* ]]; then
    export SKIP_HEALTH_CHECK=true
fi

echo -e "${GREEN}Watching: $WATCH_PATH${NC}"
echo ""

# Run pytest-watch with appropriate options
ptw "$WATCH_PATH" \
    --runner "pytest" \
    --clear \
    -- \
    -v \
    --color=yes \
    --tb=short \
    --no-cov \
    "$@"