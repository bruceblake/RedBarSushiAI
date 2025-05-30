#!/bin/bash
# Script to run end-to-end tests with full environment

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# E2E tests need all services and extended timeouts
export SKIP_HEALTH_CHECK=false
export PYTEST_TIMEOUT=600  # 10 minutes for E2E tests

# Run E2E tests with extended timeout
exec "$SCRIPT_DIR/run-tests.sh" e2e "$@"