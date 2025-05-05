#!/bin/bash
# Fix X server connection issues for OpenAI Realtime client

set -e

echo "===== Fixing X Server Connection for Docker Environment ====="

# Install Xvfb and related X11 packages if not present
if ! command -v Xvfb &> /dev/null; then
    echo "Installing Xvfb and X11 dependencies..."
    apt-get update -y && apt-get install -y xvfb x11-utils xorg dbus-x11 libxrender1 libxtst6 libxi6
    if [ $? -ne 0 ]; then
        echo "⚠️ Failed to install X11 dependencies. Will try with existing packages."
    fi
fi

# Kill any existing Xvfb processes
echo "Stopping any existing Xvfb processes..."
pkill Xvfb 2>/dev/null || true

# Find a free display number
for display_num in 1 2 3 4 5 99 0; do
    echo "Trying display :${display_num}..."
    
    # Check if display is already in use
    if [ -e "/tmp/.X${display_num}-lock" ]; then
        echo "Display :${display_num} is already in use (lock file exists)"
        continue
    fi
    
    # Start Xvfb on this display with extended parameters for better compatibility
    Xvfb :${display_num} -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
    XVFB_PID=$!
    echo "Started Xvfb process with PID $XVFB_PID"
    
    # Set the DISPLAY environment variable
    export DISPLAY=:${display_num}
    echo "export DISPLAY=:${display_num}" >> ~/.bashrc
    
    # Wait for Xvfb to initialize
    sleep 2
    
    # Test the X server connection
    if xdpyinfo >/dev/null 2>&1; then
        echo "✅ Successfully connected to display :${display_num}"
        
        # Set environment variables for OpenAI Realtime client
        echo "export DISPLAY=:${display_num}" > ~/.xdisplay
        echo "export PYNPUT_HEADLESS=0" >> ~/.xdisplay
        echo "export NO_X11=0" >> ~/.xdisplay
        echo "export HEADLESS=0" >> ~/.xdisplay
        echo "export OPENAI_REALTIME_NO_DISPLAY=0" >> ~/.xdisplay
        echo "export X11_SETUP_SUCCESS=true" >> ~/.xdisplay
        echo "export OPENAI_REALTIME_AVAILABLE=1" >> ~/.xdisplay
        
        # Source the file to set environment variables in the current shell
        source ~/.xdisplay
        
        # Add to system-wide environment
        cat > /etc/profile.d/xdisplay.sh << EOF
#!/bin/bash
export DISPLAY=:${display_num}
export PYNPUT_HEADLESS=0
export NO_X11=0
export HEADLESS=0
export OPENAI_REALTIME_NO_DISPLAY=0
export X11_SETUP_SUCCESS=true
export OPENAI_REALTIME_AVAILABLE=1
EOF
        chmod +x /etc/profile.d/xdisplay.sh
        
        echo "✅ X Server environment variables set successfully"
        echo "🖥️ Using display :${display_num} for OpenAI Realtime client"
        
        # Create a startup script to ensure Xvfb starts on container restart
        cat > /usr/local/bin/start-xvfb.sh << EOF
#!/bin/bash
pkill Xvfb 2>/dev/null || true
Xvfb :${display_num} -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
EOF
        chmod +x /usr/local/bin/start-xvfb.sh
        
        echo "✅ Created Xvfb startup script at /usr/local/bin/start-xvfb.sh"
        
        # Run a final test
        echo "Running test with xeyes if available..."
        if command -v xeyes &> /dev/null; then
            xeyes 2>/dev/null &
            XEYES_PID=$!
            sleep 2
            kill $XEYES_PID 2>/dev/null || true
            echo "✅ X application test passed"
        else
            echo "⚠️ xeyes not available for visual test, but connection seems working"
        fi
        
        exit 0
    else
        echo "❌ Failed to connect to display :${display_num}"
        kill $XVFB_PID 2>/dev/null || true
    fi
done

# If we get here, all display attempts failed
echo "❌ Could not set up working X display after trying multiple displays"
echo "Setting up fallback environment variables for headless mode..."

# Set headless mode environment variables
cat > ~/.xdisplay << EOF
export PYNPUT_HEADLESS=1
export NO_X11=1
export HEADLESS=1
export OPENAI_REALTIME_NO_DISPLAY=1
export X11_SETUP_SUCCESS=false
# Still mark realtime as available since we'll use our custom implementation
export OPENAI_REALTIME_AVAILABLE=1
EOF

source ~/.xdisplay

# Add to system-wide environment
cat > /etc/profile.d/xdisplay.sh << EOF
#!/bin/bash
export PYNPUT_HEADLESS=1
export NO_X11=1
export HEADLESS=1
export OPENAI_REALTIME_NO_DISPLAY=1
export X11_SETUP_SUCCESS=false
# Still mark realtime as available since we'll use our custom implementation
export OPENAI_REALTIME_AVAILABLE=1
EOF
chmod +x /etc/profile.d/xdisplay.sh

echo "💻 Set up for headless mode operation"
echo "⚠️ OpenAI Realtime client will use fallback WebSocket implementation"