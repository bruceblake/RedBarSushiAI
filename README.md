# RedBarSushiAI

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License](https://img.shields.io/badge/license-Proprietary-red)
![OpenAI](https://img.shields.io/badge/OpenAI%20Realtime-GPT--4o-brightgreen)

AI-powered voice ordering system for Red Bar Sushi that enables customers to place orders and get menu information over the phone using natural language processing and real-time audio.

## 🎯 Overview

RedBarSushiAI is a sophisticated voice ordering system that combines:
- **Real-time voice processing** with OpenAI's Realtime API
- **Multi-agent orchestration** for handling complex conversations
- **POS integration** via Deliverect
- **Robust infrastructure** using FastAPI, PostgreSQL, Redis, and Celery
- **Production-ready deployment** on Render with Docker support

## 🏗️ Architecture

### Core Components

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Twilio Voice      │────▶│   FastAPI Server    │────▶│  OpenAI Realtime    │
│   Media Streams     │     │   (WebSockets)      │     │      API            │
└─────────────────────┘     └──────────┬──────────┘     └─────────────────────┘
                                       │
                            ┌──────────┴──────────┐
                            │                     │
                    ┌───────▼────────┐   ┌───────▼────────┐
                    │  PostgreSQL    │   │     Redis      │
                    │  (Menu/Orders) │   │   (Caching)    │
                    └────────────────┘   └────────────────┘
```

### Multi-Agent System

The system uses specialized agents for different aspects of the conversation:

- **Frontline Agent**: Main conversation coordinator
- **Menu Agent**: Handles menu inquiries and availability
- **Cart Agent**: Manages order items and modifications
- **Guardrail Agent**: Enforces business rules and validates orders
- **Fulfillment Agent**: Processes order completion and payment
- **Escalation Agent**: Manages handoff to human staff

### Voice Processing Flow

```
Customer Call → Twilio → WebSocket → FastAPI Handler
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

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Twilio account with phone number
- OpenAI API key with Realtime API access
- Deliverect account for POS integration

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushiAI
```

2. Create a `.env` file with required variables:
```bash
# Database
DATABASE_URL=postgresql://redbarsushi:password@localhost:5432/redbarsushi
REDIS_URL=redis://localhost:6380/0
REDIS_PORT=6380

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-10-01
OPENAI_REALTIME_VOICE=shimmer

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_API_KEY=...
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_CLIENT_ID=...
DELIVERECT_CLIENT_SECRET=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application
SECRET_KEY=your-secret-key-here
LOG_LEVEL=INFO
VOICE_HANDLER=realtime
CELERY_BROKER_URL=redis://localhost:6380/1
CELERY_RESULT_BACKEND=redis://localhost:6380/1
```

### Docker Development

1. Start all services:
```bash
./start_docker.sh
```

2. Initialize the database:
```bash
docker exec -it redbarsushi-app-1 python -m app.db_init
docker exec -it redbarsushi-app-1 python seed_menu_db.py
```

3. Access the application:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/healthcheck

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start services:
```bash
# Terminal 1: FastAPI server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery worker
celery -A celery_app_fastapi worker --loglevel=INFO

# Terminal 3: Redis (if not using Docker)
redis-server --port 6380

# Terminal 4: PostgreSQL (if not using Docker)
# Ensure PostgreSQL is running on port 5432
```

## 📞 Twilio Configuration

### Webhook Setup

1. In your Twilio Console, configure your phone number's webhook:
   - **Voice & Fax** → **A call comes in** → **Webhook**
   - URL: `https://your-domain.com/voice/webhook`
   - Method: `POST`

2. For local development with ngrok:
```bash
ngrok http 8000
# Use the HTTPS URL provided by ngrok
```

### Media Streams Configuration

The system uses Twilio Media Streams for bidirectional audio:
- Incoming audio: μ-law 8kHz
- Outgoing audio: μ-law 8kHz
- WebSocket endpoint: `/ws/media/{call_sid}`

## 🧪 Testing

### Run All Tests
```bash
pytest tests/
```

### Run E2E Tests
```bash
pytest tests/e2e/
```

### Test Voice Flow
```bash
python test_websocket.py
```

### WebSocket Testing
```bash
python simple_websocket_test.py
```

## 📦 API Endpoints

### Voice Endpoints
- `POST /voice/webhook` - Twilio webhook for incoming calls
- `WS /ws/media/{call_sid}` - WebSocket for media streams
- `POST /voice/tts` - Text-to-speech generation
- `POST /voice/process-transcript` - Process voice transcripts

### Menu Endpoints
- `GET /api/menu/categories` - List menu categories
- `GET /api/menu/items` - List menu items
- `GET /api/menu/items/{item_id}` - Get specific item
- `GET /api/menu/search` - Search menu items

### Order Endpoints
- `POST /api/order/take-order` - Create new order
- `GET /api/order/{order_id}/status` - Get order status
- `POST /api/order/{order_id}/confirm` - Confirm order
- `POST /api/order/{order_id}/modify` - Modify existing order

### Monitoring
- `GET /healthcheck` - System health check
- `GET /api/monitoring/metrics` - Performance metrics
- `GET /api/monitoring/agents` - Agent status

## 🔧 Configuration

### Voice Processing Modes

The system supports multiple voice processing modes:

1. **Realtime Mode** (default):
   - Uses OpenAI Realtime API
   - Low latency, high quality
   - Set `VOICE_HANDLER=realtime`

2. **ConversationRelay Mode** (experimental):
   - Uses Twilio ConversationRelay
   - Enhanced reliability
   - Set `VOICE_HANDLER=conversation_relay`
   - Requires additional Twilio configuration

### Database Schema

Key tables:
- `menu_categories` - Menu category information
- `menu_items` - Menu items with PLU codes
- `menu_modifiers` - Item modifiers and customizations
- `modifier_groups` - Groups of modifiers with selection rules
- `menu_name_variants` - Natural language variants for menu items
- `orders` - Customer orders
- `order_items` - Items within orders
- `locations` - Restaurant locations

### Agent Configuration

Agents can be configured in `app/agents/factory_async.py`:
- Adjust temperature and model parameters
- Customize system prompts
- Configure tool availability

## 🚢 Deployment

### Render Deployment

1. Connect your GitHub repository to Render
2. Configure environment variables in Render dashboard
3. Deploy from `main` branch for production
4. Deploy from `staging` branch for staging

The deployment process:
- Uses `render.yaml` for service configuration
- Runs `fix_render_deploy.sh` during build for environment fixes
- Automatically initializes database on first deployment

### Docker Production

```bash
docker-compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

### Health Monitoring

Monitor system health:
```bash
curl http://localhost:8000/healthcheck
```

Check logs:
```bash
docker logs -f redbarsushi-app-1
```

## 🛠️ Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Check OpenAI API key is valid
   - Verify network connectivity
   - Review WebSocket logs: `docker logs redbarsushi-app-1 | grep WebSocket`

2. **Audio Processing Issues**
   - Ensure audio formats match (μ-law)
   - Check OpenAI Realtime API quotas
   - Verify Twilio Media Streams configuration

3. **Database Connection Errors**
   - Verify DATABASE_URL format
   - Check PostgreSQL is running
   - Ensure database exists: `createdb redbarsushi`

4. **Redis Connection Issues** (Port 6380)
   - Confirm Redis is running on port 6380
   - Check REDIS_URL configuration
   - Verify no port conflicts

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

### Test Connections

```bash
# Test database
python test_db_connection.py

# Test Redis
python test_redis_connection.py

# Test OpenAI
python test_openai_connection.py

# Test WebSocket
python test_websocket.py
```

## 📚 Documentation

### Core Documentation
- [CLAUDE.md](CLAUDE.md) - Comprehensive project context and AI assistant instructions
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Detailed system architecture
- [DEVELOPMENT_ENVIRONMENT.md](DEVELOPMENT_ENVIRONMENT.md) - Development setup guide
- [API Documentation](http://localhost:8000/docs) - Auto-generated FastAPI docs

### Implementation Guides
- [WebSocket Architecture](README-WEBSOCKET-ARCHITECTURE.md) - WebSocket implementation details
- [Voice Migration](VOICE_MIGRATION_COMPLETE.md) - Voice system migration guide
- [WebSocket Fixes](WEBSOCKET_FIX_CHANGES.md) - Recent WebSocket stability improvements
- [ConversationRelay Migration](CONVERSATION_RELAY_MIGRATION.md) - Alternative voice architecture

### Deployment & Operations
- [Render Deployment](RENDER_DEPLOYMENT_FIXES.md) - Render-specific configurations
- [Docker Usage](DOCKER_USAGE.md) - Docker commands and troubleshooting
- [Environment Variables](ENVIRONMENT_VARIABLE_SETUP.md) - Complete env var reference

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines

- Keep files under 500 lines
- Use async/await for I/O operations
- Follow existing code patterns
- Add tests for new features
- Update documentation
- Never implement fallbacks unless specifically asked
- Refer to CLAUDE.md for architectural decisions

### Code Quality

```bash
# Format code
black app tests

# Lint code
ruff check app tests

# Type checking
mypy app
```

## 📄 License

This project is proprietary software. All rights reserved.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Voice processing by [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- Phone integration via [Twilio](https://www.twilio.com/)
- POS integration through [Deliverect](https://www.deliverect.com/)

---

Built with ❤️ using FastAPI, OpenAI Realtime API, and modern async Python