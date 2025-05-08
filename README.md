# RedBarSushiAI

![Build Status](https://img.shields.io/github/actions/workflow/status/yourusername/RedBarSushiAI/ci.yml?branch=main)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

**RedBarSushiAI** is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It features seamless menu management, real-time order status, and multi-location support—all driven by state-of-the-art voice and messaging APIs.

---

## 🚀 Features
- **Voice-based ordering** using OpenAI Realtime API and Twilio Media Streams
- **Menu inquiries & recommendations** with semantic search capabilities
- **Order validation & processing** with Deliverect POS integration
- **Multi-location support** for restaurant chains
- **Real-time order status & SMS confirmations**
- **WebSocket-based bidirectional audio processing**
- **Multi-agent architecture** with specialized roles
- **Database-backed menu and order management**
- **Progressive fallback mechanisms** for resilience
- **Detailed logging and monitoring**

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis (for Celery and caching)
- OpenAI API key
- Twilio account
- Deliverect API credentials

### Installation
1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/RedBarSushiAI.git
   cd RedBarSushiAI
   ```
2. **Create and activate a virtual environment:**
   ```sh
   python -m venv venv
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Copy and edit environment file:**
   ```sh
   cp .env.example .env
   # Edit .env with your API keys and config
   ```
5. **Create the database:**
   ```sh
   createdb redbarsushi
   ```
6. **Run database migrations:**
   ```sh
   python migrate_db.py
   ```

---

## ▶️ Usage

- Start the Flask server:
  ```sh
  python run.py
  ```
- Start Celery worker (in another terminal):
  ```sh
  celery -A celery_app worker --loglevel=INFO
  ```
- For development with auto-reload:
  ```sh
  FLASK_DEBUG=1 FLASK_APP=run.py flask run
  ```

### Twilio Webhook Configuration

For phone calls to be properly routed to your voice system, configure your Twilio phone number with these webhook settings:

1. In Twilio Console, go to **Phone Numbers** → **Manage** → **Active Numbers**
2. Select your phone number
3. Under **Voice & Fax** configuration:
   - **A Call Comes In**: Set to Webhook
   - **URL**: `https://[your-domain]/voice`
   - **HTTP Method**: POST

Alternatively, you can use any of these equivalent webhook endpoints:
- `https://[your-domain]/voice`
- `https://[your-domain]/webhook/voice`
- `https://[your-domain]/` (root path)

### Voice Debugging

To diagnose voice system issues, these endpoints are available:
- `https://[your-domain]/routes-debug` - List all registered routes
- `https://[your-domain]/voice/debug/health` - Check voice system health
- `https://[your-domain]/healthcheck` - Overall system health check

---

## 🧪 Testing

- Run all tests:
  ```sh
  pytest
  ```
- Run a specific test:
  ```sh
  pytest tests/test_file.py::test_function
  ```
- Run voice flow tests:
  ```sh
  VOICE_HANDLER=orchestrated pytest tests/e2e/test_orchestrated_voice_flow.py
  ```
- Run tests in CI mode (without external API dependencies):
  ```sh
  TESTING=True DISABLE_OPENAI=True pytest
  ```

## 🧹 Code Quality

- Format Python code with Black:
  ```sh
  black app tests
  ```
- Check code formatting without making changes:
  ```sh
  black --check app tests
  ```
- Lint code with Ruff:
  ```sh
  ruff check app tests
  ```
- Fix auto-fixable linting issues:
  ```sh
  ruff check --fix app tests
  ```

---

## 🐳 Docker

The easiest way to get started with RedBarSushiAI is using Docker Compose, which sets up the entire environment including PostgreSQL and Redis.

### Quick Docker Start

```sh
# Start the application with Docker
./start_docker.sh

# Check the health of the Docker containers
./check_docker_health.sh
```

### Docker Compose Commands

```sh
# Start all services in the background
docker-compose up -d

# Stop all services but keep volumes
docker-compose down

# Rebuild and restart if you make changes
docker-compose up -d --build

# View logs from all services
docker-compose logs -f
```

### Troubleshooting Docker

If you encounter database connection issues:

```sh
# Run the database connection fix script
python fix_db_connection.py

# Reset the entire environment (will delete all data)
docker-compose down -v
docker-compose up -d
```

See [DOCKER_USAGE.md](DOCKER_USAGE.md) for comprehensive Docker documentation.

### Headless Mode Configuration

For Docker and production environments, the system is configured to run in headless mode:

```bash
# Required environment variables (already set in docker-compose.yml)
FORCE_HEADLESS=true
OPENAI_REALTIME_NO_DISPLAY=1
CONTAINER_MODE=1
```

---

## 🚦 CI/CD Pipeline

- Automated tests and checks on every push and pull request
- Deploys to staging from `staging` branch
- Deploys to production from `main` branch
- See `.github/workflows/` for details

---

## 📁 System Architecture

### Database Architecture

The system uses PostgreSQL for data persistence with these key models:

1. **Menu Models** (`app/models/menu.py`):
   - `MenuCategory`: Categories of menu items
   - `MenuItem`: Individual menu items with PLUs
   - `MenuModifier`: Modifiers like "Extra cheese" with price changes
   - `MenuModifierGroup`: Groups of modifiers with selection rules
   - `MenuNameVariant`: Maps natural language to specific PLUs

2. **Order Models** (`app/models/order.py`):
   - `Order`: Order details including customer info and status
   - `OrderItem`: Links orders to menu items with quantities
   - `OrderItemModifier`: Stores modifiers applied to order items

### Voice Architecture

Voice interactions use a multi-agent architecture with real-time audio processing:

```
┌───────────────────────────┐
│ OpenAI Realtime Session   │
│  • ASR & partial transcripts   │
│  • VAD-driven events           │
│  • Tool_call & tool_response   │
│  • TTS audio chunks            │
└─┬───────────────────────────┬─┘
  │ tool_call(name, args)     │ audio(TTS)
  ▼                            ▼
┌──────────┐             ┌─────────────┐
│ Frontline│─handoff─▶   │ Fulfillment │
│ Voice    │  or tool    │ Agent       │
│ Agent     ◀─tool───    └─────────────┘
└─┬────────┘
  │ tool calls
  ▼
┌────────────┐  ┌─────────┐  ┌───────────┐
│ Menu Agent │  │ Cart    │  │ Guardrail │
│            │  │ Agent   │  │ Agent     │
└────────────┘  └─────────┘  └───────────┘
```

Key components:
- **WebSocket Server**: Handles real-time audio streaming
- **Voice Activity Detection**: Manages silence detection and timeouts
- **Bidirectional Streaming**: Uses `<Connect><Stream>` for Twilio MediaStreams
- **Multi-Agent System**: Specialized agents for different tasks
- **State Machine**: Controls conversation flow between phases

### Recent Enhancements

#### WebSocket Connection Stability
- Aggressive keep-alive message strategy (200ms-3s intervals)
- Enhanced connection stabilization during critical phases
- Improved greeting sequence with recovery mechanisms
- Better error handling and reconnection logic

#### Route Registration
- Fixed route conflicts with separate registration flags
- Added `/voice` and multiple equivalent webhook paths
- Created diagnostic endpoint at `/routes-debug`
- Improved error handling for route registration

#### System Resilience
- Progressive fallback chains for all critical services
- Redis → Database → Memory cache fallback pathway
- Connection state tracking with recovery actions
- Comprehensive error logging for diagnostics

---

## 🧩 How It Works

### System Workflow

1. **Customer Call**: Customer calls the Red Bar Sushi phone number (Twilio).
2. **Voice Interaction**: Twilio connects to the WebSocket endpoint and streams audio bidirectionally.
3. **Speech Processing**: OpenAI Realtime API processes streaming audio and generates responses.
4. **Agent Orchestration**: The Frontline agent delegates to specialized agents based on intent.
5. **Menu & Order**: The system uses the database (with Redis caching) to answer questions and take orders.
6. **Order Validation**: Orders are validated and processed via Deliverect API.
7. **Order Status**: Real-time order status is provided via SMS (Twilio) and WebSocket audio updates.

**Data Flow:**
- Customer → Twilio → WebSocket → OpenAI Realtime API → Specialized Agents → Deliverect → Customer

### State Machine Workflow

The conversation follows a finite state machine with these states:

1. **GREETING**: Initial greeting and get customer name
2. **MAIN_MENU**: Present main options (order, menu questions, etc.)
3. **MENU_INQUIRY**: Handle menu questions
4. **ORDERING**: Take order details 
5. **ITEM_CLARIFICATION**: Resolve ambiguous items
6. **VALIDATION**: Validate order against constraints
7. **CONFIRMATION**: Confirm order details
8. **PAYMENT**: Handle payment details
9. **FULFILLMENT**: Process order with Deliverect
10. **FOLLOW_UP**: Post-order interaction
11. **STAFF_HANDOFF**: Escalation to human staff
12. **COMPLETION**: End the conversation

---

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) — Comprehensive project documentation
- [CONVERSATION_STORE.md](CONVERSATION_STORE.md) — Conversation state management
- [ADVANCED_AGENTIC_PATTERNS.md](ADVANCED_AGENTIC_PATTERNS.md) — Agent orchestration patterns
- [README-WEBSOCKET.md](README-WEBSOCKET.md) — WebSocket implementation details

