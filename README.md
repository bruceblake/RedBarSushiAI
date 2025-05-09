RedBarSushiAI
![alt text](https://img.shields.io/github/actions/workflow/status/yourusername/RedBarSushiAI/ci.yml?branch=main)

![alt text](https://img.shields.io/badge/python-3.11%2B-blue)

![alt text](https://img.shields.io/badge/license-Proprietary-red)
RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It integrates with Twilio for telephony, OpenAI's Realtime API for advanced speech-to-speech interaction, Deliverect for POS/menu management, and leverages a multi-agent architecture for complex conversation handling.

<!-- UPDATE: Added a slightly more technical summary -->

🚀 Features
Real-time Voice Ordering: Uses Twilio Media Streams, Flask-Sock WebSockets, and the OpenAI Realtime API for low-latency, conversational interactions.
Intelligent Menu Interaction: Handles menu inquiries and recommendations via specialized agents and OpenAI function calling, backed by a PostgreSQL database.
POS Integration: Receives menu updates and submits orders via the Deliverect API.
Multi-Agent Architecture: Employs a system of coordinated agents (Frontline, Menu, Cart, Fulfillment, Guardrail) managed by an FSM-based orchestrator for robust task handling.
Database-Backed: Uses PostgreSQL as the single source of truth for menu and order data (updated via Deliverect webhook).
State Management: Leverages Redis for caching and managing conversation state during calls.
**\_README.md`.
Updated README.md (Incorporating Changes):
Asynchronous Tasks:** Uses Celery for background processing (e.g., SMS confirmations).
Resilience:```markdown
RedBarSushiAI
![alt text](https://img.shields.io/github/actions/workflow/status/yourusername/RedBarSushiAI/ci.yml?branch=main)

![alt text](https://img.shields.io/badge/python-3.11%2B-blue)

![alt text](https://img.shields.io/badge/license-Proprietary-red)
RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It integrates real-time voice processing via Twilio and OpenAI with a sophisticated multi-agent backend built on Flask.
🚀 Features
Real-time Voice Ordering: Uses Twilio Media Streams, Flask-Sock, Gevent, and the OpenAI Realtime API for low-latency conversations.
Menu Inquiries & Recommendations: Database-backed menu with Redis caching and advanced matching (exact, fuzzy, potentially AI).
Order Validation & Processing: Integrates with Deliverect API for POS submission using PLU codes.
Multi-Agent Architecture: Specialized agents (Frontline, Menu, Cart, Fulfillment, Guardrail) handle distinct tasks, orchestrated by an FSM.
State Management: Uses Redis for conversation state and cart management per call session.
External Menu Updates: Menu dynamically updated via a webhook (e.g., /menu_update) typically triggered by Deliverect.
(Optional) SMS Confirmations: Uses Celery and Twilio for asynchronous order status updates.
Resilience: Incorporates fallback mechanisms for caching and potentially other services.
Detailed Logging & Monitoring: Configurable logging levels and potential integration with tracing tools.
🛠️ Quick Start
Prerequisites
Python 3.11+
PostgreSQL
Redis (for Celery broker, caching, conversation state)
gevent library (pip install gevent) - Required for production server.
OpenAI API key (enabled for Realtime API access)
Twilio Account & Phone Number
Deliverect Account & API Credentials
ngrok or similar tunneling service for local development testing with Twilio webhooks.
Installation
Clone the repository:
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushi Includes fallback mechanisms for caching and error handling patterns.
Use code with caution.
Bash
Detailed Logging & Monitoring: Comprehensive logging for diagnostics and tracingAI
Use code with caution.
Set up Python Environment: (Using a virtual environment is recommended)
python -m venv venv

# On macOS/Linux:

source venv/bin/activate

# On Windows:

venv\Scripts\activate
pip install -r requirements.txt
Use code with caution.
Bash
(integration with agent framework tracing).

<!-- UPDATE: Refined features list for clarity and accuracy -->

🛠️ Quick Start
Prerequisites
Python 3.11+
Docker & Docker Compose
PostgreSQL ( ```(Ensure gevent is included in`requirements.txt`)
Configure Environment:
cp .env.example .env

# Edit .env with your specific API keys, DB/Redis URLs, etc.

# Ensure OpenAI Realtime specific variables are set (e.g., MODELManaged via Docker Compose)

Use code with caution.
Bash
Redis (Managed via Docker Compose)
OpenAI API key (with access to Realtime API, e.g., GPT-4o Realtime models)
Twilio Account & Phone Number configured for Voice/Media Streams
Deliverect Account & API Credentials (including a configured Menu Update Webhook URL pointing to this service)
ngrok or similar tunneling service for local development testing with Twilio webhooks.

<!-- UPDATE: Added Docker, ngrok, clarified API key type, webhook prerequisite -->

Installation (Primarily for understanding codebase; Docker is recommended for running)
Clone the repository:
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushiAI
Use code with caution.
Sh
(, VOICE)
Optional) Create and activate a virtual environment:
python -m venv venv

# On macOS/Linux:

source venv/bin/activate

# On Windows:

venv\Scripts\activate
Use code with caution.
Sh
Set up Database:
Ensure PostgreSQL server is running.
Create the database: createdb redbarsushi (or use Docker Compose).
Initialize schema: Run any necessary database migration commands (e.g., if using Flask-Migrate: flask db upgrade). Verify schema matches models (including snoozed_until column).
Initial Menu Seeding (IMPORTANT):
The application no longer automatically loads menu data from menu_data.json on startup.
Option A (Manual Seed): Run the provided seeding script (requires menu data source like JSON or Deliverect API access configured):

# Example, adjust command as needed

python seed_menu_3. **(Optional) Install dependencies (handled by Docker setup):**
Use code with caution.
Bash

# Ensure build tools and libpq-dev are installed if running locally

# sudo apt-get update && sudo apt-get install build-essential libpq-dev

pip install -r requirements.txt
Use code with caution.
Sh
Copy and edit environment file:
cp .env.example .env

# Edit .env with your API keys and other configurations

Use code with caution.
Sh
Database Setup (Handled by Docker Compose & Seeding Script):
The Docker Compose setup will create the PostgreSQL container and database (redbarsushi).
Initial Menu Seeding: Thedb.py --file menu_data.json
Use code with caution.
Option B (Webhook): Ensure your Deliverect account is configured to POST the initial full menu to your /menu_update webhook endpoint after the service starts.
▶️ Usage
Production / Docker (Recommended for Real-time Voice)
The system relies on gevent for handling concurrent WebSocket connections efficiently, as recommended by Flask-Sock. Use Docker Compose for easy setup.
Build/Rebuild Docker Environment:

# application **does not** load menu data from file on startup. The database must be seeded initially.

    *   Use the dedicated seeding script: `python seed_menu_db.py` (run inside the app container or with appropriate DB connection info For the first time or after major config/dependency changes:

./force_rebuild.sh

# Then). This likely reads `menu_data.json`.

    *   Alternatively, ensure Deliverect pushes a full menu via start (or use this directly for subsequent starts):

./restart_docker.sh
the `/menu_update` webhook after initial setup.
Use code with caution.
Bash

<!-- UPDATE: Clarified Docker focus, removed manual DB creation/```
*(These scripts should configure Gunicorn to run with `-k gevent`)*

2. **Start Celery Worker (if using async tasks):**
```bash
# Typically run in a separate container managed by docker-compose
#migration steps, added seeding step -->

▶️ Usage (Docker Recommended)
Refer to the 🐳 Docker section below for the primary method of running the application and its dependencies (PostgreSQL, Redis).
Running Command inside container might be:
celery -A celery_app worker --loglevel=INFO

````
Use code with caution.
Local Development (Limited WebSocket Performance)
Using flask run is suitable for basic HTTP endpoint testing but not recommended for testing the real-time voice functionality due to the limitations of the development server with concurrent WebSocket handling.
# Locally (Development/Debugging - Requires Manual Dependency Setup)

*   **Start the Flask/Gevent server:**
    ```sh
    # Ensure gevent monkey patching is active (likely in wsgi.py)
    # Ensure DB and Redis are running and accessible
    gunicorn -k gevent --workers 4 --worker-connections 1000 --bind 0.0.0.0:5050 wsgi:app
    # Adjust port, workers, connections as needed
    ```
*   **Start Celery worker (in another terminal):**
    ```sh
    # Ensure Redis broker is running
    celery -A celery_app worker --loglevel=INFO
    ```
*   **Flask Development Server (NOT recommended for WebSocket testing):**
    ```sh
    # This uses Werkzeug, may not work correctly with gevent-based WebSocket handlers
    # FLASK_DEBUG=1 FLASK_APP=wsgi:app flask run --port 5050
    ```

<!-- UPDATE: Updated run commands to reflect Gevent/Gunicorn usage, warned against Flask dev server for WS -->
### Twilio Webhook Configuration

For phone calls to be properly routed to your voice system, configure your Twilio phone number with these webhook settings:

1.  In Twilio Console, go to ** For basic HTTP testing ONLY:
FLASK_DEBUG=1 FLASK_APP=run.py flask run
Use code with caution.
Bash
(Always use the Docker/Gunicorn/Gevent setup for voice testing)
Twilio Webhook Configuration
Configure your Twilio phone number's Voice -> A Call Comes In webhook:
URL: https://[your-ngrok-domain-or-render-url]/ (or /voice, /webhook/voice depending on your registered routes)
HTTP Method: POST
Deliverect Webhook Configuration
Configure Deliverect to send menu updates via POST to:
https://[your-ngrok-domain-or-render-url]/menu_update
Debugging Endpoints
/healthcheck: Overall system health.
/routes-debug: List registered Flask routes.
/voice/debug/health: (If implemented) Voice system specific health.
🧪 Testing
(Keep existing testing commands, ensure they run in the correct environment if testing voice)
Run all tests:
Use code with caution.
Phone Numbers** → **Manage** → **Active Numbers**
Select your phone number
Under Voice & Fax configuration:
A Call Comes In: Set to Webhook
URL:bash
pytest
- Run a specific test:
```bash
pytest tests/test_file.py::test_function
Use code with caution.
Run voice flow tests (ensure environment uses Gevent worker):
``` https://[your-public-domain]/ (or `/voice`, `/webhook/voice` - ensure the target route exists and generates the correct TwiML). Use your `ngrok` HTTPS URL during local development.
HTTP Method:bash
May require specific setup or mocks if running outside Docker
VOICE_HANDLER=realtime pytest tests/e2e/test_realtime_voice_flow.py
Use code with caution.
Run tests in CI mode (without external API dependencies):
TESTING=True DISABLE POST
Use code with caution.
Bash
<!-- UPDATE: Adjusted recommendation to point to root path as primary, added ngrok mention -->
Deliverect Menu_OPENAI=True pytest
Update Webhook
Configure your Deliverect account to send menu updates via POST request to:
https://[your-public-domain]/menu_update
<!-- ADD: New section for Deliverect Webhook -->
Voice Debugging & Health```
🧹 Code Quality
(Keep existing code quality commands)
Format: black app tests
Check Format: black --check app tests
Lint: ruff check app tests
Fix Lint: ruff check --fix app tests
🐳 Docker
Use Docker Compose for a consistent development and production environment including PostgreSQL and Redis.
Quick Docker Start
# First time or after major config changes (builds image with Gevent worker):
./force_rebuild.sh

check

*   `/healthcheck`: Overall system health check.
*   `/routes-debug`: (If available) List all registered routes.
*   `/realtime/capabilities`: (If available) Show Realtime API capabilities.
*   `/# Start/Restart containers using the built image:
./restart_docker.sh

# Check health:
./check_docker_health.sh

# View logs:
docker-compose logs -f redbarsushi-app #realtime/healthcheck`: (If available) Healthcheck for the realtime service components.

<!-- UPDATE: Grouped diagnostic Adjust service name if needed
Use code with caution.
Bash
Docker Compose Commands
---

## 🧪 Testing

*(Section looks okay, assuming tests are adapted for the Gevent environmentbash
# Start all services detached:
docker-compose up -d

# Stop services:
docker-compose down

# Force rebuild image and restart:
docker-compose up -d if they interact with async components)*

---

## 🧹 Code Quality

*(Section looks okay)*

---

## 🐳 Docker

The recommended way to run RedBarSushiAI is using Docker Compose, which manages the Flask application, PostgreSQL, and Redis containers.

### Quick Docker Start

1.  **Ensure `.env` file is configured.**
2.  **Force Initial Build (Important after major changes or first run):**
    ```sh
    # Stops containers, removes old image, rebuilds, restarts
    ./force_rebuild.sh
    ```
3.  **Start/Restart Normally:**
    ```sh
    # Use this for subsequent starts/stops
    ./restart_docker.sh
    ```
4.  **Initial Menu Seed (If DB is empty):**
    ```sh
    # Run the seeding script inside the running app container
    docker exec -it <your_app_container_name> python seed_menu_db.py
    # Or trigger a full menu publish from Deliverect to the /menu_update webhook
    ```
5.  **Check Health:**
    ```sh
    ./check_docker_health.sh
    # Or access the /healthcheck endpoint
    ```

<!-- UPDATE: Added force_rebuild step, clarified initial seeding -->
### Docker Compose Commands

*(Section looks okay)*

### Troubleshooting Docker

*(Section looks okay)*

### Headless Mode Configuration

*(Section looks okay)*

---

## 🚦 CI/CD Pipeline

*(Section looks okay)*

---

## 📁 System Architecture

### 1. Core Philosophy

A Flask (WSGI) application utilizing **Gevent** for concurrency and **Flask-Sock** for native WebSocket handling within the Gevent environment. It integrates tightly with the **OpenAI Realtime API** for voice interactions and an internal **Multi-Agent System** (built using an Agent SDK like `openai-python-agents`) for managing conversational logic and tasks. Data persistence relies on **PostgreSQL**, caching/session state on **Redis**, and external order management via **Deliverect**.

<!-- UPDATE: Added core philosophy summary -->
### 2. Database Architecture

*(Section looks okay, assuming model fields align with Deliverect and `snoozed_until` fix)*

### 3. Voice Architecture & Realtime API Integration (`app/routes/realtime.py`)

*   **Server:** Gunicorn with `-k gevent` worker.
*   **WebSocket Listener:** Flask-Sock (`@sock.route("/ws/media/<call_sid>")`).
*   **Concurrency:** Gevent Greenlets (`gevent.spawn`) manage concurrent tasks within the WebSocket handler (audio forwarding, OpenAI processing, heartbeats).
*   **OpenAI Connection:** Uses `websocket-client` library (made non-blocking via `gevent.monkey.patch_all()`) to connect to `wss://api.openai.com/v1/realtime?model=...`
*   **Session Config:** Sends `session.update` message after connection, configured according to OpenAI Realtime API docs (using `g711_ulaw`, correct `turn_detection`, `tools` definition, no invalid parameters like `sample_rate_hz` or `audio_output_enabled`).
*   **Audio Flow:** Twilio `media` events -> `input_audio_buffer.append` sent to OpenAI -> OpenAI `response.audio.delta` received -> Twilio `media` event sent back.
*   **Transcript Event:** Listens for `conversation.item.input_audio_transcription.completed` for final user transcript.
*   **Agent Interaction:** Passes final user transcript to `FrontlineAgent.process_voice_input`.
*   **Agent TTS Flow:** Takes text response from Agent -> Sends `conversation.item.create` (type `input_text`) -> Sends `response.create` -> Receives `response.audio.delta` for TTS.
*   **Tool Flow:** Receives `tool_calls` from OpenAI -> Executes corresponding local Python tool function (`execute_rbs_tool_sync`) -> Sends `conversation.item.create` (type `function_call_output`) -> Sends `response.create`.
*   **Key File:** `app/routes/realtime.py` orchestrates this entire interaction.

<!-- UPDATE: Detailed description of the final Gevent/WebSocket/OpenAI flow -->
### 4. Multi-Agent System & Orchestration

*(Section describing Frontline, Menu, Cart, etc., agents and FSM/AgentGraph/SlotStore looks okay. Assumes agent logic is compatible with Gevent environment).*

---

## 🧩 How It Works

### System Workflow (Updated for Realtime API)

1.  **Customer Call:** Customer calls Twilio number.
2.  **TwiML Fetch:** Twilio sends HTTP POST to `/` (or `/voice`), receives TwiML.
3.  **Greeting & WS Connect:** Twilio speaks initial `<Say>`, then establishes WebSocket connection to `/ws/media/CALL_SID` endpoint handled by Flask-Sock/Gevent.
4.  **OpenAI Session:** Backend connects to OpenAI Realtime API via WebSocket, sends `session.update` config.
5.  **Proactive Greeting:** Backend triggers initial TTS greeting via OpenAI (`conversation.item.create` + `response.create`). Audio streams OpenAI -> Backend -> Twilio -> User.
6.  **User Interaction Loop:**
    *   User speaks. Audio streams User -> Twilio -> Backend ( --build

# View logs (all services):
docker-compose logs -f
`input_audio_buffer.append`) -> OpenAI.
    *   OpenAI VAD detects speech end.
    *   OpenAI A```

*(Keep Troubleshooting Docker and Headless Mode Configuration sections)*

---

## 🚦 CI/CD Pipeline

*(Keep existing CI/CD section)*

---

## 📁 System Architecture

*(Keep existing Database Architecture section)*

### Voice Architecture & WebSocket Implementation

The real-time voice interaction relies on a specific stack:
- **Flask + Flask-Sock:** Handles incoming WebSocket connections from Twilio on the `/ws/media/<CallSid>` route.
- **Gunicorn + Gevent Worker:** Provides the WSGI server environment optimized for concurrent I/O using greenlets, as recommended by Flask-Sock. `gevent.monkey.patch_all()` is used for compatibility.
- **OpenAI Realtime API:** Connected via a separate outbound WebSocket (using `websocket-client` library within a greenlet) for STT, NLU, TTS, and Tool Calling.
- **Twilio Media Streams:** Provides the bidirectional audio path via the initial WebSocket.
- **`app/routes/realtime.py`:** Contains the core `handle_media_realtime` function orchestrating the Gevent greenlets for:
    - Forwarding Twilio audio chunks to OpenAI (`input_audio_buffer.append`).
    - Receiving OpenAI events (`conversation.item.input_audio_transcription.completed`, `response.audio.delta`, `tool_calls`, etc.).
    *   Passing user transcripts to the `FrontlineAgent`.
    *   Initiating OpenAI TTS for agent responses using the documented `conversation.item.create` + `response.create` flow.
    *   Mediating OpenAI tool calls by executing local agent tools and returning results via `conversation.item.create` (type `function_call_output`) + `response.create`.
- **Multi-Agent System & FSM:** (As described before - Frontline, Menu, Cart, etc. orchestrated via FSM/AgentGraph/SlotStore, logic runs synchronously within the Gevent environment).

*(Keep existing Agent Diagram if desired)*

*(Remove the "Recent Enhancements" section as it described the debugging process, not the final state)*

---

## 🧩 How It Works

*(Keep System Workflow, updating step 2/3 slightly)*

### System Workflow

1.  **Customer Call:** Customer calls the Twilio number.
2.  **TwiML & WS Connect:** Flask endpoint returns TwiML instructing Twilio to `<Connect>` to the app's `/ws/media/<CallSid>` WebSocket endpoint.
3.  **Realtime Session:** The `handle_media_realtime` function (running under Gevent):
    *   Accepts Twilio WebSocket.
    *   Connects to OpenAI Realtime API WebSocket.
    *   Sends `session.update` to configure OpenAI (voice, instructions, tools, audio format `g711_ulaw`).
    *   Starts greenlets to manage bidirectional audio streams.
    *   Sends initial greeting text to OpenAI for TTS.
4.  **Conversation Loop:**
    *   User speaks; audio streamed Twilio -> App WS -> OpenAI WS.
    *   OpenAI VAD detects end of speech.
    *   OpenAI sends `conversation.item.input_audio_transcription.completed` event.
    *   App WS handler receives transcript, passes it to `FrontlineAgent`.
5.  **Agent Orchestration:** Frontline agent (using FSM, AgentGraph, SlotStore) processes input, potentially calls tools (mediated via OpenAI API flow), and generates a text response.
6.  **TTS Response:** App WS handler sends agent's text to OpenAI for TTS (using `conversation.item.create` + `response.create`).
7.  **Audio Output:** OpenAI streams back TTS audio (`response.audio.delta`). App WS handler forwards this to Twilio WS. User hears response.
8.  **(Order Specific)** Cart building, validation (using GuardrailAgent/tools), Deliverect submission (via FulfillmentAgent/tools) occur based on conversation state and tool calls.
9.  **(Optional)** Status updates sent via Celery/Twilio SMS.

*(Keep State Machine Workflow section)*

---

## 📚 Documentation

*(Update links if Readmes were renamed/added)*
- [CLAUDE.md](CLAUDE.md) — Comprehensive project documentation
- [CONVERSATION_STORE.md](CONVERSATION_STORE.md) — Conversation state management
- [ADVANCED_AGENTIC_PATTERNS.md](ADVANCED_AGENTIC_PATTERNS.md) — Agent orchestration patterns
- [GEVENT_README.md](GEVENT_README.md) — Details on the Gevent WebSocket implementation (or similar relevant file)
- [README-WEBSOCKET.md](README-WEBSOCKET.md) — Older WebSocket details (Consider archiving or removing if superseded by GEVENT_README.md)

---

## 🤝 Contributing

*(Keep existing Contributing section)*

---

## 📬 Support

*(Keep existing Support section)*

---

## License

*(Keep existing License section)*

---

## Development Workflow

*(Keep existing Development Workflow section)*

## Deployment

*(Keep existing Deployment section)*

### Render WebSocket Configuration (**Updated**)

The application runs using Gunicorn with the **Gevent worker** for efficient WebSocket handling with Flask-Sock. Your `render.yaml` or Procfile should reflect this:

```yaml
# Example render.yaml service definition
services:
  - type: web
    name: redbarsushi-app
    env: python
    plan: standard # Or your chosen plan
    buildCommand: "SR runs -> sends `conversation.item.input_audio_transcription.completed` event to Backend.
    *   Backend calls `FrontlineAgent.process_voice_input(transcript)`.
    *   Agent logic executes (using FSM,pip install -r requirements.txt"
    startCommand: "gunicorn -k gevent --workers 4 --worker-connections 1000 --bind 0.0.0.0:$PORT --log-level info potentially calling tools via OpenAI mediation).
    *   Agent generates text response.
    *   Backend triggers OpenAI TTS (`conversation.item.create` + `response.create`).
    *   OpenAI sends `response.audio.delta` events wsgi:app"
    # Adjust workers/connections based on plan/needs
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.x # Or your specific version
      - key:.
    *   Backend forwards audio to Twilio. User hears response.
7.  **Order Placement:** FLASK_APP
        value: wsgi:app # Or run:app if wsgi.py imports app from If order confirmed, `FulfillmentAgent` (likely via a tool) sends order to Deliverect API.
8.  ** run.py
      # ... other envVars from your .env file ...
Use code with caution.
Endpoints -->
OR
<!-- UPDATE: Updated workflow description -->
### State Machine Workflow

*(Section looks okay, assuming states match FSM implementation)*

---

## 📚 Documentation

*(bash
# Example Procfile (if used by Render)
web: gunicorn -k gevent --workers 4 --worker-connections 1000Suggest adding GEVENT_README.md and ASGI_README.md if they exist and removing README-WEBSOCKET.md if it's less relevant now)*
- [GEVENT_README.md](GEVENT_README.md) — --bind 0.0.0.0:$PORT --log-level info wsgi:app
Use code with caution.
Call End:** User or system hangs up, WebSockets close.
(Ensure wsgi:app correctly points to your Flask app instance exposed in wsgi.py)
Twilio Media Streams Configuration (Updated)
TwiML configuration must use <Connect><Stream> pointing to the correct WebSocket endpoint including the CallSid:
- [ASGI_README.md](ASGI_README.md) — (If kept) Documents the previous ASGI attempts and why they were replaced.
- [CLAUDE.md](CLAUDE.md) — Comprehensive project documentation
- [CONVERSATION_STORE.md](CONVERSATION_STORE.md) —xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <!-- Brief initial prompt from Twilio (Optional) -->
    <Say>Connecting you to Red Bar Sushi AI Conversation state management
- [ADVANCED_AGENTIC_PATTERNS.md](ADVANCED_AGENTIC_PATTERNS.md) — Agent orchestration patterns
<!-- REMOVE: README-WEBSOCKET.md (Likely superseded) -->

---

## 🤝 Contributing

*(Section looks okay)*

---

## 📬 Support

*(Section looks okay)*

---

## License. Please wait.</Say>
    <Connect>
        <!-- Ensure wss:// for production -->
        <Stream url="wss://your-render-domain.onrender.com/ws/media/{{CallSid}}" />
    </Connect>
    <!-- Fallback message if WebSocket connection fails -->
    <Say>Sorry, we couldn't connect right

*(Section looks okay)*

---

## Development Workflow

*(Section looks okay)*

## Deployment

*(Section looks okay)*

### Render WebSocket Configuration (NEEDS UPDATE)

<!-- REMOVE: Old Gevent-WebSocket Worker now. Please try again later.</Say>
</Response>
Use code with caution.
Details on the Gevent-based WebSocket implementation.
Environment Variables (Updated)
Key environment variables include:
# Database
DATABASE_URL=postgresql://user:password@host:port/redbarsushi

# Redis
REDIS_URL=redis://host:port/0
CELERY_BROKER_ -->
<!-- ```bash -->
<!-- # In Procfile (used by Render) -->
<!-- web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 'run:app' -->
<!-- ``` -->
<!-- ADD: Correct Gevent Worker for Flask-Sock -->
The application is now configured to run with Gunicorn usingURL=redis://host:port/1 # Often same as REDIS_URL or different DB
CELERY_RESULT_BACKEND=redis://host:port/1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL="gpt-4o-realtime-preview-..." # Specify model
OPENAI_REALTIME_VOICE="shimmer" # Or alloy, nova, etc.
OPENAI_REALTIME_SYSTEM_MESSAGE="You are..." the standard `gevent` worker, which is compatible with Flask-Sock. Ensure your `Procfile` (or Render # Your full system prompt (can be multi-line if supported by env loader)
# Add other OpenAI config if needed (language, VAD params?)

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com # Or production URL

# Application Settings
FLASK_APP=wsgi:app # Entry point for Gunicorn
FLASK_ENV=production # Or development
# VOICE_HANDLER=realtime # May not be needed if it's the only mode now
FORCE_HEADLESS=true # Keep for Docker/Render
# CONTAINER_MODE=1 # Keep if used by scripts

# Gunicorn/Server Settings (Often set in start command, but can be env vars)
# PORT=8080
# WORKERS=4
 start command) uses this worker:

```yaml
# Example render.yaml service definition
services:
  - type: web
    name: redbarsushi-app
    env: python
    plan: standard # Adjust as needed
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn -k gevent --workers 4 --worker-connections 1000 --bind 0.0.0.0:$PORT --log-level info wsgi:app"
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
Use code with caution.
Dotenv
(Adjust worker count, connections, port, and app entry point (wsgi:app) as needed)# WORKER_CONNECTIONS=1000
See `.env.example` for a complete list and add any new configuration variables introduced.
Use code with caution.
This updated README should accurately reflect the final architecture and provide
<!-- UPDATE: Corrected Render configuration to use standard gevent worker -->
Twilio Media Streams Configuration (NE correct guidance for setup, deployment, and understanding the system's flow. Remember to replace placeholders like yourusername, your-domain, etc.
````
