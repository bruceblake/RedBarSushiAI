#!/bin/bash
# Quick script to run unit tests

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Unit tests don't need services, so skip health check
export SKIP_HEALTH_CHECK=true

# Run unit tests with appropriate options
exec "$SCRIPT_DIR/run-tests.sh" unit "$@"