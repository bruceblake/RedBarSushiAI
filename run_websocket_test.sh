#!/bin/bash
# Script to test WebSocket connectivity with OpenAI

echo "===== Testing WebSocket Connectivity ====="

# Check if websockets package is installed
if ! python -c "import websockets" 2>/dev/null; then
    echo "❌ websockets package not installed"
    echo "Installing websockets package..."
    pip install websockets || {
        echo "❌ Failed to install websockets. Creating virtual environment..."
        python -m venv ws_test_env
        source ws_test_env/bin/activate
        pip install websockets
    }
fi

# Run the WebSocket test script
echo "Running WebSocket test script..."
python test_websocket.py

# Check the result
if [ $? -eq 0 ]; then
    echo "✅ WebSocket test passed! Your OpenAI API key works with Realtime API"
    echo "Your environment should be properly set up to use WebSockets."
else
    echo "❌ WebSocket test failed!"
    echo "Please make sure your OpenAI API key is correct and has access to the Realtime API."
    echo "Check your .env.development file to ensure the OPENAI_API_KEY is properly set."
fi