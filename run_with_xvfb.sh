#!/bin/bash
# Script to run the application with a virtual X server (Xvfb)
# This helps the OpenAI Realtime client which requires an X display

# Set up Xvfb display
echo "Setting up virtual X display with Xvfb..."

# Install Xvfb if not present
if ! command -v Xvfb &> /dev/null; then
    echo "Xvfb not found. Installing Xvfb and X11 dependencies..."
    apt-get update -y && apt-get install -y xvfb x11-utils xorg libxrender1 libxtst6 libxi6 dbus-x11
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Xvfb. Will continue but OpenAI Realtime client may not work."
    fi
fi

# Kill any existing Xvfb processes
pkill Xvfb 2>/dev/null || true

# Start Xvfb with improved options
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Export display setting
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Test if Xvfb is working
if ! command -v xdpyinfo &> /dev/null; then
    echo "xdpyinfo not found, installing x11-utils..."
    apt-get update -y && apt-get install -y x11-utils
fi

# Test the X server connection
xdpyinfo &>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ X server is running and accessible at DISPLAY=:99"
    
    # Configure environment for X11
    export USE_XVFB=true
    export OPENAI_REALTIME_NO_DISPLAY=0
else
    echo "❌ X server connection failed. Will continue but OpenAI Realtime client may not work."
fi

# Create a function to clean up Xvfb on exit
cleanup() {
    echo "Cleaning up Xvfb process..."
    if [ -n "$XVFB_PID" ]; then
        kill $XVFB_PID 2>/dev/null || true
    fi
    exit
}

# Set up trap for cleanup
trap cleanup EXIT INT TERM

# Run the test script to verify everything is working
echo "Running test script to verify setup..."
python test_realtime_client.py

echo ""
echo "Starting application with Xvfb support..."
echo "Press Ctrl+C to stop the application"
echo ""

# Start the application
python run.py