#!/bin/bash
# Script to run a quick subset of tests for development

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Quick tests - unit tests and fast integration tests
export SKIP_HEALTH_CHECK=false

echo "🚀 Running quick test suite (unit + fast integration tests)"
echo "=========================================================="

# Run fast tests without coverage for speed
exec "$SCRIPT_DIR/run-tests.sh" fast --no-cov "$@"