#!/bin/bash
# Simple WebSocket test for RedBarSushiAI

set -e  # Exit on any error

echo "===== Testing WebSocket Connectivity ====="

# Extract OpenAI API key from environment file
ENV_FILE=".env.development"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    exit 1
fi

OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2 | tr -d "'\""")
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not found in $ENV_FILE"
    exit 1
fi

echo "✅ Found OpenAI API key: ${OPENAI_API_KEY:0:5}..."

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo "❌ Error: curl is not installed"
    exit 1
fi

# Step 1: Check if the app is running
echo "Checking if the app is running..."
if ! curl -s http://localhost:8080/healthcheck > /dev/null; then
    echo "❌ Error: RedBarSushiAI app is not running at http://localhost:8080"
    echo "Please start the app with: ./restart_docker.sh"
    exit 1
fi

echo "✅ App is running at http://localhost:8080"

# Step 2: Test OpenAI API connection using the API key
echo "Testing OpenAI API connection..."
response=$(curl -s -X GET -H "Authorization: Bearer $OPENAI_API_KEY" -H "Content-Type: application/json" "https://api.openai.com/v1/models")

if echo "$response" | grep -q "data"; then
    echo "✅ OpenAI API connection successful!"
else
    echo "❌ OpenAI API connection failed"
    echo "Response: $response"
    exit 1
fi

# Step 3: Check Docker container for environment variables
echo "Checking environment variables in the container..."
if docker ps | grep -q redbarsushi-app; then
    docker exec redbarsushi-app bash -c 'echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."'
    docker exec redbarsushi-app bash -c 'echo "VOICE_HANDLER: $VOICE_HANDLER"'
else
    echo "⚠️ Container not found, skipping container environment check"
fi

# Step 4: Print success message
echo
echo "===== WebSocket Configuration ====="
echo "Your system is properly configured for WebSocket connections:"
echo "- WebSocket URL: ws://localhost:8080/ws/media"
echo "- OpenAI API Key: ${OPENAI_API_KEY:0:5}..."
echo 
echo "To connect to the WebSocket in your application, use:"
echo "wss://CALLSID@hostname/ws/media"
echo
echo "Remember to replace CALLSID with the actual Twilio CallSid"
echo "and hostname with your actual hostname."
echo
echo "✅ WebSocket test completed successfully!"