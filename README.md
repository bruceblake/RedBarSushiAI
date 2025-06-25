# RedBarSushiAI

An enterprise-grade AI-powered voice ordering system for restaurants, built with FastAPI, multi-agent AI architecture, and real-time voice processing capabilities.

## Overview

RedBarSushiAI enables customers to place orders via phone using natural language conversation. The system features:

- 🎙️ **Real-time voice processing** with Twilio integration
- 🤖 **Multi-agent AI system** for intelligent conversation handling
- 📊 **Finite State Machine (FSM)** for robust conversation flow management
- 🍱 **Dynamic menu management** with fuzzy matching capabilities
- 💳 **POS integration** via Deliverect API
- 📱 **SMS notifications** for order confirmations
- 🔄 **Async-first architecture** for high performance

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Twilio account with phone number
- OpenAI API key
- Deliverect API credentials (for POS integration)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/RedBarSushiAI.git
   cd RedBarSushiAI
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start with Docker**
   ```bash
   docker-compose up -d
   ```

4. **Initialize database**
   ```bash
   docker exec -it redbarsushi-app-1 python init_db.py
   docker exec -it redbarsushi-app-1 python seed_menu_db.py
   ```

The application will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Flower (Celery): http://localhost:5555

### Local Development

For local development without Docker:

```bash
# Install dependencies
pip install -r requirements.txt  # Production deps
pip install -r requirements-dev.txt  # Development deps

# Set up database
createdb redbarsushi
python init_db.py
python seed_menu_db.py

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

### High-Level Components

1. **Voice Gateway**: Handles Twilio webhooks and audio streaming
2. **Agent Orchestrator**: Coordinates multiple AI agents based on conversation state
3. **FSM Manager**: Manages conversation state transitions
4. **Database Layer**: Async SQLAlchemy with PostgreSQL
5. **Task Queue**: Celery for background processing
6. **Cache Layer**: Redis for session state and caching

### Multi-Agent System

The system uses specialized AI agents, each responsible for specific aspects of the conversation:

- **Greeting Agent**: Handles initial customer interaction
- **Menu Agent**: Answers menu questions and performs item matching
- **Order Agent**: Manages order building and modifications
- **Cart Agent**: Handles cart operations and order summaries
- **Payment Agent**: Processes payment collection
- **General Agent**: Handles off-topic queries and general assistance

### Conversation Flow (FSM)

The conversation follows a defined state machine with these primary states:

```
INITIAL → GREETING → LISTENING → ORDERING → CONFIRMING → 
COLLECTING_INFO → PAYMENT → ORDER_COMPLETE
```

Each state has specific handlers and valid transitions defined in `app/fsm/`.

## Development

### Running Tests

```bash
# Run all tests in Docker (recommended)
./run-docker-tests.sh

# Run specific test categories
./run-docker-tests.sh unit
./run-docker-tests.sh integration
./run-docker-tests.sh e2e

# Run tests locally
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check app/
ruff format app/

# Type checking
mypy app/
```

### Common Commands

```bash
# View logs
docker logs -f redbarsushi-app-1

# Access container shell
docker exec -it redbarsushi-app-1 bash

# Access database
docker exec -it redbarsushi-postgres-1 psql -U redbarsushi -d redbarsushi

# Run Celery worker
docker-compose run --rm app celery -A app.celery_app:celery_app worker --loglevel=info
```

## Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6380/0

# OpenAI
OPENAI_API_KEY=your-key

# Twilio
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890

# Deliverect
DELIVERECT_API_KEY=your-key
DELIVERECT_ACCOUNT_ID=your-account-id
DELIVERECT_CHANNEL_LINK_ID=your-channel-id
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.

Key endpoints:

- `POST /voice/webhook` - Twilio voice webhook
- `GET /menu` - Retrieve menu items
- `POST /orders` - Create order
- `GET /orders/{order_id}` - Get order status
- `GET /health` - Health check

## Deployment

### Docker Deployment

The application includes production-ready Docker configuration:

```bash
# Build image
docker build -t redbarsushi:latest .

# Run container
docker run -d \
  --name redbarsushi \
  -p 8000:8000 \
  --env-file .env \
  redbarsushi:latest
```

### Environment-Specific Configuration

- **Staging**: Uses `.env.staging` 
- **Production**: Uses `.env.production`

Both environments are deployed on Render with automatic deployments from respective branches.

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Verify DATABASE_URL is correct
   - Ensure PostgreSQL is running
   - Check network connectivity

2. **Redis connection errors**
   - Verify REDIS_URL (note: uses port 6380)
   - Ensure Redis is running

3. **Voice webhook failures**
   - Verify Twilio webhook URL is publicly accessible
   - Check Twilio credentials
   - Review webhook logs

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export DEBUG=true
```

## Contributing

1. Create a feature branch from `development`
2. Make changes following existing patterns
3. Add/update tests as needed
4. Submit PR with clear description

### Development Guidelines

- Keep files under 1000 lines
- Follow async patterns throughout
- Use type hints
- Add comprehensive error handling
- Write tests for new features

## License

Proprietary - All rights reserved

## Support

For issues or questions:
- Create an issue in the repository
- Check existing documentation in `/docs`
- Review troubleshooting guide