#!/bin/bash
# Script to help debug OpenAI Realtime API issues in RedBarSushiAI

set -e  # Exit on any error

echo "===== RedBarSushiAI Realtime API Debug Helper ====="

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

# Check if we're running in Render
IS_RENDER=false
if [ -n "$RENDER_SERVICE_ID" ]; then
    IS_RENDER=true
    log "Running in Render environment"
else
    log "Running in local environment"
fi

# Switch to enhanced logging with the realtime client
log "Enabling enhanced debugging for OpenAI Realtime API..."

# Create symlink to enhanced version
if [ -f app/utils/realtime_audio_async.py ]; then
    log "Creating backup of original realtime_audio_async.py..."
    cp app/utils/realtime_audio_async.py app/utils/realtime_audio_async.py.bak
    log "Replacing with enhanced debugging version..."
    cp app/utils/enhanced_realtime_audio_async.py app/utils/realtime_audio_async.py
else
    log "❌ Error: realtime_audio_async.py not found"
    exit 1
fi

# Set logging level to DEBUG
export LOG_LEVEL=DEBUG

# Check environment variables
log "Checking critical environment variables..."

# Function to check environment variable
check_env_var() {
    var_name=$1
    var_value=${!var_name}
    
    if [ -z "$var_value" ]; then
        log "❌ Missing: $var_name is not set!"
        return 1
    else
        # Mask secrets in logs
        if [[ "$var_name" == *"KEY"* || "$var_name" == *"TOKEN"* || "$var_name" == *"SECRET"* ]]; then
            log "✅ Found: $var_name = ${var_value:0:4}...${var_value: -4}"
        else
            log "✅ Found: $var_name = $var_value"
        fi
        return 0
    }
}

# Check critical environment variables
missing_vars=0

check_env_var "OPENAI_API_KEY" || missing_vars=$((missing_vars + 1))
check_env_var "TWILIO_ACCOUNT_SID" || missing_vars=$((missing_vars + 1))
check_env_var "TWILIO_AUTH_TOKEN" || missing_vars=$((missing_vars + 1))
check_env_var "TWILIO_PHONE_NUMBER" || missing_vars=$((missing_vars + 1))

if [ $missing_vars -gt 0 ]; then
    log "❌ Found $missing_vars missing critical environment variables!"
    
    if [ "$IS_RENDER" = true ]; then
        log "Please set these variables in your Render dashboard:"
        log "1. Go to https://dashboard.render.com/web/srv-xxx/env"
        log "2. Add the missing environment variables"
        log "3. Click Save Changes and wait for redeployment"
    else
        log "Please set these variables in your .env file or export them in your shell"
    fi
    
    exit 1
fi

log "All critical environment variables are set!"

# Make log directory if it doesn't exist
mkdir -p logs

# Create additional file handler specifically for voice API
log "Setting up enhanced logging for voice API..."
cat > app/api/voice_debug.py << 'EOF'
"""
Debug utility for voice API.
This module patches the voice_async module with enhanced logging.
"""

import logging
import os
import traceback
from functools import wraps
import asyncio

# Configure logging
voice_logger = logging.getLogger('voice.debug')
voice_logger.setLevel(logging.DEBUG)

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Create file handler
file_handler = logging.FileHandler('logs/voice_debug.log')
file_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add handler to logger
voice_logger.addHandler(file_handler)

# Log initialization
voice_logger.info('=== Voice API Debug Logger Initialized ===')

def log_async_calls(func):
    """Decorator to log async function calls with detailed information."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        call_id = None
        
        # Try to extract call SID from args or kwargs
        for arg in args:
            if isinstance(arg, str) and (arg.startswith('CA') or arg.startswith('call_')):
                call_id = arg
                break
        
        if call_id is None:
            for k, v in kwargs.items():
                if (k in ['call_sid', 'sid'] and isinstance(v, str) and 
                    (v.startswith('CA') or v.startswith('call_'))):
                    call_id = v
                    break
        
        call_context = f"[{call_id}] " if call_id else ""
        func_name = func.__qualname__
        
        try:
            voice_logger.debug(f"{call_context}ENTER: {func_name} with args={args}, kwargs={kwargs}")
            start_time = asyncio.get_event_loop().time()
            result = await func(*args, **kwargs)
            elapsed = asyncio.get_event_loop().time() - start_time
            voice_logger.debug(f"{call_context}EXIT: {func_name} completed in {elapsed:.4f}s")
            return result
        except Exception as e:
            voice_logger.error(f"{call_context}ERROR in {func_name}: {str(e)}")
            voice_logger.error(traceback.format_exc())
            raise
    
    return wrapper
EOF

log "All debug enhancements applied. Ready for testing!"

if [ "$IS_RENDER" = true ]; then
    log "Your app is already running on Render. To view logs:"
    log "1. Visit the Render dashboard"
    log "2. Go to your service"
    log "3. Click the 'Logs' tab"
    log "4. Look for errors in the OpenAI Realtime connections"
else
    log "Run your application now and check these log files for errors:"
    log "- logs/realtime_audio.log - for OpenAI Realtime API interactions"
    log "- logs/voice_debug.log - for voice API call details"
    log "- logs/app.log - for general application logs"
fi

echo
echo "After testing, you can restore the original files with these commands:"
echo "mv app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py"
echo "rm app/api/voice_debug.py"
echo