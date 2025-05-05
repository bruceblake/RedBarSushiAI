# Render Deployment Guide

This document provides complete instructions for deploying RedBarSushiAI to Render with comprehensive dependency management.

## System Requirements

The application requires the following system dependencies:

- portaudio19-dev
- libportaudio2
- libportaudiocpp0
- python3-dev
- ffmpeg
- build-essential

## Dependencies Installation

Dependency installation has been fully automated with the following approach:

1. System dependencies are installed via apt-get
2. Python dependencies are installed via pip from requirements.strict.txt
3. Critical packages are verified to ensure they're installed correctly

The `install_all_dependencies.sh` script handles all of this automatically.

## Deployment Process

### Production

1. Push changes to the `main` branch
2. Render automatically deploys:
   - Web service: redbarsushi-web
   - Worker service: redbarsushi-celery
   - Redis service: redbarsushi-redis

### Staging

1. Push changes to the `staging` branch
2. Render automatically deploys:
   - Web service: redbarsushi-staging
   - Worker service: redbarsushi-staging-celery
   - Redis service: redbarsushi-staging-redis
   - E2E test job: redbarsushi-staging-e2e

## Environment Variables

Ensure the following environment variables are set in Render:

- `PROCESS`: Set to "web" for web services, "celery" for worker services
- `FORCE_HEADLESS`: Set to "true" to ensure headless mode
- `PYTHONUNBUFFERED`: Set to "1" for unbuffered logging
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- Other API credentials (Twilio, OpenAI, Stripe)

## WebSocket Configuration

The application uses WebSockets for real-time voice processing:

1. Gunicorn is configured with gevent-websocket worker
2. Flask-Sock is used for WebSocket support in Flask
3. OpenAI Realtime API is used for streaming audio

## Fixed Issues

The deployment now addresses several critical issues:

1. **Dependency Management**: Strict version pinning for all packages
2. **System Dependencies**: Automatic installation of required system libraries
3. **Redis Connection**: Proper connection to Redis service
4. **Headless Mode**: Configured for server environments without X11
5. **WebSocket Support**: Proper Gunicorn worker configuration
6. **Enhanced Logging**: Structured logging for diagnostics

## Troubleshooting

If deployment fails, check the following:

1. Verify all environment variables are set correctly
2. Check Render logs for installation errors
3. Test the health endpoint: `https://redbarsushi-staging.onrender.com/health`
4. Check WebSocket stats: `https://redbarsushi-staging.onrender.com/monitoring/websocket/stats`

## Debug Endpoints

These endpoints are available for debugging:

- `/health`: Basic health check
- `/monitoring/health`: Detailed health check with component status
- `/monitoring/websocket/stats`: WebSocket connection statistics
- `/monitoring/agents/health`: Agent system health
- `/environment`: Environment details (development/staging only)

## Custom Scripts

- `install_all_dependencies.sh`: Installs all dependencies required by the system
- `run_e2e_tests.sh`: Runs end-to-end tests with proper environment setup
- `docker-entrypoint.sh`: Contains deployment logic for container environments

## Verifying the Deployment

After deploying, verify everything is working by:

1. Check application health: `curl https://redbarsushi-staging.onrender.com/health`
2. Monitor WebSocket connections: `curl https://redbarsushi-staging.onrender.com/monitoring/websocket/stats`
3. Test a WebSocket connection with the debug endpoint if needed