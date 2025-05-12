# RedBarSushiAI Development Environment

This document provides instructions for setting up and managing the development environment for the RedBarSushiAI project using the new unified development script.

## Prerequisites

- Docker and Docker Compose installed
- Git
- Optional: ngrok (for exposing local services to the internet for Twilio webhook testing)

## Environment Setup

The development environment is now managed through a unified script called `start_dev_env.sh` that provides a consistent interface for working with Docker containers.

### Initial Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd RedBarSushiAI
   ```

2. Build and start the development environment:
   ```
   ./start_dev_env.sh up --build
   ```
   This will build the Docker images and start all necessary services (app, postgres, redis). If a `.env.development` file doesn't exist, the script will create a default one with placeholder values.

## Managing the Development Environment

The `start_dev_env.sh` script provides a unified interface for managing the Docker development environment:

### Basic Commands

- **Start services**:
  ```
  ./start_dev_env.sh up
  ```
  Add `--build` to rebuild images, or `-d` to run in detached mode.

- **Stop services**:
  ```
  ./start_dev_env.sh down
  ```

- **Restart services**:
  ```
  ./start_dev_env.sh restart
  ```
  Add `--build` to rebuild images.

- **Build or rebuild images without starting**:
  ```
  ./start_dev_env.sh build
  ```

- **View logs**:
  ```
  ./start_dev_env.sh logs
  ```
  To view logs for a specific service:
  ```
  ./start_dev_env.sh logs postgres
  ```

- **Clean environment** (remove containers, volumes, networks):
  ```
  ./start_dev_env.sh clean
  ```

- **Run diagnostics**:
  ```
  ./start_dev_env.sh diagnostics
  ```
  This will check container status, database connectivity, and OpenAI API connectivity.

### Testing with Twilio

For testing voice functionality with Twilio, you need to expose your local development server to the internet using ngrok:

1. Start the development environment:
   ```
   ./start_dev_env.sh up
   ```

2. In another terminal, start an ngrok tunnel:
   ```
   ./start_dev_env.sh ngrok 8080
   ```
   This will provide you with a temporary public URL that forwards to your local server.

3. Configure your Twilio phone number's voice webhook URL to point to:
   ```
   https://<your-ngrok-subdomain>.ngrok.io/voice/webhook
   ```

## Environment Variables

The `.env.development` file contains configuration for your development environment. Key variables include:

```
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=redbarsushi

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# OpenAI API (required for AI functionality)
OPENAI_API_KEY=your_openai_api_key
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Twilio (required for voice functionality)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

# Application settings
SECRET_KEY=your_secret_key
FASTAPI_ENV=development
```

## Accessing Services

- **API**: http://localhost:8080
- **WebSocket Test**: ws://localhost:8080/ws-test/test
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Differences from Production

The development environment differs from production in these ways:

1. Uses a single worker instead of multiple workers
2. Enables debug-level logging
3. Mounts local code directories for hot-reload
4. Uses dummy API keys by default (replace with real ones for testing)

## Troubleshooting

### Database Connection Issues

If you experience database connection issues:

1. Run diagnostics:
   ```
   ./start_dev_env.sh diagnostics
   ```

2. If issues persist, try a clean restart:
   ```
   ./start_dev_env.sh clean
   ./start_dev_env.sh up --build
   ```

3. Check if your `.env.development` file has the correct `DATABASE_URL` (should be `postgresql://postgres:postgres@postgres:5432/redbarsushi`)

### OpenAI API Connection Issues

The most common cause is an invalid API key:

1. Check if your OpenAI API key is valid and has access to the model specified
2. Update your `.env.development` file with a valid OpenAI API key
3. Restart the services with `./start_dev_env.sh restart`

### WebSocket Connection Issues 

The WebSocket implementation has been fixed to resolve the "cannot call recv while another coroutine is already waiting" error by:

1. Using `async for message in self.websocket:` instead of manually calling `await self.websocket.recv()`
2. Adding proper task management with `_event_processing_task` and `is_processing_loop_active` flags 
3. Implementing proper task cancellation in the `close()` method

If you still experience WebSocket issues, run diagnostics and check the logs:
```
./start_dev_env.sh logs app
```

## Best Practices

1. **Use the unified script**: Always use `start_dev_env.sh` to manage the development environment for consistency.

2. **Environment variables**: Use `.env.development` for local development to configure API keys and services.

3. **Check logs regularly**: Monitor the application logs during development to catch issues early.

4. **Run diagnostics**: Use `./start_dev_env.sh diagnostics` to verify the environment is working correctly.