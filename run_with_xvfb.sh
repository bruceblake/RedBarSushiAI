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

# Start Xvfb with better display selection
echo "Starting virtual X server..."

# Try different display numbers in case some are already in use
for display_num in 1 2 99 0 3 4 5; do
    echo "Trying display :${display_num}..."
    
    # Check if this display is already in use
    if [ -e "/tmp/.X${display_num}-lock" ]; then
        echo "Display :${display_num} is already in use (lock file exists)"
        continue
    fi

    # Start Xvfb on this display
    Xvfb :${display_num} -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
    XVFB_PID=$!
    
    # Wait a moment for it to start
    sleep 2
    
    # Set the display variable
    export DISPLAY=:${display_num}
    
    # Test if it's working
    if xdpyinfo &>/dev/null; then
        echo "✅ Successfully started Xvfb on display :${display_num}"
        break
    else
        echo "❌ Failed to use display :${display_num}"
        kill $XVFB_PID 2>/dev/null || true
        unset XVFB_PID
    fi
done

# Check if we successfully started Xvfb
if [ -z "$XVFB_PID" ]; then
    echo "❌ Failed to start Xvfb on any display. Will continue in headless mode."
    export USE_XVFB=false
    export OPENAI_REALTIME_NO_DISPLAY=1
else
    echo "🖥️ Using virtual X display: $DISPLAY"
fi

# Make sure we have xdpyinfo to test the X server
if ! command -v xdpyinfo &> /dev/null; then
    echo "xdpyinfo not found, installing x11-utils..."
    apt-get update -y && apt-get install -y x11-utils
fi

# Configure environment based on X11 status
if [ -n "$XVFB_PID" ] && xdpyinfo &>/dev/null; then
    echo "✅ X server is running and accessible at DISPLAY=$DISPLAY"
    
    # Configure environment for X11
    export USE_XVFB=true
    export OPENAI_REALTIME_NO_DISPLAY=0
    export X11_SETUP_SUCCESS=true
    export PYNPUT_HEADLESS=0
    export NO_X11=0
    export HEADLESS=0
else
    echo "❌ X server connection failed. Will continue in headless mode."
    export USE_XVFB=false
    export OPENAI_REALTIME_NO_DISPLAY=1
    export X11_SETUP_SUCCESS=false
    export PYNPUT_HEADLESS=1
    export NO_X11=1
    export HEADLESS=1
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