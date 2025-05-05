# Docker Environment Fixes for RedBarSushiAI

This document provides information about the Docker environment fixes implemented for RedBarSushiAI.

## Overview

The Docker environment for RedBarSushiAI requires specific configurations to work properly:

1. **Redis Connection** - The application needs to connect to Redis for caching, session management, and message queuing
2. **X11 Display** - OpenAI Realtime client requires an X11 display for operation
3. **OpenAI SDK Configuration** - Proper setup of the OpenAI SDK and Realtime client

These fixes address common issues encountered when running RedBarSushiAI in Docker or on Render.

## Quick Start

To apply all fixes at once, run:

```bash
./fix_docker_environment.sh
```

This script will:
1. Fix Redis connection issues
2. Set up a virtual X11 display (or configure headless mode if needed)
3. Configure the OpenAI Realtime client

## Redis Connection Fix

The Redis connection fix (`fix_redis_connection.py`) addresses issues with connecting to Redis in different environments.

### What It Does

- Detects the current environment (local, Docker, Render)
- Fixes Redis URLs to use the correct host based on the environment
- Updates Redis connection logic in application files
- Sets the appropriate environment variables

### Running the Fix

```bash
python fix_redis_connection.py
```

### Environment Variables

The fix sets these environment variables:
- `REDIS_URL` - Main Redis connection URL
- `CELERY_BROKER_URL` - Redis URL for Celery tasks
- `CELERY_RESULT_BACKEND` - Redis URL for Celery results

## X11 Display Fix

The X11 display fix (`fix_docker_x11.py`) sets up a virtual X11 display for the OpenAI Realtime client.

### What It Does

- Installs necessary X11 packages
- Sets up a virtual X11 server using Xvfb
- Configures environment variables for X11 support
- Creates startup scripts for persistence
- Falls back to headless mode if X11 setup fails

### Running the Fix

```bash
python fix_docker_x11.py
```

### Environment Variables

The fix sets these environment variables when X11 setup succeeds:
- `DISPLAY` - X11 display number (e.g., `:1`)
- `PYNPUT_HEADLESS=0` - Disables headless mode for pynput
- `NO_X11=0` - Enables X11 support
- `HEADLESS=0` - Disables headless mode
- `OPENAI_REALTIME_NO_DISPLAY=0` - Enables display for OpenAI Realtime
- `X11_SETUP_SUCCESS=true` - Indicates successful X11 setup
- `OPENAI_REALTIME_AVAILABLE=1` - Indicates OpenAI Realtime is available
- `USE_XVFB=true` - Indicates Xvfb is being used

In headless mode, it sets:
- `PYNPUT_HEADLESS=1`
- `NO_X11=1`
- `HEADLESS=1`
- `OPENAI_REALTIME_NO_DISPLAY=1`
- `X11_SETUP_SUCCESS=false`
- `OPENAI_REALTIME_AVAILABLE=1` (still available using fallback implementation)

## OpenAI Realtime Setup

The OpenAI Realtime setup (`setup_openai_realtime.py`) ensures the OpenAI SDK and Realtime client are properly configured.

### What It Does

- Installs/upgrades the OpenAI SDK
- Installs/upgrades the OpenAI Realtime client
- Sets up fallback WebSocket implementation for environments without X11
- Verifies the installation and configuration

### Running the Fix

```bash
python setup_openai_realtime.py
```

## Troubleshooting

### Redis Connection Issues

If you still have Redis connection issues after running the fixes:

1. Check if Redis is running:
   ```bash
   docker ps | grep redis
   ```

2. Verify Redis environment variables:
   ```bash
   echo $REDIS_URL
   ```

3. Try connecting manually:
   ```bash
   redis-cli -u $REDIS_URL ping
   ```

### X11 Display Issues

If you have issues with the X11 display:

1. Check if Xvfb is running:
   ```bash
   ps aux | grep Xvfb
   ```

2. Verify the DISPLAY environment variable:
   ```bash
   echo $DISPLAY
   ```

3. Test the X11 connection:
   ```bash
   xdpyinfo
   ```

4. If X11 setup continues to fail, the system will use the headless mode.

### OpenAI Realtime Client Issues

If you have issues with the OpenAI Realtime client:

1. Check if the client is installed:
   ```bash
   pip show openai-realtime-client
   ```

2. Verify that fallback packages are installed:
   ```bash
   pip show websockets aiohttp python-socketio
   ```

3. Make sure the OPENAI_API_KEY is set:
   ```bash
   echo $OPENAI_API_KEY | wc -c
   ```
   (Should output a number greater than 1)

## Manual Installation

If the automated fixes don't work, you can manually install the required components:

### Redis

```bash
# For Docker Compose environments, add Redis service to docker-compose.yml:
services:
  redis:
    image: redis:7
    ports:
      - "6379:6379"

# Then set environment variables in your app service:
environment:
  - REDIS_URL=redis://redis:6379/0
  - CELERY_BROKER_URL=redis://redis:6379/1
  - CELERY_RESULT_BACKEND=redis://redis:6379/1
```

### X11 Display

```bash
# Install X11 packages
apt-get update && apt-get install -y xvfb x11-utils xorg libxrender1 libxtst6 libxi6 dbus-x11

# Start Xvfb
Xvfb :1 -screen 0 1280x720x24 -ac +extension GLX +render -noreset &

# Set environment variables
export DISPLAY=:1
export PYNPUT_HEADLESS=0
export NO_X11=0
export HEADLESS=0
export OPENAI_REALTIME_NO_DISPLAY=0
export X11_SETUP_SUCCESS=true
```

### OpenAI Realtime Client

```bash
# Install OpenAI SDK
pip install --upgrade openai==1.77.0

# Install OpenAI Realtime client
pip install --upgrade openai-realtime-client==0.1.0

# Install fallback packages
pip install websockets==13.1 aiohttp==3.11.13 python-socketio==5.8.0 eventlet==0.33.3
```

## Additional Resources

- [OpenAI Realtime API Documentation](https://platform.openai.com/docs/api-reference/audio-realtime)
- [Redis Documentation](https://redis.io/documentation)
- [Xvfb Documentation](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml)
- [Docker Documentation](https://docs.docker.com/)
- [Render Documentation](https://render.com/docs)