---

## 🤝 Contributing

Pull requests are welcome! Please:
- Fork the repo and create a feature branch
- Write tests for new features
- Follow the existing code style
- Open a PR to `development` or `staging`
- Files should not exceed 500 lines of code

---

## 📬 Support

For issues, open a GitHub issue or contact the maintainer.

---

## License

Proprietary - All Rights Reserved

---

## Development Workflow

### Branching Strategy

- `main`: Production-ready code
- `staging`: Pre-production for testing
- `development`: Active development

### Working with Branches

```bash
# Create a new feature branch
git checkout -b feature/my-new-feature

# Make changes, then commit
git add .
git commit -m "Add my new feature"

# Push to remote
git push -u origin feature/my-new-feature

# Create a PR to staging branch when ready
```

## Deployment

The application is deployed on Render with separate environments:

- Production: https://redbarsushi-web.onrender.com
- Staging: https://redbarsushi-staging.onrender.com

### Render WebSocket Configuration

For the WebSocket-based real-time voice system, Render requires this configuration:

```bash
# In Procfile (used by Render)
web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 'run:app'
```

### Twilio Media Streams Configuration

For Twilio Media Streams, TwiML configuration uses Connect/Stream for bidirectional streaming:

```xml
<Response>
    <Say>Welcome to Red Bar Sushi!</Say>
    <Connect>
        <Stream url="wss://your-domain/ws/voice/media" name="redbarsushi_stream" />
    </Connect>
</Response>
```

## Environment Variables

Key environment variables include:

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/redbarsushi

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# OpenAI
OPENAI_API_KEY=sk-...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application Settings
FLASK_APP=run.py
FLASK_ENV=development  # or production
VOICE_HANDLER=realtime
FORCE_HEADLESS=true
```

See `.env.example` for a complete list.