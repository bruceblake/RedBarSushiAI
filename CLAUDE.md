# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Rules

- FILES MUST NOT BE LONGER THAN 1000 LINES LONG
- NEVER IMPLEMENT FALLBACKS UNLESS SPECIFICALLY ASKED
- WE HAVE 2 ENVIRONMENTS: STAGING AND PRODUCTION. ALL ENVIRONMENTS ARE DEPLOYED USING RENDER WITH THEIR OWN ENVIRONMENT VARIABLES
- NEVER create files unless absolutely necessary - ALWAYS prefer editing existing files
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested

## Common Development Commands

### Running Tests
```bash
# Run all tests in Docker (recommended for consistency)
./run-docker-tests.sh

# Run specific test categories in Docker
./run-docker-tests.sh unit          # Unit tests only
./run-docker-tests.sh integration   # Integration tests only  
./run-docker-tests.sh e2e          # E2E tests only

# Run tests locally (faster for development)
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/e2e/ -v              # E2E tests

# Run a single test file
pytest tests/unit/test_agents.py -v

# Run a specific test function
pytest tests/unit/test_agents.py::test_menu_agent -v

# Run tests with coverage
pytest tests/ --cov=app --cov-report=html
```

### Linting and Type Checking
```bash
# Run linting (if configured)
ruff check app/
ruff format app/

# Type checking (if mypy is configured)
mypy app/
```

### Running the Application
```bash
# Local development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker development (recommended)
docker-compose up -d

# View Docker logs
docker logs -f redbarsushi-app-1

# Access container shell
docker exec -it redbarsushi-app-1 bash
```

### Database Operations
```bash
# Initialize database (Docker)
docker exec -it redbarsushi-app-1 python init_db.py

# Seed menu data
docker exec -it redbarsushi-app-1 python seed_menu_db.py

# Access PostgreSQL
docker exec -it redbarsushi-postgres-1 psql -U redbarsushi -d redbarsushi
```

## High-Level Architecture

RedBarSushiAI is an AI-powered voice ordering system with a sophisticated multi-agent architecture. The system enables natural language phone ordering through real-time audio processing and intelligent conversation orchestration.

### Core Architectural Patterns

1. **Multi-Agent System with Orchestration**
   - The system uses specialized AI agents for different conversation aspects, coordinated by an orchestrator (`app/utils/agent_orchestration_async.py`)
   - Each agent inherits from `BaseAsyncAgent` and implements specific functionality
   - Agents communicate through a standardized interface with tool calling capabilities
   - The orchestrator selects agents based on FSM state and intent detection

2. **Finite State Machine (FSM) for Conversation Flow**
   - FSM implementation in `app/fsm/core.py` defines conversation states and valid transitions
   - State handlers in `app/fsm/handlers/` implement state-specific logic
   - FSM manager (`app/utils/fsm_async.py`) handles persistence in Redis
   - State transitions triggered by events detected through LLM-based intent detection

3. **Voice Processing Architecture (ConversationRelay)**
   - Uses Twilio's ConversationRelay for reliable webhook-based voice handling
   - HTTP POST webhooks handle audio chunks and responses
   - No WebSocket connections or real-time streaming
   - More reliable with built-in retries and error handling

4. **Database Architecture (Async SQLAlchemy 2.0)**
   - Async engine configuration in `app/db_async.py` with connection pooling
   - Models use SQLAlchemy 2.0 declarative style with async support
   - Critical relationships: MenuItem ← PLU → MenuNameVariant for intelligent menu matching
   - JSONB columns for flexible modifier storage and order metadata

### Key Architectural Decisions

1. **Async-First Design**: All I/O operations use async/await for non-blocking execution
2. **Dependency Injection**: FastAPI's dependency system for database sessions, Redis, and services
3. **No Hardcoded Logic**: Uses LLM for intent detection instead of keyword matching
4. **Stateless Request Handling**: All state stored in Redis/PostgreSQL for horizontal scaling
5. **AI-Only Menu Matching**: All menu item identification done through Menu Agent using AI

### Critical Integration Points

1. **OpenAI API**
   - Standard REST API calls for text processing
   - GPT-4 for intent detection and conversation
   - No real-time audio streaming required

2. **Twilio Integration**
   - TwiML generation for call routing
   - ConversationRelay for all voice processing
   - HTTP webhooks for audio handling
   - SMS notifications via Celery background tasks

3. **Deliverect POS Integration**
   - Menu synchronization via webhooks
   - Order submission with PLU mapping
   - Real-time availability updates
   - Status tracking and notifications

### Service Dependencies

- **PostgreSQL**: Primary data store for menus, orders, and configuration
- **Redis** (port 6380): Session state, FSM persistence, and caching
- **Celery**: Background tasks for SMS and order processing
- **OpenAI API**: Realtime API for voice and GPT-4 for intent/matching
- **Twilio**: Phone system integration and SMS
- **Deliverect**: POS system integration

## Development Best Practices

1. **Code Organization**
   - Keep files under 1000 lines (split large files into logical components)
   - Follow existing patterns for new features
   - Place new agents in `app/agents/`, utilities in `app/utils/`
   - Use type hints throughout for better IDE support

2. **Error Handling**
   - Implement proper error boundaries in agents
   - Use specific exception types for different failures
   - Log errors with context (call_sid, order_id, etc.)
   - Graceful degradation for non-critical failures

3. **Testing Strategy**
   - Unit tests: Heavy mocking, test business logic
   - Integration tests: Test component interactions
   - E2E tests: Real service calls (staging only)
   - Always add tests for new features

4. **Performance Considerations**
   - Use connection pooling for database
   - Implement caching for frequently accessed data
   - Stream audio in small chunks (20ms)
   - Batch database operations where possible

## Common Development Scenarios

### Adding a New Agent
1. Create agent class in `app/agents/` inheriting from `BaseAsyncAgent`
2. Implement required methods: `__init__`, `get_tools`, `process`
3. Register in `app/agents/factory_async.py`
4. Update orchestrator logic if needed
5. Add comprehensive unit tests

### Modifying FSM States
1. Update state enum in `app/fsm/core.py`
2. Add transitions in the state machine configuration
3. Create handler in `app/fsm/handlers/`
4. Update intent detector prompts
5. Test state transitions thoroughly

### Working with Menu Data
1. Menu models are in `app/models/menu_async.py`
2. CRUD operations in `app/db/crud_menu_async.py`
3. Menu matching ONLY through Menu Agent's AI (`app/agents/menu_async_enhanced.py`)
4. Always use PLUs for POS integration
5. Cart Agent must delegate ALL menu matching to Menu Agent

### Debugging Voice Issues
1. Check Twilio webhook configuration
2. Verify ConversationRelay service setup
3. Review HTTP webhook logs
4. Check TwiML generation
5. Verify agent response handling