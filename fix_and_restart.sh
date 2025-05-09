#!/bin/bash

# Fix and restart script for RedBarSushiAI
# This script fixes database issues and restarts the service with optimized settings

echo "Starting fix and restart process for RedBarSushiAI..."

# Fix database structure
echo "Fixing database structure..."
python3 fix_db_structure.py

# Check if the fix was successful
if [ $? -ne 0 ]; then
    echo "Database fix failed. Please check the logs."
    exit 1
fi

echo "Database structure fix completed successfully."

# Restart Docker containers
echo "Restarting Docker containers..."
./restart_docker.sh

echo "Done! The application has been fixed and restarted."
echo "The audio processing has been slowed down to prevent overwhelming the OpenAI API."
echo ""
echo "NOTES:"
echo "1. The application now uses a token bucket rate limiter to restrict API calls to 2 per second."
echo "2. Additional delays have been added between audio packets to prevent overwhelming the API."
echo "3. The missing database column 'reference_handler' has been added to the menu_modifiers table."
echo ""
echo "If you continue to experience issues, consider further reducing the rate by editing:"
echo "  - token_rate in realtime.py (currently 2.0 tokens per second)"
echo "  - delay settings in the rate limiting code"