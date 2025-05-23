# RedBarSushiAI

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License](https://img.shields.io/badge/license-Proprietary-red)
![OpenAI](https://img.shields.io/badge/OpenAI%20Realtime-GPT--4o-brightgreen)

RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It integrates with Twilio for telephony, OpenAI's Realtime API for advanced speech-to-speech interaction, Deliverect for POS/menu management, and leverages a modern async architecture with FastAPI and multi-agent design for complex conversation handling.

## 🚀 Features

- **Real-time Voice Ordering**: Uses Twilio Media Streams, FastAPI WebSockets, and the OpenAI Realtime API for low-latency, conversational interactions
- **Intelligent Menu Interaction**: Handles menu inquiries and recommendations via specialized agents and OpenAI function calling, backed by an async PostgreSQL database
- **POS Integration**: Receives menu updates and submits orders via the Deliverect API
- **Async Multi-Agent Architecture**: Employs a system of coordinated async agents (Frontline, Menu, Cart, Fulfillment, Guardrail) managed by an async FSM-based orchestrator for robust task handling
- **Async Database-Backed**: Uses PostgreSQL with SQLAlchemy 2.0 and asyncpg for non-blocking data access
- **State Management**: Uses Redis for caching and managing conversation state during calls
- **Asynchronous Tasks**: Uses Celery for background task processing (e.g., SMS confirmations, order status polling)
- **Resilient WebSocket Handling**: Optimized WebSocket communication with OpenAI's Realtime API, featuring comprehensive error handling and connection recovery
- **Advanced Logging & Monitoring**: Enhanced diagnostic logging for tracing complex WebSocket interactions and Realtime API events

## 🏗️ Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  Twilio Voice  │  WebSocket Handler  │  FastAPI REST APIs       │
├─────────────────────────────────────────────────────────────────┤
│                      Application Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  FSM Manager   │  Agent Orchestrator │  Conversation Store      │
│                │                     │                          │
│  Multi-Agent System:                                            │
│  - Frontline Agent (Main coordinator)                           │
│  - Menu Agent (Menu inquiries)                                  │
│  - Cart Agent (Order management)                                │
│  - Guardrail Agent (Validation)                                 │
│  - Fulfillment Agent (Order submission)                         │
│  - Escalation Agent (Human handoff)                             │
├─────────────────────────────────────────────────────────────────┤
│                       Integration Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  OpenAI Realtime  │  Deliverect API  │  Twilio API             │
├─────────────────────────────────────────────────────────────────┤
│                         Data Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL       │  Redis           │  Celery                  │
└─────────────────────────────────────────────────────────────────┘
```

### Voice Processing Flow

```
Customer → Twilio → WebSocket → FastAPI Handler
                                      ↓
                              OpenAI Realtime API
                                      ↓
                              FSM + Agent System
                                      ↓
                              Business Logic
                                      ↓
                              Response Generation
                                      ↓
Customer ← Twilio ← WebSocket ← TTS Audio
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (Managed via Docker Compose)
- Redis (Managed via Docker Compose)
- OpenAI API key (with access to `gpt-4o-realtime-preview-2024-10-01`)
- Twilio Account & Phone Number configured for Voice/Media Streams
- Deliverect Account & API Credentials
- ngrok or similar tunneling service for local development

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushiAI
```

2. **Copy and configure environment file:**
```bash
cp .env.example .env
# Edit .env with your API keys and configurations
```

3. **Start with Docker (Recommended):**
```bash
# First time setup or after major changes:
./force_rebuild.sh

# Start all services:
./restart_docker.sh

# For local testing with Twilio webhooks:
./start_docker_with_ngrok.sh
```

4. **Initialize the database:**
```bash
# Seed menu data (run after containers are up):
docker exec -it redbarsushi-app python seed_menu_db.py
```

### Configuration

#### Twilio Webhook Configuration
Configure your Twilio phone number's Voice webhook:
- URL: `https://[your-domain]/voice` or `https://[your-domain]/webhook/voice`
- HTTP Method: POST

#### Deliverect Webhook Configuration
Configure Deliverect to send menu updates:
- URL: `https://[your-domain]/menu_update`
- HTTP Method: POST

## 📁 Project Structure

```
app/
├── api/                    # API endpoints
│   ├── menu/              # Menu-related endpoints
│   ├── order/             # Order-related endpoints
│   ├── voice/             # Voice handling components
│   ├── realtime.py        # OpenAI Realtime API integration
│   └── voice_async.py     # Main WebSocket handler
│
├── agents/                 # Multi-agent system
│   ├── base_async.py      # Base agent class
│   ├── cart_async.py      # Cart management agent
│   ├── factory_async.py   # Agent factory
│   ├── frontline_async.py # Main conversation agent
│   ├── fulfillment_async.py # Order submission agent
│   ├── guardrail_async.py # Validation agent
│   ├── menu_async.py      # Menu inquiry agent
│   └── escalation_async.py # Human handoff agent
│
├── db/                     # Database components
│   ├── crud_menu_async.py # Async CRUD operations
│   └── jsonb_helper.py    # JSONB column helper
│
├── models/                 # SQLAlchemy models
│   ├── menu_async.py      # Menu-related models
│   ├── order_async.py     # Order-related models
│   └── location_async.py  # Location settings
│
├── utils/                  # Utility modules
│   ├── agent_orchestration_async.py # Agent coordination
│   ├── conversation_store_async.py  # Conversation state
│   ├── deliverect_async.py         # Deliverect integration
│   ├── fsm_async.py               # Finite State Machine
│   ├── menu_matcher_db_async.py   # Menu matching logic
│   └── realtime_audio_async.py    # OpenAI Realtime client
│
├── db_async.py            # Async database configuration
├── dependencies.py        # FastAPI dependencies
└── main.py               # FastAPI application entry point
```

## 🔧 Development

### Running Locally

```bash
# Start FastAPI server with auto-reload:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker:
celery -A celery_app worker --loglevel=INFO

# Run tests:
pytest

# Run specific test file:
pytest tests/e2e/test_voice_flow.py
```

### Docker Commands

```bash
# View logs:
docker logs -f redbarsushi-app

# Monitor WebSocket activity:
docker logs -f redbarsushi-app | grep -E "OPENAI|WebSocket|ERROR"

# Access container shell:
docker exec -it redbarsushi-app bash

# Restart specific service:
docker-compose restart app
```

### Code Quality

```bash
# Format code:
black app tests

# Check formatting:
black --check app tests

# Lint code:
ruff check app tests

# Fix linting issues:
ruff check --fix app tests
```

## 🧪 Testing

The project includes comprehensive test coverage:

- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test agent interactions and API endpoints
- **E2E Tests**: Test complete voice flows and order processing

```bash
# Run all tests:
pytest

# Run with coverage:
pytest --cov=app

# Run voice flow tests:
VOICE_HANDLER=realtime pytest tests/e2e/test_realtime_voice_flow.py

# Run in CI mode (no external dependencies):
TESTING=True DISABLE_OPENAI=True pytest
```

## 🚀 Deployment

### Render Deployment

The application is configured for deployment on Render with automatic CI/CD:

1. **Environment Setup**: Configure all required environment variables in Render dashboard
2. **Database**: Use Render's PostgreSQL service
3. **Redis**: Use Render's Redis service or external provider
4. **Build**: Automatic builds triggered on git push
5. **Deployment**:
   - Staging: Push to `staging` branch
   - Production: Push to `main` branch

### Required Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:port/redbarsushi

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_CLIENT_ID=...
DELIVERECT_CLIENT_SECRET=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application
FASTAPI_ENV=production
FORCE_HEADLESS=true
LOG_LEVEL=INFO
VOICE_HANDLER=realtime
```

## 📚 Key Documentation

- [CLAUDE.md](CLAUDE.md) - Comprehensive project documentation and AI assistant context
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Detailed system architecture
- [DEVELOPMENT_ENVIRONMENT.md](DEVELOPMENT_ENVIRONMENT.md) - Development setup guide
- [API_KEY_INSTRUCTIONS.md](API_KEY_INSTRUCTIONS.md) - API key configuration guide

### Implementation Documentation

- [VOICE_MIGRATION_COMPLETE.md](VOICE_MIGRATION_COMPLETE.md) - Voice system migration details
- [WEBSOCKET_FIX_CHANGES.md](WEBSOCKET_FIX_CHANGES.md) - WebSocket stability improvements
- [RENDER_DEPLOYMENT_FIXES.md](RENDER_DEPLOYMENT_FIXES.md) - Render deployment optimizations

## 🔍 Debugging & Monitoring

### Health Check Endpoints

- `/health` - Overall system health
- `/routes-debug` - List all registered FastAPI routes
- `/voice/debug/health` - Voice system specific health

### Monitoring Tools

```bash
# Check Docker health:
./check_docker_health.sh

# Monitor agent activity:
docker logs -f redbarsushi-app | grep "AGENT"

# Watch FSM transitions:
docker logs -f redbarsushi-app | grep "FSM"

# Track OpenAI API calls:
docker logs -f redbarsushi-app | grep "OPENAI"
```

### Common Issues & Solutions

1. **WebSocket Connection Issues**:
   - Verify OpenAI API key is valid
   - Check network connectivity
   - Review WebSocket logs for specific errors

2. **Database Connection Errors**:
   - Ensure PostgreSQL is running
   - Verify DATABASE_URL format
   - Check database permissions

3. **Twilio Integration Problems**:
   - Verify webhook URL is accessible
   - Check Twilio credentials
   - Review TwiML configuration

## 🤝 Contributing

1. Create a feature branch from `staging`
2. Make your changes with appropriate tests
3. Ensure code passes formatting and linting checks
4. Submit a pull request to `staging`
5. After review and staging tests, merge to `main` for production

## 📄 License

This project is proprietary software. See the LICENSE file for details.

## 🆘 Support

For support:
- Check the documentation in `/docs`
- Review debug logs and health endpoints
- Contact the development team
- File an issue in the GitHub repository

---

Built with ❤️ using FastAPI, OpenAI Realtime API, and modern async Python