# RedBarSushiAI - AI-Powered Voice Ordering System

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License](https://img.shields.io/badge/license-Proprietary-red)
![OpenAI](https://img.shields.io/badge/OpenAI%20Realtime-GPT--4o-brightgreen)

An advanced AI-powered voice ordering system for Red Bar Sushi that enables customers to place orders over the phone using natural language processing, real-time audio streaming, and intelligent multi-agent orchestration.

## 🎯 Overview

RedBarSushiAI combines cutting-edge technologies to create a seamless voice ordering experience:

- **Real-time Voice Processing**: Uses OpenAI's Realtime API for natural conversation
- **Multi-Agent Architecture**: Specialized AI agents handle different aspects of the conversation
- **LLM-Based Intent Detection**: No hardcoded keywords - uses GPT-4 for understanding
- **Finite State Machine (FSM)**: Orchestrates conversation flow with intelligent state transitions
- **ConversationRelay Integration**: Twilio's advanced webhook system for reliable voice handling
- **POS Integration**: Deliverect integration for menu management and order submission
- **Robust Infrastructure**: FastAPI, PostgreSQL, Redis, and async Python throughout

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Customer Phone    │────▶│   Twilio            │────▶│   FastAPI Server    │
│                     │     │   Voice/WebSocket   │     │   (Async)           │
└─────────────────────┘     └─────────────────────┘     └──────────┬──────────┘
                                                                    │
                            ┌───────────────────────────────────────┼───────────────────────────────────────┐
                            │                                       │                                       │
                    ┌───────▼────────┐                     ┌───────▼────────┐                    ┌────────▼────────┐
                    │ ConversationRelay│                   │ WebSocket Handler│                  │ OpenAI Realtime │
                    │ Webhook Handler  │                   │ Media Streams    │                   │      API        │
                    └───────┬────────┘                     └───────┬────────┘                    └────────┬────────┘
                            │                                       │                                       │
                            └───────────────────────┬───────────────────────────────────────────────────────┘
                                                    │
                                            ┌───────▼────────┐
                                            │ FSM + Agent    │
                                            │ Orchestrator   │
                                            └───────┬────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────────────┐
                    │                               │                                       │
            ┌───────▼────────┐            ┌────────▼────────┐                     ┌────────▼────────┐
            │ PostgreSQL     │            │     Redis       │                     │   Deliverect    │
            │ Menu/Orders    │            │   Caching/State │                     │   POS System    │
            └────────────────┘            └─────────────────┘                     └─────────────────┘
```

### Multi-Agent System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Orchestrator                            │
│  (app/utils/agent_orchestration_async.py)                          │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼────────┐ ┌──────▼──────┐ ┌───────▼────────┐
│ Frontline Agent│ │ Menu Agent  │ │  Cart Agent    │
│ (Coordinator)  │ │ (Inquiries) │ │ (Order Build)  │
└────────────────┘ └─────────────┘ └────────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼────────┐ ┌──────▼──────┐ ┌───────▼────────┐
│Guardrail Agent │ │Fulfillment  │ │Escalation Agent│
│ (Validation)   │ │   Agent     │ │ (Human Handoff)│
└────────────────┘ └─────────────┘ └────────────────┘
```

### Conversation Flow State Machine

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  GREETING   │──────────┐
                    └──────┬──────┘          │
                           │              ┌───▼────┐
                    ┌──────▼──────┐       │ ERROR  │
                    │ MAIN_MENU   │◀──────┤RECOVERY│
                    └──────┬──────┘       └────────┘
                           │
               ┌───────────┼───────────┐
               │           │           │
        ┌──────▼──────┐ ┌──▼───┐ ┌────▼─────┐
        │  ORDERING   │ │MENU  │ │ESCALATION│
        └──────┬──────┘ │INQUIRY│ └──────────┘
               │        └──────┘
        ┌──────▼──────┐
        │ VALIDATION  │
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │CONFIRMATION │
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │ FULFILLMENT │
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │ COMPLETION  │
        └─────────────┘
```

## 📁 Project Structure

```
RedBarSushiAI/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── db_async.py               # Async database setup
│   ├── redis_async.py            # Async Redis setup
│   │
│   ├── api/                      # API endpoints
│   │   ├── conversation_relay/   # ConversationRelay webhook handling
│   │   │   ├── handler.py        # Main webhook handler
│   │   │   ├── audio.py          # Audio processing
│   │   │   └── twiml.py          # TwiML generation
│   │   ├── voice/                # Voice endpoints
│   │   │   ├── twiml.py          # TwiML webhooks
│   │   │   └── testing.py        # Voice testing endpoints
│   │   ├── menu/                 # Menu API endpoints
│   │   │   ├── items.py          # Menu item endpoints
│   │   │   ├── categories.py     # Category endpoints
│   │   │   └── search.py         # Menu search
│   │   ├── order/                # Order API endpoints
│   │   │   ├── take_order.py     # Order creation
│   │   │   ├── status.py         # Order status
│   │   │   └── confirmation.py   # Order confirmation
│   │   ├── deliverect.py         # Deliverect integration
│   │   └── deliverect_menu.py    # Menu webhook from Deliverect
│   │
│   ├── agents/                   # AI Agents
│   │   ├── base_async.py         # Base agent class
│   │   ├── factory_async.py      # Agent factory
│   │   ├── frontline_async_ai.py # Main conversation coordinator
│   │   ├── menu_async_enhanced.py # Menu specialist
│   │   ├── cart_async.py         # Cart management
│   │   ├── guardrail_async.py    # Order validation
│   │   ├── fulfillment_async.py  # Order submission
│   │   └── escalation_async.py   # Human handoff
│   │
│   ├── fsm/                      # Finite State Machine
│   │   ├── core.py               # FSM implementation
│   │   └── handlers/             # State-specific handlers
│   │       ├── greeting.py       # Greeting state handler
│   │       ├── main_menu.py      # Main menu handler
│   │       ├── ordering.py       # Ordering handler
│   │       ├── validation.py     # Validation handler
│   │       ├── confirmation.py   # Confirmation handler
│   │       └── fulfillment.py    # Fulfillment handler
│   │
│   ├── models/                   # Database models
│   │   ├── base_async.py         # Base model class
│   │   ├── menu_async.py         # Menu models
│   │   ├── order_async.py        # Order models
│   │   └── location_async.py     # Location model
│   │
│   ├── utils/                    # Utilities
│   │   ├── agent_orchestration_async.py  # Agent coordination
│   │   ├── intent_detector_async.py      # LLM intent detection
│   │   ├── menu_matcher_cache_async.py   # Menu matching with cache
│   │   ├── conversation_store_async.py   # Conversation state storage
│   │   ├── deliverect/                   # Deliverect utilities
│   │   │   ├── menu_async.py             # Menu processing
│   │   │   └── orders_async.py           # Order submission
│   │   └── realtime_audio_async.py       # OpenAI Realtime client
│   │
│   └── schemas/                  # Pydantic schemas
│       └── menu.py               # Menu data schemas
│
├── tests/
│   ├── conftest.py               # Test configuration
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
│
├── docker-compose.yml            # Docker services
├── Dockerfile                    # App container
├── requirements.txt              # Python dependencies
├── CLAUDE.md                     # AI assistant instructions
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (runs on port 6380)
- Twilio account with phone number
- OpenAI API key with Realtime API access
- Deliverect account (sandbox for testing)

### Environment Setup

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/RedBarSushiAI.git
cd RedBarSushiAI
```

2. **Create `.env.development` file**:
```bash
# Database
DATABASE_URL=postgresql://redbarsushi:password@localhost:5432/redbarsushi
REDIS_URL=redis://localhost:6380/0
REDIS_PORT=6380

# OpenAI
OPENAI_API_KEY=sk-...your-key...
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
VOICE_HANDLER=conversation_relay  # or 'realtime' for WebSocket mode
FASTAPI_ENV=development
```

### Docker Development

```bash
# Start all services
./start_docker.sh

# Initialize database
docker exec -it redbarsushi-app-1 python init_db.py

# Seed menu data
docker exec -it redbarsushi-app-1 python seed_menu_db.py

# View logs
docker logs -f redbarsushi-app-1
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start services
uvicorn app.main:app --reload --port 8000

# In another terminal, start Celery
celery -A celery_app_fastapi worker --loglevel=INFO
```

## 📞 Voice System Configuration

### ConversationRelay Mode (Recommended)

ConversationRelay is Twilio's advanced webhook system that provides:
- Reliable message delivery
- Built-in retries
- Proper timeout handling
- Simplified audio processing

**Twilio Configuration**:
1. Set phone number webhook to: `https://your-domain.com/api/conversation-relay`
2. Method: `POST`
3. Enable "Process Speech" in Twilio Console

**Key Implementation Files**:
- `app/api/conversation_relay/handler.py` - Main webhook handler
- `app/api/conversation_relay/audio.py` - Audio processing
- `app/api/conversation_relay/twiml.py` - Response generation

### WebSocket Mode (Alternative)

Uses Twilio Media Streams for real-time bidirectional audio:
- Lower latency
- More complex implementation
- Direct WebSocket to OpenAI Realtime API

**Configuration**:
1. Set `VOICE_HANDLER=realtime` in environment
2. Webhook generates TwiML with `<Stream>` element
3. WebSocket endpoint: `/ws/media/{call_sid}`

## 🤖 AI Agent System

### Agent Roles and Responsibilities

1. **Frontline Agent** (`app/agents/frontline_async_ai.py`)
   - Main conversation coordinator
   - Manages overall flow
   - Delegates to specialist agents
   - Handles greetings and general queries

2. **Menu Agent** (`app/agents/menu_async_enhanced.py`)
   - Answers menu questions
   - Checks item availability
   - Provides recommendations
   - Handles dietary restrictions

3. **Cart Agent** (`app/agents/cart_async.py`)
   - Parses natural language orders
   - Manages cart state
   - Handles quantity and modifications
   - Resolves ambiguities

4. **Guardrail Agent** (`app/agents/guardrail_async.py`)
   - Validates orders against business rules
   - Checks modifier limits
   - Ensures item availability
   - Calculates accurate pricing

5. **Fulfillment Agent** (`app/agents/fulfillment_async.py`)
   - Collects delivery/pickup details
   - Submits orders to Deliverect
   - Records in database
   - Triggers confirmations

6. **Escalation Agent** (`app/agents/escalation_async.py`)
   - Handles complex issues
   - Manages human handoff
   - Preserves context for staff

### Agent Orchestration

The orchestrator (`app/utils/agent_orchestration_async.py`) coordinates agents:

```python
# Example flow
async def process_voice_input(self, call_sid: str, transcript: str, **kwargs):
    # 1. Get current FSM state
    fsm = await self.get_fsm(call_sid)
    
    # 2. Detect intent using LLM
    intent = await self.intent_detector.detect_intent(
        transcript, fsm.current_state, fsm.context
    )
    
    # 3. Process FSM transition
    if intent:
        await fsm.process_event(intent)
    
    # 4. Select appropriate agent
    agent = self._get_agent_for_state(fsm.current_state)
    
    # 5. Process with agent
    response = await agent.process_input(transcript, fsm.context)
    
    # 6. Update context and return
    fsm.context.update(response.get("context_updates", {}))
    return response
```

## 🧠 LLM-Based Intent Detection

No hardcoded keywords! The system uses GPT-4 to understand intent:

```python
# app/utils/intent_detector_async.py
class AsyncIntentDetector:
    async def detect_intent(self, transcript: str, current_state: ConversationState, context: Dict):
        # Build state-specific prompt
        prompt = self._build_prompt(transcript, current_state, context)
        
        # Use GPT-4 to detect intent
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.1
        )
        
        # Map to FSM event
        return self._map_to_event(response.choices[0].message.content)
```

## 🍱 Menu Management

### Database Schema

```sql
-- Categories
CREATE TABLE menu_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    deliverect_category_id VARCHAR(255)
);

-- Items with PLU (Product Lookup Code)
CREATE TABLE menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255),
    plu VARCHAR(50) UNIQUE,  -- Critical for POS
    price INTEGER,           -- In cents
    is_available BOOLEAN DEFAULT true,
    deliverect_item_id VARCHAR(255)
);

-- Modifiers
CREATE TABLE menu_modifiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    plu VARCHAR(50) UNIQUE,
    price_change INTEGER DEFAULT 0
);

-- Natural language variants
CREATE TABLE menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255),  -- "cali roll"
    canonical_name VARCHAR(255),  -- "California Roll"
    target_plu VARCHAR(50)        -- "PLU_CALI_001"
);
```

### Menu Matching System

The menu matcher (`app/utils/menu_matcher_cache_async.py`) uses a three-tier approach:

1. **Exact Match** - Direct PLU or name lookup
2. **Fuzzy Match** - Levenshtein distance for typos
3. **AI Match** - GPT-4 for semantic understanding

## 📦 API Endpoints

### ConversationRelay Webhook
- `POST /api/conversation-relay` - Main voice webhook

### Voice Endpoints
- `POST /voice/webhook` - Twilio webhook (generates TwiML)
- `WS /ws/media/{call_sid}` - WebSocket for media streams
- `GET /voice/test/greeting` - Test greeting response

### Menu Endpoints
- `GET /api/menu/categories` - List all categories
- `GET /api/menu/items` - List all items
- `GET /api/menu/items/{item_id}` - Get specific item
- `GET /api/menu/search?q={query}` - Search menu

### Order Endpoints
- `POST /api/order/take-order` - Create order
- `GET /api/order/{order_id}/status` - Check status
- `POST /api/order/{order_id}/confirm` - Confirm order

### Deliverect Webhooks
- `POST /api/deliverect/menu/update` - Menu updates
- `POST /api/deliverect/order/status` - Order status updates

### Monitoring
- `GET /health` - System health check
- `GET /api/monitoring/agents` - Agent status
- `GET /api/monitoring/fsm/{call_sid}` - FSM state

## 🧪 Testing Strategy

### Test Categories

1. **Unit Tests** (Development)
   - Test individual components in isolation
   - Heavy mocking of external services
   - Fast execution

2. **Integration Tests** (Development/CI)
   - Test component interactions
   - Mock external services or use sandboxes
   - Verify internal contracts

3. **E2E Tests** (Staging Only)
   - Test complete flows with real services
   - Minimal mocking
   - Use Twilio test numbers, OpenAI API, Deliverect sandbox

### Running Tests

```bash
# Unit and integration tests (development)
pytest tests/unit tests/integration -v

# E2E tests (staging only)
export FASTAPI_ENV=staging
pytest tests/e2e -v

# Specific test file
pytest tests/integration/test_fsm_orchestration.py -v
```

## 🚢 Deployment

### Render Deployment

1. **Environment Variables** (Set in Render Dashboard):
   - All variables from `.env.development`
   - Set `FASTAPI_ENV=staging` or `production`

2. **Deployment Process**:
   ```yaml
   # render.yaml
   services:
     - type: web
       name: redbarsushi-api
       env: python
       buildCommand: "./fix_render_deploy.sh"
       startCommand: "./fastapi_render_entrypoint.sh"
   ```

3. **Database Initialization**:
   - Automatic on first deploy
   - Uses `init_db.py` and `seed_menu_db.py`

### Docker Production

```bash
docker-compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

## 🔧 Configuration Details

### Voice Processing Configuration

```python
# OpenAI Realtime Session Config
{
    "model": "gpt-4o-realtime-preview-2024-10-01",
    "voice": "shimmer",
    "instructions": "You are a helpful restaurant assistant...",
    "input_audio_format": "pcm16",      # or "g711_ulaw" for Twilio
    "output_audio_format": "pcm16",
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500
    }
}
```

### FSM Configuration

States and transitions are defined in `app/fsm/core.py`:

```python
class ConversationState(Enum):
    GREETING = "greeting"
    MAIN_MENU = "main_menu"
    ORDERING = "ordering"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    FULFILLMENT = "fulfillment"
    COMPLETION = "completion"
    ESCALATION = "escalation"
```

## 🛠️ Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Check OpenAI API key validity
   - Verify network connectivity
   - Check logs: `docker logs redbarsushi-app-1 | grep WebSocket`

2. **Menu Not Loading**
   - Verify Deliverect webhook is configured
   - Check menu data: `docker exec -it redbarsushi-app-1 python -c "from app.db.crud_menu_async import *; print(await get_all_items())"`
   - Clear cache: `docker exec -it redbarsushi-app-1 python -c "from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher; await clear_cached_menu_matcher()"`

3. **FSM State Issues**
   - Check FSM transitions in logs
   - Verify intent detection is working
   - Debug with: `GET /api/monitoring/fsm/{call_sid}`

4. **Order Submission Failures**
   - Verify Deliverect credentials
   - Check order payload format
   - Review logs for validation errors

## 📚 Important Files for AI Agent Understanding

### Core Application Files

1. **app/main.py** - FastAPI application setup and initialization
2. **app/config.py** - All configuration management
3. **CLAUDE.md** - Comprehensive project documentation

### Agent System Files

4. **app/agents/factory_async.py** - Agent creation and registration
5. **app/agents/frontline_async_ai.py** - Main conversation coordinator
6. **app/utils/agent_orchestration_async.py** - Agent orchestration logic

### FSM and Intent Detection

7. **app/fsm/core.py** - FSM implementation with states and transitions
8. **app/utils/intent_detector_async.py** - LLM-based intent detection

### Voice Handling

9. **app/api/conversation_relay/handler.py** - ConversationRelay webhook
10. **app/api/voice_async.py** - WebSocket voice handling (if exists)

### Database and Models

11. **app/models/menu_async.py** - Menu database models
12. **app/models/order_async.py** - Order database models
13. **app/db_async.py** - Database setup and configuration

### Utilities

14. **app/utils/menu_matcher_cache_async.py** - Menu matching with caching
15. **app/utils/deliverect/orders_async.py** - Order submission to POS

### Testing

16. **tests/conftest.py** - Test configuration
17. **tests/TEST_STRATEGY.md** - Testing approach documentation

## 🤝 Contributing

1. Keep files under 500 lines
2. Use async/await throughout
3. Follow existing patterns
4. Add comprehensive tests
5. Update documentation
6. Never implement fallbacks unless asked
7. Refer to CLAUDE.md for architectural decisions

## 📄 License

Proprietary - All rights reserved.

---

Built with ❤️ using FastAPI, OpenAI Realtime API, and modern async Python