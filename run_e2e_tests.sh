#!/bin/bash
set -e

# This script runs end-to-end tests with proper environment setup

echo "=== Setting up environment for E2E tests ==="
echo "============================================"

# Install all dependencies first
echo "Installing all dependencies..."
./install_all_dependencies.sh

# Set environment variables for testing
export TESTING=True
export FLASK_ENV=testing
export IS_STAGING=true
export BASE_URL=${BASE_URL:-"https://redbarsushi-staging.onrender.com"}
export HEADLESS=1
export FORCE_HEADLESS=true
export PYNPUT_HEADLESS=1
export NO_X11=1
export OPENAI_REALTIME_NO_DISPLAY=1

# Start the tests
echo "Running E2E tests against $BASE_URL..."
pytest tests/e2e -v

echo "=== E2E tests completed successfully! ==="