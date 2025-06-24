#!/bin/bash

# E2E Test Runner for RedBarSushiAI
# This script runs E2E tests with proper configuration for ngrok/ConversationRelay

echo "🚀 RedBarSushiAI E2E Test Runner"
echo "================================"

# Check if ngrok URL is provided
if [ -n "$1" ]; then
    export NGROK_URL="$1"
    echo "📍 Using provided ngrok URL: $NGROK_URL"
else
    # Check if ngrok is already set in environment
    if [ -n "$NGROK_URL" ]; then
        echo "📍 Using ngrok URL from environment: $NGROK_URL"
    else
        echo "📍 No ngrok URL provided, using localhost"
        export NGROK_URL="http://localhost:8000"
        export USE_NGROK="false"
    fi
fi

# Set test environment
export TESTING=1
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo ""
echo "🧪 Running ConversationRelay E2E Tests..."
echo "========================================="

# Run the new ConversationRelay E2E test
echo ""
echo "1️⃣ Testing ConversationRelay Integration..."
python -m pytest tests/e2e/test_conversation_relay_e2e.py -v -s

# Check if we should run additional E2E tests
if [ "$2" == "--all" ]; then
    echo ""
    echo "2️⃣ Running Additional E2E Tests..."
    
    # Run other E2E tests that might work
    echo "Testing live ngrok endpoints..."
    python -m pytest tests/e2e/test_live_ngrok.py -v -s -k "not websocket"
    
    echo ""
    echo "Testing working endpoints..."
    python -m pytest tests/e2e/test_working_endpoints.py -v -s
fi

echo ""
echo "✅ E2E tests completed!"
echo ""
echo "📝 Usage Tips:"
echo "  - Run with ngrok URL: ./run_e2e_tests.sh https://your-ngrok-url.ngrok-free.app"
echo "  - Run all tests: ./run_e2e_tests.sh https://your-ngrok-url.ngrok-free.app --all"
echo "  - Run locally: ./run_e2e_tests.sh"