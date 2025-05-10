#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== RedBarSushiAI Render Debugging Setup ===${NC}"

# Check for Python
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}Error: Python 3 is not installed or not in PATH!${NC}"
  exit 1
fi

# Make the check_env_variables.py script executable
chmod +x check_env_variables.py

# Make the enhance_openai_client.py script executable
chmod +x enhance_openai_client.py

# Run the environment variable check
echo -e "${CYAN}Running environment variable check...${NC}"
python3 check_env_variables.py

# Capture the exit code
ENV_CHECK_STATUS=$?

if [ $ENV_CHECK_STATUS -ne 0 ]; then
  echo -e "${RED}Environment variable check failed!${NC}"
  echo -e "${YELLOW}Please check the output above and make sure all critical variables are set.${NC}"
  echo -e "${YELLOW}You should set these variables in the Render dashboard:${NC}"
  echo -e "${CYAN}1. Go to your Render dashboard${NC}"
  echo -e "${CYAN}2. Select your RedBarSushiAI service${NC}"
  echo -e "${CYAN}3. Click 'Environment' tab${NC}"
  echo -e "${CYAN}4. Add/update the missing environment variables${NC}"
  echo -e "${CYAN}5. Save changes and deploy again${NC}"
  
  read -p "Do you want to continue with the debugging setup anyway? (y/n): " continue_anyway
  if [[ "$continue_anyway" != "y" ]]; then
    exit 1
  fi
fi

# Ask if user wants to enable enhanced debugging
read -p "Do you want to enable enhanced debugging for OpenAI Realtime API? (y/n): " enable_debug
if [[ "$enable_debug" == "y" ]]; then
  echo -e "${CYAN}Enhancing OpenAI Realtime client with detailed logging...${NC}"
  python3 enhance_openai_client.py
  ENHANCE_STATUS=$?
  
  if [ $ENHANCE_STATUS -ne 0 ]; then
    echo -e "${RED}Failed to enhance OpenAI Realtime client!${NC}"
    exit 1
  fi
fi

# Create a summary file with instructions
cat > RENDER_DEBUG_INSTRUCTIONS.md << 'EOF'
# RedBarSushiAI Render Debugging Instructions

## Environment Variables Check

First, ensure these critical environment variables are set correctly in your Render dashboard:

- `OPENAI_API_KEY` - **CRITICAL** for voice functionality
- `TWILIO_ACCOUNT_SID` - For Twilio integration
- `TWILIO_AUTH_TOKEN` - For Twilio authentication
- `TWILIO_PHONE_NUMBER` - For outgoing calls
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string

## How to Check Logs

1. Go to your Render dashboard
2. Select your RedBarSushiAI service
3. Click the "Logs" tab
4. Look for logs with these patterns for troubleshooting OpenAI connection issues:

```
[OpenAI Realtime] Attempting to connect to OpenAI Realtime API...  # Connection attempt
[OpenAI Realtime] Successfully connected to OpenAI Realtime API    # Success
[OpenAI Realtime] Authentication failed: Invalid API key           # Auth failure
[OpenAI Realtime] Failed to connect to OpenAI Realtime API         # General failure
```

## Common Issues and Solutions

### "Couldn't connect" after greeting

This usually indicates one of these issues:

1. **Invalid or missing OPENAI_API_KEY**
   - Check the key in Render environment variables
   - Ensure it starts with "sk-" and is complete
   - Verify the key has access to the Realtime API

2. **OpenAI Realtime API access issues**
   - Ensure your OpenAI account has access to Realtime API
   - Check API status at status.openai.com

3. **WebSocket connection problems**
   - Look for WebSocket errors in the logs
   - Check if Render's IP addresses need to be allowlisted for OpenAI

### Environment variable errors

Look for these patterns in logs:

```
Error parsing Twilio version: name 'TWILIO_ACCOUNT_SID' is not defined
Error initializing Stripe client: name 'STRIPE_API_KEY' is not defined
```

These indicate missing environment variables that need to be set in Render.

## Testing Procedure

1. Set all environment variables in Render dashboard
2. Deploy the application again
3. Make a test call to your Twilio number
4. Check logs immediately for detailed connection information
5. If the issue persists, note the exact error messages in the logs

## Restoring Original Code

To restore the original client implementation, SSH into your server and run:

```bash
cp app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py
cp app/api/voice_async.py.bak app/api/voice_async.py
```
EOF

echo -e "${GREEN}Debug setup complete!${NC}"
echo -e "${CYAN}Please check RENDER_DEBUG_INSTRUCTIONS.md for detailed instructions on debugging.${NC}"

if [ $ENV_CHECK_STATUS -ne 0 ]; then
  echo -e "${YELLOW}REMINDER: You need to set the missing environment variables in your Render dashboard!${NC}"
  echo -e "${YELLOW}After setting them, redeploy your application for the changes to take effect.${NC}"
fi

if [[ "$enable_debug" == "y" ]]; then
  echo -e "${MAGENTA}Enhanced debugging is enabled. The next call attempt will have detailed logging.${NC}"
  echo -e "${MAGENTA}Check your Render logs for detailed connection information.${NC}"
fi