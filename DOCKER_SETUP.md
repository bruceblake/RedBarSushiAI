# Docker Setup Guide for RedBarSushiAI

This guide will help you run the entire RedBarSushiAI system using Docker with ngrok for local development.

## Prerequisites

1. **Docker Desktop** installed and running
   - [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
   
2. **Make** command (optional but recommended)
   - Windows: Use Git Bash or WSL
   - Mac: Already installed
   - Linux: `sudo apt-get install make`

3. **Accounts Needed**:
   - [OpenAI API Key](https://platform.openai.com/api-keys)
   - [Twilio Account](https://www.twilio.com/try-twilio)
   - [ngrok Account](https://ngrok.com/signup) (free tier is fine)

## Quick Start (5 minutes)

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd RedBarSushiAI

# Copy environment template
cp .env.docker.example .env

# Edit .env file with your keys
# IMPORTANT: Add your OpenAI API key, Twilio credentials, and ngrok auth token
nano .env  # or use your favorite editor
```

### 2. Start Everything with One Command

```bash
# This will build images, start services, and initialize the database
make setup
```

That's it! The system will:
- Build Docker images
- Start PostgreSQL, Redis, FastAPI app, and ngrok
- Initialize the database with tables
- Seed sample menu data
- Show you the ngrok public URL for Twilio

### 3. Configure Twilio

When `make setup` completes, you'll see output like:
```
Ngrok Public URL: https://abc123.ngrok.io
Twilio Webhook URL: https://abc123.ngrok.io/voice/webhook
```

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Click on your phone number
4. Set the webhook URL to the one shown above
5. Set HTTP method to POST
6. Save

### 4. Test Your System

Call your Twilio phone number! You should hear:
- "Welcome to Red Bar Sushi AI!"
- "How can I help you today?"

## Common Docker Commands

### Using Make (Recommended)

```bash
make up          # Start all services
make down        # Stop all services
make logs        # View all logs
make logs-app    # View only app logs
make shell       # Open shell in app container
make ngrok-url   # Get current ngrok URL
make psql        # Connect to PostgreSQL
make redis-cli   # Connect to Redis
make test        # Run system tests
make clean       # Remove everything (including data)
```

### Using Docker Compose Directly

```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# Stop services
docker-compose -f docker-compose.dev.yml down

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Rebuild after code changes
docker-compose -f docker-compose.dev.yml build
```

## Service URLs

When running:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **ngrok Inspector**: http://localhost:4040
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Troubleshooting

### ngrok URL keeps changing

This is normal for free ngrok accounts. Each time you restart, you'll get a new URL and need to update Twilio.

**Solutions**:
1. Keep services running with `make up` (don't use `make down`)
2. Get a paid ngrok account for a stable subdomain
3. Use `make ngrok-url` to quickly get the current URL

### "Connection refused" errors

Make sure all services are running:
```bash
docker-compose -f docker-compose.dev.yml ps
```

All services should show "Up" status.

### Database initialization fails

If the automatic initialization fails:
```bash
# Initialize manually
make init

# Or step by step
docker-compose -f docker-compose.dev.yml run --rm app python init_db.py
docker-compose -f docker-compose.dev.yml run --rm app python seed_menu_db.py
```

### Port conflicts

If you get "port already in use" errors, either:
1. Stop the conflicting service
2. Change ports in `.env`:
   ```
   APP_PORT=8001
   POSTGRES_PORT=5433
   REDIS_PORT=6380
   ```

### Voice quality issues

In `.env`, try different TTS voices:
```
CONVERSATION_RELAY_TTS_VOICE=alloy    # For Google
CONVERSATION_RELAY_TTS_VOICE=rachel   # For ElevenLabs
```

## Development Workflow

### 1. Making Code Changes

The app directory is mounted as a volume, so changes are reflected immediately:
```bash
# Edit code in your IDE
# The app will auto-reload
# Check logs to see the reload
make logs-app
```

### 2. Database Changes

```bash
# Connect to PostgreSQL
make psql

# Run SQL commands
\dt  # List tables
SELECT * FROM menu_items;
\q   # Quit
```

### 3. Testing

```bash
# Run system health check
make test

# Test voice integration
docker-compose -f docker-compose.dev.yml run --rm app python verify_voice_integration.py

# Run specific tests
docker-compose -f docker-compose.dev.yml run --rm app pytest tests/unit/test_agents.py
```

### 4. Debugging

```bash
# Open shell in app container
make shell

# Inside container:
python
>>> from app.db_async import get_db
>>> # Test database connection
```

## Production Deployment

For production, you'll want to:
1. Use a proper domain instead of ngrok
2. Set up environment variables on your hosting platform
3. Use the production Dockerfile
4. Enable SSL/TLS
5. Set up monitoring and logging

## Clean Up

To completely remove everything (including data):
```bash
make clean
```

This removes:
- All containers
- All volumes (database data)
- All networks

## Tips

1. **Keep ngrok running**: Don't stop services unnecessarily to maintain the same URL
2. **Check logs often**: `make logs-app` is your friend for debugging
3. **Monitor ngrok**: http://localhost:4040 shows all requests/responses
4. **Use the API docs**: http://localhost:8000/docs for testing endpoints
5. **Database GUI**: Use tools like pgAdmin or DBeaver to connect to localhost:5432

## Need Help?

1. Check logs: `make logs`
2. Verify services: `docker-compose -f docker-compose.dev.yml ps`
3. Test system: `make test`
4. Review environment: `cat .env`
5. Check ngrok: http://localhost:4040

Happy developing! 🍱