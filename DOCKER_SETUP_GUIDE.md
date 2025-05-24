# Docker Setup Guide for RedBarSushiAI

This guide provides comprehensive instructions for setting up RedBarSushiAI using Docker Compose.

## Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+
- Git
- At least 4GB of available RAM
- OpenAI API key with access to Realtime API

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/RedBarSushiAI.git
   cd RedBarSushiAI
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys (see Environment Variables section below).

3. **Initialize and start the services:**
   ```bash
   ./docker-init.sh
   ```

4. **Verify the setup:**
   ```bash
   # Test WebSocket connectivity
   ./test-websocket.py
   
   # Run E2E tests
   ./run-tests.sh
   ```

## Environment Variables

### Required Variables

These MUST be set in your `.env` file for the application to work:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key with Realtime API access | `sk-proj-...` |

### Optional Variables for Full Functionality

These are needed for production use but not required for local testing:

| Variable | Description | Example |
|----------|-------------|---------|
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | `AC...` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | `...` |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number | `+1234567890` |
| `DELIVERECT_API_KEY` | Deliverect API key | `...` |
| `DELIVERECT_CLIENT_ID` | Deliverect Client ID | `...` |
| `DELIVERECT_CLIENT_SECRET` | Deliverect Client Secret | `...` |

### Configuration Variables

These have sensible defaults but can be customized:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_REALTIME_MODEL` | OpenAI model to use | `gpt-4o-realtime-preview-2024-10-01` |
| `OPENAI_REALTIME_VOICE` | Voice for TTS | `shimmer` |
| `FASTAPI_ENV` | Environment mode | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `BASE_URL` | Base URL for webhooks | `http://localhost:8000` |

## Docker Services

The `docker-compose.yml` file sets up the following services:

### 1. **app** - FastAPI Application
- **Port**: 8000 (configurable via `APP_PORT`)
- **Endpoints**:
  - Health check: `http://localhost:8000/health`
  - API docs: `http://localhost:8000/docs`
  - WebSocket: `ws://localhost:8000/realtime/ws/media/{call_sid}`

### 2. **postgres** - PostgreSQL Database
- **Port**: 5432 (configurable via `POSTGRES_PORT`)
- **Credentials**: postgres/postgres
- **Database**: redbarsushi

### 3. **redis** - Redis Cache
- **Port**: 6379 (configurable via `REDIS_PORT`)
- **Used for**: Session storage, caching, Celery broker

### 4. **celery** - Background Worker
- Processes async tasks like SMS notifications

### 5. **celery-beat** - Task Scheduler
- Schedules periodic tasks

## Common Commands

### Starting Services
```bash
# Start all services
docker-compose up -d

# Start with logs
docker-compose up

# Rebuild and start
docker-compose up -d --build
```

### Stopping Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (full reset)
docker-compose down -v
```

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app

# Filter logs
docker-compose logs -f app | grep WebSocket
```

### Database Operations
```bash
# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d redbarsushi

# Run migrations
docker-compose exec app python -m app.db_init

# Seed menu data
docker-compose exec app python seed_menu_db.py
```

### Running Tests
```bash
# Run all E2E tests
./run-tests.sh

# Run specific test file
docker-compose exec app pytest tests/e2e/test_fastapi_voice_flow.py -v

# Run with coverage
docker-compose exec app pytest --cov=app tests/
```

## Troubleshooting

### Port Conflicts
If you get port binding errors, change the ports in `.env`:
```env
APP_PORT=8001
POSTGRES_PORT=5433
REDIS_PORT=6380
```

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready -U postgres
```

### WebSocket Connection Issues
```bash
# Test WebSocket connectivity
./test-websocket.py

# Check app logs for WebSocket errors
docker-compose logs -f app | grep -i websocket
```

### OpenAI API Issues
- Verify your API key is correct in `.env`
- Check you have access to the Realtime API
- Monitor logs: `docker-compose logs -f app | grep -i openai`

## Production Deployment

For production deployment:

1. Update `.env` with production values:
   ```env
   FASTAPI_ENV=production
   BASE_URL=https://your-domain.com
   ```

2. Use the production Docker Compose override:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. Set up SSL/TLS for WebSocket connections (required for `wss://`)

4. Configure your domain's webhook URLs in Twilio:
   - Voice webhook: `https://your-domain.com/voice/`
   - WebSocket URL will be: `wss://your-domain.com/realtime/ws/media/{CallSid}`

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Docker Network                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   FastAPI   │  │  PostgreSQL │  │   Redis    │ │
│  │    :8000    │  │    :5432    │  │   :6379    │ │
│  └─────────────┘  └─────────────┘  └────────────┘ │
│         │                                   │       │
│  ┌─────────────┐  ┌──────────────────────────┐    │
│  │   Celery    │  │     Celery Beat          │    │
│  │   Worker    │  │     Scheduler            │    │
│  └─────────────┘  └──────────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify environment variables are set correctly
3. Ensure Docker has enough resources allocated
4. Review the troubleshooting section above
5. Check the GitHub issues for similar problems