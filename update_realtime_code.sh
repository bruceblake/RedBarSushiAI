#!/bin/bash
# Script to update the OpenAI Realtime client code

echo "===== Updating OpenAI Realtime Client Code ====="

# Step 1: Making a backup of the original file
if [ -f app/api/voice/realtime.py ]; then
    echo "Step 1: Making a backup of the original realtime.py..."
    cp app/api/voice/realtime.py app/api/voice/realtime.py.bak
    echo "✅ Backup created as app/api/voice/realtime.py.bak"
else
    echo "Step 1: Original file app/api/voice/realtime.py not found, skipping backup"
fi

# Step 2: Replacing the file with the fixed version
echo "Step 2: Replacing realtime.py with the fixed version..."
cp app/api/voice/realtime_fixed.py app/api/voice/realtime.py
echo "✅ Fixed version installed"

echo
echo "===== OpenAI Realtime Client Code Updated ====="
echo "The RealtimeEventProcessor initialization issue has been fixed."
echo "You will need to restart the Docker containers for the changes to take effect."
echo "Run: ./restart_docker_simple.sh"
