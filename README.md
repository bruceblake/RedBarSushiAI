# RedBarSushiAI

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License](https://img.shields.io/badge/license-Proprietary-red)
![OpenAI](https://img.shields.io/badge/OpenAI%20Realtime-GPT--4o-brightgreen)

RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It integrates with Twilio for telephony, OpenAI's Realtime API for advanced speech-to-speech interaction, Deliverect for POS/menu management, and leverages a modern async architecture with FastAPI and multi-agent design for complex conversation handling.

🚀 Features
- **Real-time Voice Ordering**: Uses Twilio Media Streams, FastAPI WebSockets, and the OpenAI Realtime API for low-latency, conversational interactions.
- **Intelligent Menu Interaction**: Handles menu inquiries and recommendations via specialized agents and OpenAI function calling, backed by an async PostgreSQL database.
- **POS Integration**: Receives menu updates and submits orders via the Deliverect API.
- **Async Multi-Agent Architecture**: Employs a system of coordinated async agents (Frontline, Menu, Cart, Fulfillment, Guardrail) managed by an async FSM-based orchestrator for robust task handling.
- **Async Database-Backed**: Uses PostgreSQL with SQLAlchemy 2.0 and asyncpg for non-blocking data access.
- **State Management**: Uses Redis for caching and managing conversation state during calls.
- **Asynchronous Tasks**: Uses background tasks for processing (e.g., SMS confirmations).
- **Resilient WebSocket Handling**: Optimized WebSocket communication with OpenAI's Realtime API, featuring comprehensive error handling and connection recovery.
- **Advanced Logging & Monitoring**: Enhanced diagnostic logging for tracing complex WebSocket interactions and Realtime API events.

🛠️ Quick Start
## Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (Managed via Docker Compose)
- Redis (Managed via Docker Compose)
- OpenAI API key (with access to the latest Realtime API models, specifically `gpt-4o-realtime-preview-2024-12-17`)
- Twilio Account & Phone Number configured for Voice/Media Streams
- Deliverect Account & API Credentials (including a configured Menu Update Webhook URL pointing to this service)
- ngrok or similar tunneling service for local development testing with Twilio webhooks.

## Installation (Primarily for understanding codebase; Docker is recommended for running)
1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushiAI
```

2. **(Optional) Create and activate a virtual environment:**
```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. **(Optional) Install dependencies (handled by Docker setup):**
```bash
# Ensure build tools and libpq-dev are installed if running locally
# sudo apt-get update && sudo apt-get install build-essential libpq-dev

pip install -r requirements.txt
```

4. **Copy and edit environment file:**
```bash
cp .env.example .env

# Edit .env with your API keys and other configurations
```

5. **Database Setup (Handled by Docker Compose & Seeding Script):**
   * The Docker Compose setup will create the PostgreSQL container and database (redbarsushi).
   * Initial Menu Seeding: The application **does not** load menu data from file on startup. The database must be seeded initially.
     * Use the dedicated seeding script: `python seed_menu_db.py` (run inside the app container or with appropriate DB connection info). This likely reads `menu_data.json`.
     * Alternatively, ensure Deliverect pushes a full menu via the `/menu_update` webhook after initial setup.

▶️ Usage (Docker Recommended)
Refer to the 🐳 Docker section below for the primary method of running the application and its dependencies (PostgreSQL, Redis).

## Twilio Webhook Configuration
Configure your Twilio phone number's Voice -> A Call Comes In webhook:
- URL: https://[your-ngrok-domain-or-render-url]/ (or /voice, /webhook/voice depending on your registered routes)
- HTTP Method: POST

## Deliverect Webhook Configuration
Configure Deliverect to send menu updates via POST to:
- https://[your-ngrok-domain-or-render-url]/menu_update

## Debugging Endpoints
- /healthcheck: Overall system health.
- /routes-debug: List registered FastAPI routes.
- /voice/debug/health: (If implemented) Voice system specific health.

🧪 Testing
Run all tests:
```bash
pytest
```

Run a specific test:
```bash
pytest tests/test_file.py::test_function
```

Run voice flow tests (ensure environment uses async worker):
```bash
# May require specific setup or mocks if running outside Docker
VOICE_HANDLER=realtime pytest tests/e2e/test_realtime_voice_flow.py
```

Run tests in CI mode (without external API dependencies):
```bash
TESTING=True DISABLE_OPENAI=True pytest
```

🧹 Code Quality
- Format: `black app tests`
- Check Format: `black --check app tests`
- Lint: `ruff check app tests`
- Fix Lint: `ruff check --fix app tests`

🐳 Docker
Use Docker Compose for a consistent development and production environment including PostgreSQL and Redis.

## Quick Docker Start
```bash
# First time or after major config changes:
./force_rebuild.sh

# Start/Restart containers using the fixed configuration:
./restart_docker_fixed.sh 

# For local testing with Twilio, start with ngrok tunneling:
./start_docker_with_ngrok.sh

# Check health:
./check_docker_health.sh

# View logs:
docker logs -f redbarsushi-app

# Monitor WebSocket activity:
docker logs -f redbarsushi-app | grep "OPENAI\|WebSocket\|ERROR"
```

## Docker Compose Commands
```bash
# Start all services with the fixed configuration:
docker-compose -f docker-compose.fixed.yml up -d

# Stop services:
docker-compose -f docker-compose.fixed.yml down

# Force rebuild image and restart:
docker-compose -f docker-compose.fixed.yml up -d --build

# View logs in real-time:
docker-compose -f docker-compose.fixed.yml logs -f
```

## Environment Setup
Make sure your `.env.development` file contains the following key settings:
```
# OpenAI Settings (Critical for Realtime API)
OPENAI_API_KEY=your_valid_api_key
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview-2024-12-17
OPENAI_REALTIME_VOICE=shimmer

# Database and Redis settings are handled by docker-compose.fixed.yml
```

## 🚦 CI/CD Pipeline
The project uses GitHub Actions for Continuous Integration and Render for Continuous Deployment:

- **Staging:** Automatic deployment to staging from the `staging` branch
- **Production:** Automatic deployment to production from the `main` branch
- **Testing:** Runs tests and linting on each PR and push to main branches

## 📁 System Architecture

### 1. Core Philosophy
A FastAPI application utilizing native `asyncio` for concurrency and WebSocket support. It integrates with the **OpenAI Realtime API** for voice interactions and an internal **Async Multi-Agent System** for managing conversational logic and tasks. Data persistence relies on **PostgreSQL** with asyncpg for non-blocking operations, caching/session state on **Redis**, and external order management via **Deliverect**.

### 2. Database Architecture
The system uses PostgreSQL for data persistence with these key models:

- **Menu Models** (`app/models/menu.py`):
  - Categories, Items, Modifiers, Modifier Groups
  - Variants for natural language mapping to PLUs
  - SQLAlchemy 2.0 with asyncpg for async database operations

- **Order Models** (`app/models/order.py`):
  - Orders, Order Items, Order Item Modifiers
  - Links to Deliverect via PLUs

- **Location Model** (`app/models/location.py`):
  - Location settings, business hours, Deliverect connection details

### 3. Voice Architecture & Async WebSocket Implementation

- **Server:** Uvicorn with native asyncio workers.
- **WebSocket Handler:** FastAPI WebSocket endpoint (`@app.websocket("/ws/media/{call_sid}")`).
- **Concurrency:** Native asyncio tasks (`asyncio.create_task()`) manage concurrent operations within the WebSocket handler.
- **OpenAI Connection:** Uses `aiohttp` for async WebSocket connection to `wss://api.openai.com/v1/realtime?model=...`
- **Session Config:** Sends `session.update` message after connection, configured according to OpenAI Realtime API docs.
- **Audio Flow:** Twilio `media` events -> `input_audio_buffer.append` sent to OpenAI -> OpenAI `response.audio.delta` received -> Twilio WebSocket message sent back.
- **Transcript Event:** Uses asyncio queues for event processing with clean error handling and resource management.
- **Finite State Machine:** Implements an async FSM for robust conversation flow management with specialized state handlers.
- **Agent Integration:** Uses dependency injection for components and clean separation of concerns.
- **Key Files:** 
  - `app/api/voice_async.py` - WebSocket endpoint and task management
  - `app/utils/fsm_async.py` - Async FSM implementation
  - `app/utils/agent_orchestration_async.py` - Async agent orchestration
  - `app/db/session_async.py` - Async database session management

### 4. Multi-Agent System & Orchestration
The system uses a sophisticated multi-agent architecture with an Async Finite State Machine (FSM):

- **AsyncConversationFSM** (`app/utils/fsm_async.py`):
  - Manages conversation states and transitions
  - Specialized state handlers for each conversation state
  - Event-driven state transitions

- **AsyncAgentOrchestrator** (`app/utils/agent_orchestration_async.py`):
  - Coordinates between FSM and specialized agents
  - Routes voice input to appropriate agents based on FSM state
  - Manages tool execution and agent handoffs

- **Specialized Async Agents**:
  - **AsyncFrontlineAgent**: Main voice interface, delegates to specialists
  - **AsyncMenuAgent**: Handles menu inquiries
  - **AsyncCartAgent**: Manages order items and modifications
  - **AsyncFulfillmentAgent**: Processes order completion
  - **AsyncGuardrailAgent**: Enforces business rules
  - **AsyncEscalationAgent**: Manages handoff to human staff

## 🧩 How It Works

### System Workflow (Async Implementation)
1. **Customer Call:** Customer calls the Twilio number.
2. **TwiML & WS Connect:** FastAPI endpoint returns TwiML instructing Twilio to `<Connect>` to the app's `/ws/media/{call_sid}` WebSocket endpoint.
3. **Async Realtime Session:** The async WebSocket handler:
   * Accepts Twilio WebSocket connection.
   * Connects to OpenAI Realtime API WebSocket using `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17&voice=shimmer`.
   * Sends `session.update` with audio format configuration and system instructions.
   * Creates asyncio tasks to manage bidirectional audio streams.
   * Uses asyncio queues for event processing with robust error handling.
4. **Conversation Loop:**
   * User speaks; audio streamed Twilio -> App WS -> OpenAI WS.
   * OpenAI VAD detects end of speech.
   * OpenAI sends transcript event.
   * App WS handler receives transcript, passes it to FSM and agent orchestrator.
5. **Async Agent Orchestration:** FSM determines the current state and appropriate agent, processes input, potentially calls tools, and generates a text response.
6. **TTS Response:** App WS handler:
   * Creates a conversation item with agent's response text
   * Sends `conversation.item.create` message with the `item` containing the response 
   * Requests TTS with a `response.create` message with a unique response_id
7. **Audio Output:** OpenAI generates TTS audio, then:
   * Streams audio chunks via `response.audio.delta` events
   * App WS handler forwards these audio chunks to Twilio WS
   * User hears the spoken response in real-time
8. **Order Processing:** Cart building, validation, and Deliverect submission occur based on FSM state.
9. **Call End:** User or system hangs up, WebSockets close, tasks are properly cancelled, and resources are cleaned up.

### Finite State Machine Workflow
The Async FSM manages conversation flow through these primary states:
- **INITIAL**: Setup phase
- **GREETING**: Initial customer interaction
- **MAIN_MENU**: Central decision point
- **ORDERING**: Building the cart
- **VALIDATION**: Checking order constraints
- **CONFIRMATION**: Getting final approval
- **FULFILLMENT**: Submitting to POS
- **COMPLETION**: End of successful interaction
- **ERROR**: Handling exceptional situations
- **ESCALATION**: Transferring to human staff

Each state has a specialized async handler, and transitions are triggered by events from user input, agent decisions, or system conditions.

## 📚 Documentation
- [CLAUDE.md](CLAUDE.md) — Comprehensive project documentation
- [CONVERSATION_STORE.md](CONVERSATION_STORE.md) — Conversation state management
- [ADVANCED_AGENTIC_PATTERNS.md](ADVANCED_AGENTIC_PATTERNS.md) — Agent orchestration patterns
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Detailed system architecture documentation
- [OPENAI_REALTIME_FIX_UPDATED.md](OPENAI_REALTIME_FIX_UPDATED.md) — Fixes for OpenAI Realtime API integration
- [OPENAI_REALTIME_PAYLOAD_FIXES.md](OPENAI_REALTIME_PAYLOAD_FIXES.md) — Details on OpenAI Realtime payload format updates
- [TEST_AFTER_API_KEY_FIX.md](TEST_AFTER_API_KEY_FIX.md) — Testing instructions after API key and WebSocket fixes

## 🤝 Contributing
Please read our contribution guidelines before submitting pull requests.

## 📬 Support
For support, contact the development team or file an issue in the GitHub repository.

## License
This project is licensed under a proprietary license. See the LICENSE file for details.

## Development Workflow
1. Create a feature branch from `staging`
2. Develop and test your changes
3. Submit a PR to `staging`
4. After approval and merge, test on staging environment
5. Submit a PR from `staging` to `main` for production deployment

## Deployment
The application is deployed on Render:

### Render WebSocket Configuration
The application runs using Uvicorn with asyncio workers for efficient async WebSocket handling. Your `render.yaml` should reflect this:

```yaml
# Example render.yaml service definition
services:
  - type: web
    name: redbarsushi-app
    env: python
    plan: standard # Adjust as needed
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 4"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.12
      # Add other envVars from your .env file using Render secrets
      - key: DATABASE_URL
        fromDatabase:
          name: redbarsushi-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: redbarsushi-redis
          property: connectionString
      # ... etc ...
```

### Twilio Media Streams Configuration
TwiML configuration must use `<Connect><Stream>` pointing to the correct WebSocket endpoint including the CallSid:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <!-- Brief initial prompt from Twilio (Optional) -->
    <Say>Connecting you to Red Bar Sushi AI. Please wait.</Say>
    <Connect>
        <!-- Ensure wss:// for production -->
        <Stream url="wss://your-render-domain.onrender.com/ws/media/{{CallSid}}" />
    </Connect>
    <!-- Fallback message if WebSocket connection fails -->
    <Say>Sorry, we couldn't connect right now. Please try again later.</Say>
</Response>
```

### Environment Variables
Key environment variables include:
```
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:port/redbarsushi

# Redis
REDIS_URL=redis://host:port/0
CELERY_BROKER_URL=redis://host:port/1 # Often same as REDIS_URL or different DB
CELERY_RESULT_BACKEND=redis://host:port/1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL="gpt-4o-realtime-preview-2024-12-17" # Latest model version
OPENAI_REALTIME_VOICE="shimmer" # Or alloy, nova, etc.
OPENAI_REALTIME_INSTRUCTIONS="You are..." # Your full system prompt

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com # Or production URL

# Application Settings
FASTAPI_ENV=production # Or development
FORCE_HEADLESS=true # Keep for Docker/Render

# Server Settings (Often set in start command)
# PORT=8080
# WORKERS=4
```

See `.env.example` for a complete list and add any new configuration variables introduced.