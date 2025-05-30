#!/bin/bash
# Script to run integration tests with proper service setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Integration tests need services
export SKIP_HEALTH_CHECK=false

# Run integration tests
exec "$SCRIPT_DIR/run-tests.sh" integration "$@"