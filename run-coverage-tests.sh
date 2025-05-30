#!/bin/bash
# Script to run tests with detailed coverage analysis

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "📊 Running tests with coverage analysis"
echo "====================================="

# Ensure coverage is enabled
export COVERAGE=true

# Run all tests with coverage
"$SCRIPT_DIR/run-tests.sh" all "$@"

# Open coverage report if available
if [ -f "htmlcov/index.html" ]; then
    echo ""
    echo "📊 Opening coverage report in browser..."
    
    # Try to open in browser based on OS
    if command -v xdg-open > /dev/null; then
        xdg-open htmlcov/index.html
    elif command -v open > /dev/null; then
        open htmlcov/index.html
    elif command -v start > /dev/null; then
        start htmlcov/index.html
    else
        echo "Please open htmlcov/index.html in your browser"
    fi
fi