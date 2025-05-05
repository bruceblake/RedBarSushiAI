# Deploying the Fixes to Render Staging Environment

This document explains how to deploy the Redis and X11 fixes to your Render staging environment.

## Overview

The fixes we've implemented address three main issues:

1. **Redis Connection Error**: The application was trying to connect to Redis on localhost, but Redis is available at a different hostname in the Render environment.
2. **X11 Display Configuration**: The OpenAI Realtime client was failing because it couldn't connect to the X11 display.
3. **Logger Initialization Error**: There was an unbound `logger` variable in `app/__init__.py`.

## How to Deploy

### Option 1: Push Changes to Your Staging Branch

1. Commit all the fix scripts and the updated `docker-entrypoint.sh`:

```bash
git add docker-entrypoint.sh
git add fix_redis_connection.py
git add fix_docker_x11.py
git add fix_logger.py
git add fix_render_staging.py
git add DOCKER_ENV_FIXES.md
git add RENDER_DEPLOYMENT.md

git commit -m "Add environment fixes for Redis connection and X11 display issues"
git push origin staging
```

2. Render will automatically deploy the changes to your staging environment.

### Option 2: Manual Application in Render Console

If you can't push changes right now, you can manually apply the fixes in the Render console:

1. Log in to your Render dashboard
2. Go to your RedBarSushiAI staging service
3. Click on "Shell" in the sidebar
4. Run the following commands:

```bash
# Create the fix script
cat > fix_render_staging.py << 'EOF'
#!/usr/bin/env python

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("render_fix")

# Fix Redis environment variables
redis_host = "red-ceqpb6rf1sgc739ut8e0"
redis_port = "6379"

os.environ["REDIS_URL"] = f"redis://{redis_host}:{redis_port}/0"
os.environ["CELERY_BROKER_URL"] = f"redis://{redis_host}:{redis_port}/1"
os.environ["CELERY_RESULT_BACKEND"] = f"redis://{redis_host}:{redis_port}/1"

logger.info(f"Set REDIS_URL: {os.environ['REDIS_URL']}")

# Fix X11 display settings
x11_env = {
    "PYNPUT_HEADLESS": "1",
    "NO_X11": "1", 
    "HEADLESS": "1",
    "OPENAI_REALTIME_NO_DISPLAY": "1",
    "X11_SETUP_SUCCESS": "false",
    "USE_DIRECT_WEBSOCKET": "true",
    "OPENAI_REALTIME_AVAILABLE": "1"
}

for key, value in x11_env.items():
    os.environ[key] = value
    logger.info(f"Set {key}: {value}")

# Fix logger initialization
init_file = "/app/app/__init__.py"
if os.path.exists(init_file):
    with open(init_file, "r") as f:
        content = f.read()
    
    if "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")" in content:
        logger.info("Fixing logger initialization...")
        new_content = content.replace(
            "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")",
            "app_logger = logging.getLogger(__name__)\n    app_logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")"
        )
        new_content = new_content.replace("logger.info(\"Voice handler set to ORCHESTRATED", "app_logger.info(\"Voice handler set to ORCHESTRATED")
        new_content = new_content.replace("logger.info(\"Voice handler set to STANDARD", "app_logger.info(\"Voice handler set to STANDARD")
        
        with open(init_file, "w") as f:
            f.write(new_content)
        logger.info("Logger initialization fixed")

logger.info("All fixes applied successfully")
EOF

# Make it executable
chmod +x fix_render_staging.py

# Run the fix script
python fix_render_staging.py

# Restart the web process
echo "Fix applied, please restart the service from the Render dashboard"
```

5. After running these commands, restart the service from the Render dashboard.

## Verifying the Fixes

After deploying the fixes, verify they're working by:

1. Check the application logs in the Render dashboard:
   - Look for "Applying enhanced Redis fix for Render environment..."
   - Look for "Configured Render environment for headless mode..."

2. Ensure the application starts without Redis connection errors.

3. Validate that the OpenAI Realtime client is working in headless mode.

## Troubleshooting

If you still encounter issues after applying the fixes:

### Redis Connection Issues

- Check if the Redis hostname is correct. If your Render Redis instance has a different hostname, update the `redis_host` variable in the fix scripts.
- Verify Redis is running by checking the Redis logs in the Render dashboard.

### OpenAI Realtime Client Issues

- If OpenAI Realtime client still has issues, try setting the `USE_DIRECT_WEBSOCKET` environment variable to `true` in your environment variables settings.

### Logger Initialization Issues

- If the application still crashes with an unbound `logger` variable error, manually fix the `app/__init__.py` file following the steps in Option 2 above.

## Long-term Solution

These fixes address the immediate issues, but for a more robust long-term solution:

1. Update the application code to properly handle Redis connections in different environments.
2. Implement proper fallback mechanisms for the OpenAI Realtime client.
3. Fix all logger initialization patterns in the codebase.

## Support

If you encounter any issues with these fixes, please contact the development team.