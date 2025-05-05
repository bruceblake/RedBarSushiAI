#!/bin/bash
# Fix Docker environment issues for RedBarSushiAI

set -e

echo "=========================================================="
echo "      RedBarSushiAI Docker Environment Fix Script"
echo "=========================================================="

# Get directory of script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Step 1: Fix Redis connection
echo -e "\n[1/3] 🔄 Fixing Redis connection..."
python "$SCRIPT_DIR/fix_redis_connection.py"

if [ $? -eq 0 ]; then
    echo "✅ Redis connection fix completed successfully"
else
    echo "⚠️ Redis connection fix may have encountered issues"
fi

# Step 2: Fix X11 display
echo -e "\n[2/3] 🔄 Fixing X11 display configuration..."
python "$SCRIPT_DIR/fix_docker_x11.py"

if [ $? -eq 0 ]; then
    echo "✅ X11 display fix completed successfully"
else
    echo "⚠️ X11 display fix may have encountered issues - falling back to headless mode"
fi

# Step 3: Set up OpenAI Realtime client
echo -e "\n[3/3] 🔄 Setting up OpenAI Realtime client..."
python "$SCRIPT_DIR/setup_openai_realtime.py"

if [ $? -eq 0 ]; then
    echo "✅ OpenAI Realtime client setup completed successfully"
else
    echo "⚠️ OpenAI Realtime client setup may have encountered issues"
fi

# Final status
echo -e "\n=========================================================="
echo "              Environment Fix Completed"
echo "==========================================================\n"

# Set environment variables for immediate use
echo "Setting up environment variables for the current session..."

# Redis environment variables
if [ -f "/tmp/redis_env.sh" ]; then
    source "/tmp/redis_env.sh"
    echo "✅ Redis environment variables loaded"
fi

# X11 environment variables
if [ -f "/tmp/x11_env.sh" ]; then
    source "/tmp/x11_env.sh"
    echo "✅ X11 environment variables loaded"
elif [ -f "/tmp/headless_env.sh" ]; then
    source "/tmp/headless_env.sh"
    echo "✅ Headless mode environment variables loaded"
fi

# Start services if needed
if [ -f "/usr/local/bin/start-xvfb.sh" ]; then
    echo "Starting Xvfb..."
    /usr/local/bin/start-xvfb.sh
    echo "✅ Xvfb started"
fi

# Final instructions
echo -e "\nTo use the fixed environment, please restart your application or run:"
echo "source ~/.bashrc"
echo -e "\nYou can also run the diagnostic script to verify the fixes:"
echo "python diagnose.py"

echo -e "\n✨ Fix completed. Happy coding with RedBarSushiAI! ✨"