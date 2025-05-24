# RedBarSushiAI Development Guide

This guide will help you set up and use the Docker-based development environment for RedBarSushiAI.

## Prerequisites

- Docker and Docker Compose installed
- Git
- Your OpenAI API key

## Quick Start

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <your-repo-url>
   cd RedBarSushiAI
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Start the development environment**:
   ```bash
   ./dev.sh start
   ```

   This will:
   - Start PostgreSQL database
   - Start Redis cache
   - Start the FastAPI application
   - Start Celery workers
   - Initialize the database

4. **Access the application**:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/healthcheck
   - WebSocket endpoint: ws://localhost:8000/ws/media/{call_sid}

## Development Commands

The `dev.sh` script provides several useful commands:

### Basic Commands

```bash
# Start the development environment
./dev.sh start

# Stop the development environment
./dev.sh stop

# Restart the development environment
./dev.sh restart

# View logs
./dev.sh logs

# View logs for a specific service
./dev.sh logs app
./dev.sh logs postgres
./dev.sh logs redis
./dev.sh logs celery

# Check status
./dev.sh status
```

### Advanced Commands

```bash
# Open a shell in the app container
./dev.sh shell

# Run tests
./dev.sh test

# Run specific tests
./dev.sh test tests/e2e/test_fastapi_voice_flow.py

# Clean up everything (removes containers and volumes)
./dev.sh clean

# Initialize/reset the database
./dev.sh init-db
```

## Port Configuration

If you have port conflicts, you can change the ports in your `.env` file:

```env
# Default ports
APP_PORT=8000      # FastAPI app
POSTGRES_PORT=5432 # PostgreSQL
REDIS_PORT=6379    # Redis

# Alternative ports if defaults are in use
APP_PORT=8001
POSTGRES_PORT=5433
REDIS_PORT=6380
```

## Troubleshooting

### Port Already in Use

If you get a "port is already allocated" error:

1. Check what's using the port:
   ```bash
   lsof -i :6379  # For Redis
   lsof -i :5432  # For PostgreSQL
   lsof -i :8000  # For the app
   ```

2. Either stop the conflicting service or change the port in `.env`

3. Restart the environment:
   ```bash
   ./dev.sh restart
   ```

### Container Issues

If containers are failing to start:

1. Check the logs:
   ```bash
   ./dev.sh logs
   ```

2. Clean and restart:
   ```bash
   ./dev.sh clean
   ./dev.sh start
   ```

### Database Issues

If you need to reset the database:

```bash
./dev.sh init-db
```

## Testing

### Running Tests

Run all tests:
```bash
./dev.sh test
```

Run specific test files:
```bash
./dev.sh test tests/e2e/test_fastapi_voice_flow.py
```

Run with coverage:
```bash
./dev.sh test --cov=app
```

### Testing WebSocket Connections

A test script is provided to verify WebSocket functionality:

```bash
docker exec redbarsushi-app python test_development.py
```

## Development Workflow

1. **Make code changes** in your local editor

2. **The changes are automatically reflected** in the container (volumes are mounted)

3. **The app auto-reloads** when you save files (FastAPI with --reload)

4. **Check logs** if something goes wrong:
   ```bash
   ./dev.sh logs app
   ```

5. **Run tests** to verify your changes:
   ```bash
   ./dev.sh test
   ```

## API Documentation

Once the environment is running, you can access:

- **Interactive API docs**: http://localhost:8000/docs
- **Alternative API docs**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

## WebSocket Testing

To test WebSocket connections manually:

1. Open the WebSocket test page: http://localhost:8000/static/websocket-test.html

2. Or use a WebSocket client to connect to: `ws://localhost:8000/ws/media/{call_sid}`

## Environment Variables

Key environment variables (set in `.env`):

```env
# Required
OPENAI_API_KEY=sk-...

# Optional (for full functionality)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

DELIVERECT_API_KEY=...
DELIVERECT_CLIENT_ID=...
DELIVERECT_CLIENT_SECRET=...

# Development settings
FASTAPI_ENV=development
LOG_LEVEL=INFO
```

## Next Steps

1. **Set up ngrok** for testing with Twilio webhooks:
   ```bash
   ./start_docker_with_ngrok.sh
   ```

2. **Configure Twilio** to point to your ngrok URL for voice webhooks

3. **Load menu data** from Deliverect or use the sample data

4. **Start developing** your features!

## Common Issues and Solutions

### Issue: Stripe module not found
**Solution**: The app gracefully handles missing Stripe. Payment functionality will be disabled but the app will run.

### Issue: Flask imports failing
**Solution**: The codebase is migrating from Flask to FastAPI. Some routes may not work yet but core functionality is available.

### Issue: WebSocket 403 Forbidden
**Solution**: This is expected without proper Twilio authentication. Use the test endpoints for development.

### Issue: Menu data not loading
**Solution**: Check that menu_data.json exists or configure Deliverect integration.

## Support

For issues or questions:
1. Check the logs: `./dev.sh logs`
2. Check the health endpoint: http://localhost:8000/healthcheck
3. Review this guide and the README.md
4. Check existing issues in the repository