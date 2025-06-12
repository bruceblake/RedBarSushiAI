# RedBarSushiAI Codebase Explanation & Getting Started Guide

This document explains how the RedBarSushiAI codebase works, what's currently implemented, what needs work, and how to get it running.

## Table of Contents
1. [What This System Does](#what-this-system-does)
2. [Current State of the Codebase](#current-state-of-the-codebase)
3. [How the System Works](#how-the-system-works)
4. [Getting Started](#getting-started)
5. [What Needs to Be Fixed/Implemented](#what-needs-to-be-fixed)
6. [Development Workflow](#development-workflow)

## What This System Does

RedBarSushiAI is an AI-powered phone ordering system for a sushi restaurant. When customers call the restaurant:

1. **Phone Call → AI Assistant**: The call is answered by an AI that can understand natural speech
2. **Conversation**: The AI helps customers browse the menu, answer questions, and take orders
3. **Order Processing**: Orders are sent to the restaurant's POS (Point of Sale) system
4. **Confirmation**: Customers receive SMS confirmations

Think of it as having a virtual employee who never gets tired and can handle multiple calls simultaneously.

## Current State of the Codebase

### ✅ What's Implemented
- **Multi-Agent AI System**: Different specialized AI "agents" handle different parts of the conversation
- **Database Models**: Menu items, orders, and customer data structures are defined
- **API Endpoints**: Routes for handling voice calls, menu data, and orders
- **Test Infrastructure**: Comprehensive test setup (unit, integration, E2E)
- **Docker Configuration**: Complete containerized development environment
- **ConversationRelay Integration**: Voice handling structure using HTTP webhooks

### ⚠️ What's Partially Working
- **ConversationRelay Voice Handling**: HTTP webhook structure exists but needs agent integration
- **Menu Matching**: AI-only matching through Menu Agent (no algorithmic matching)
- **FSM (Finite State Machine)**: Conversation flow logic exists but needs refinement

### ❌ What's Missing/Broken
- **ConversationRelay Agent Integration**: Voice webhooks aren't connected to AI agents
- **Twilio Configuration**: Phone number webhooks and ConversationRelay service need setup
- **Database Initialization**: No menu data loaded by default
- **Environment Variables**: Critical API keys not configured

## How the System Works

### 1. **Phone Call Flow**
```
Customer Calls → Twilio → ConversationRelay → Your Server → AI Agents → Response
```

### 2. **Core Components**

#### **Agents** (`app/agents/`)
Think of agents as specialized employees:
- **Frontline Agent**: The greeter who directs the conversation
- **Menu Agent**: Knows everything about the menu
- **Cart Agent**: Handles adding/removing items from orders
- **Guardrail Agent**: Checks that orders are valid
- **Fulfillment Agent**: Completes the order and gets delivery info
- **Escalation Agent**: Transfers to a human when needed

#### **FSM (Finite State Machine)** (`app/fsm/`)
Controls the conversation flow like a flowchart:
```
GREETING → MAIN_MENU → ORDERING → CONFIRMATION → FULFILLMENT → COMPLETION
```

#### **Voice Processing** (`app/api/voice/` and `app/api/conversation_relay/`)
Uses ConversationRelay exclusively:
- Twilio sends audio chunks via HTTP POST
- Server processes with AI agents
- Responses sent back via HTTP
- More reliable than streaming

#### **Database** (`app/models/`)
Stores:
- Menu items with prices and descriptions
- Customer orders
- Restaurant settings

### 3. **Key Technologies**
- **FastAPI**: The web framework (like Express.js for Python)
- **PostgreSQL**: Database for storing data
- **Redis**: Fast temporary storage for active conversations
- **Docker**: Containers to run everything consistently
- **Twilio**: Phone service provider
- **ConversationRelay**: Twilio's reliable voice processing service
- **OpenAI**: AI for understanding and responding to customers

## Getting Started

### Step 1: Prerequisites
Make sure you have:
- Docker Desktop installed and running
- Git for version control
- A code editor (VS Code recommended)
- Terminal/Command Line access

### Step 2: Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd RedBarSushiAI

# Copy the example environment file
cp .env.example .env
```

### Step 3: Configure Environment Variables
Edit the `.env` file with your actual values:

```bash
# REQUIRED - Get from OpenAI
OPENAI_API_KEY=sk-...your-key-here...

# REQUIRED for phone calls - Get from Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# REQUIRED for ConversationRelay - Get from Twilio Console
TWILIO_CONVERSATION_SERVICE_SID=IS...
TWILIO_CONNECTOR_NAME=your-connector-name

# ConversationRelay Voice Settings
CONVERSATION_RELAY_TTS_PROVIDER=ElevenLabs
CONVERSATION_RELAY_TTS_VOICE=rachel
CONVERSATION_RELAY_LANGUAGE=en-US

# OPTIONAL - For POS integration (can use dummy values for testing)
DELIVERECT_API_KEY=test-key
DELIVERECT_CHANNEL_NAME=redbarsushi
```

### Step 4: Initialize Database
```bash
# Create database tables and default location
python init_db.py

# Load sample menu data (optional, for testing)
python seed_menu_db.py
```

### Step 5: Start Services
```bash
# Option A: Start with Docker Compose (recommended)
docker-compose up -d

# Check if everything is running
docker-compose ps

# View logs
docker-compose logs -f app

# Option B: Run locally (for development)
# Start PostgreSQL and Redis first, then:
uvicorn app.main:app --reload
```

### Step 6: Test the API
```bash
# Check if the server is running
curl http://localhost:8000/health

# View API documentation
# Open browser to: http://localhost:8000/docs
```

### Step 7: Configure Twilio
1. Log into Twilio Console
2. Set up ConversationRelay service
3. Configure your phone number webhook to: `https://your-domain.com/voice/webhook`
4. Set HTTP method to POST

## What Needs to Be Fixed/Implemented

### ✅ UPDATE: Voice Integration is Complete!

The ConversationRelay integration with agents is **FULLY IMPLEMENTED** and ready to use! Here's what's working:

1. **ConversationRelay WebSocket Handler** (`/api/conversation-relay`)
   - ✅ Receives Twilio WebSocket connections
   - ✅ Processes voice through agent orchestration system
   - ✅ Maintains conversation state with FSM
   - ✅ Handles interruptions and DTMF input

2. **Voice Webhook** (`/voice/webhook`)
   - ✅ Generates proper ConversationRelay TwiML
   - ✅ Points to the WebSocket endpoint
   - ✅ Configures STT/TTS providers

3. **Agent System**
   - ✅ All agents properly initialized on startup
   - ✅ AI-only menu matching through Menu Agent
   - ✅ Complete conversation flow from greeting to order completion

### 🚨 Remaining Setup Tasks (External Configuration)

1. **Environment Variables** (Required)
   ```bash
   OPENAI_API_KEY=sk-...        # For AI agents
   TWILIO_ACCOUNT_SID=AC...     # Your Twilio account
   TWILIO_AUTH_TOKEN=...        # Your Twilio auth token
   TWILIO_PHONE_NUMBER=+1...    # Your Twilio phone number
   ```

2. **Twilio Phone Number Configuration**
   - Log into Twilio Console
   - Go to Phone Numbers → Manage → Active Numbers
   - Click on your phone number
   - Set the webhook URL to: `https://your-domain.com/voice/webhook`
   - Set HTTP method to: POST
   - Save the configuration

3. **Database Setup**
   ```bash
   python init_db.py      # Create tables
   python seed_menu_db.py # Add sample menu data
   ```

### 🔧 Important Improvements

4. **Complete ConversationRelay Handler**
   ```python
   # app/api/conversation_relay/handler.py needs:
   - Process incoming audio transcripts
   - Route through agent orchestrator
   - Generate appropriate responses
   - Handle errors gracefully
   ```

5. **Menu Data Management**
   - Create admin endpoints to add/update menu items
   - Import menu from CSV/JSON
   - Sync with Deliverect (if using)

6. **Testing Voice Locally**
   - Create a test endpoint that simulates voice input
   - Add a simple web interface for testing conversations
   - Mock Twilio for local development

### 📝 Nice to Have

7. **Monitoring and Logging**
   - Better error tracking
   - Conversation analytics
   - Performance metrics

8. **Documentation**
   - API endpoint documentation
   - Deployment guide
   - Troubleshooting guide

## Development Workflow

### Making Changes

1. **Always work in a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Test your changes**:
   ```bash
   # Run unit tests
   pytest tests/unit/ -v
   
   # Run specific test
   pytest tests/unit/test_agents.py::test_menu_agent -v
   ```

3. **Check logs while developing**:
   ```bash
   docker-compose logs -f app
   ```

4. **Common Docker commands**:
   ```bash
   # Restart after code changes
   docker-compose restart app
   
   # Rebuild if requirements change
   docker-compose build app
   
   # Access Python shell in container
   docker exec -it redbarsushi-app-1 python
   ```

### Debugging Tips

1. **Can't connect to services?**
   - Check Docker is running: `docker ps`
   - Check logs: `docker-compose logs postgres redis`

2. **Import errors?**
   - Rebuild: `docker-compose build --no-cache app`
   - Check requirements.txt is complete

3. **Database errors?**
   - Reset database: `docker-compose down -v` then `docker-compose up -d`
   - Re-run initialization scripts

4. **Voice not working?**
   - Check Twilio webhook URL configuration
   - Verify ConversationRelay service is set up
   - Check agent orchestrator logs
   - Verify HTTP POST webhooks are received

### How ConversationRelay Works

ConversationRelay is Twilio's production-grade voice processing service that uses HTTP webhooks instead of WebSockets:

1. **Call Initiation**:
   - Customer calls your Twilio number
   - Twilio hits your `/voice/webhook` endpoint
   - Your server returns TwiML with ConversationRelay configuration

2. **Audio Processing**:
   - Twilio processes audio and sends transcripts to `/api/conversation-relay`
   - Your server receives the transcript via HTTP POST
   - Process through agents and FSM
   - Return response text
   - Twilio converts to speech and plays to customer

3. **Why ConversationRelay?**:
   - More reliable than WebSockets
   - Built-in retries and error handling
   - Better for production deployments
   - Easier to debug and monitor

### Next Steps for You

1. **Get the basic system running locally** following the steps above
2. **Create the missing initialization scripts** (init_db.py, seed_menu_db.py)
3. **Connect ConversationRelay to agents** in handler.py
4. **Test with Twilio** using ngrok for local development
5. **Implement a simple test interface** to verify agents work

## Understanding the Code Structure

### Where to Look for What

- **Starting point**: `app/main.py` - FastAPI app setup
- **API routes**: `app/api/` - All HTTP endpoints
- **Business logic**: `app/agents/` - AI agent implementations
- **Data models**: `app/models/` - Database table definitions
- **Utilities**: `app/utils/` - Helper functions
- **Configuration**: `app/config.py` - Settings management

### Key Files to Understand First

1. `app/main.py` - Application entry point
2. `app/agents/frontline_async_ai.py` - Main conversation handler
3. `app/fsm/core.py` - Conversation state management
4. `app/api/conversation_relay/handler.py` - Voice webhook handler (needs work)
5. `app/models/menu_async.py` - Menu database structure

### Making Your First Change

Try this simple modification to understand the flow:

1. Edit `app/api/__init__.py`
2. Add a simple test endpoint:
   ```python
   @router.get("/test")
   async def test_endpoint():
       return {"message": "Hello from RedBarSushiAI!"}
   ```
3. Restart the app: `docker-compose restart app`
4. Test it: `curl http://localhost:8000/test`

This will help you understand how changes flow through the system.

## Questions You Might Have

**Q: Do I need to know AI/ML to work on this?**
A: No! The AI parts are handled by OpenAI's API. You just need to understand how to call their API.

**Q: Can I test without a real phone number?**
A: Yes! You can create test endpoints that simulate voice input, or use Twilio's test credentials.

**Q: How much will this cost to run?**
A: During development, costs are minimal. OpenAI charges based on API usage (about $0.01-0.03 per conversation).

**Q: Why ConversationRelay instead of WebSockets?**
A: ConversationRelay is more reliable, easier to debug, and recommended by Twilio for production voice applications.

**Q: Can I run this without Docker?**
A: Technically yes, but Docker makes it much easier to manage all the services (database, Redis, etc.).

## Getting Help

When you get stuck:

1. **Check the logs first** - they usually tell you what's wrong
2. **Read the error messages carefully** - Python errors are quite descriptive
3. **Test in small pieces** - don't try to fix everything at once
4. **Use the test files** - they show how components should work

Remember: This is a complex system, but each piece is relatively simple. Take it one component at a time!

## Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Customer      │────▶│   Twilio        │────▶│   Your Server   │
│   Phone Call    │     │                 │     │   (FastAPI)     │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                        │
                                 │                        ▼
                                 │              ┌─────────────────┐
                                 │              │ ConversationRelay│
                                 │              │ Webhook Handler │
                                 │              └────────┬────────┘
                                 │                        │
                                 │                        ▼
                                 │              ┌─────────────────┐
                                 │              │ Agent           │
                                 │              │ Orchestrator    │
                                 │              └────────┬────────┘
                                 │                        │
                                 │                        ▼
                                 │              ┌─────────────────┐
                                 │              │ AI Agents       │
                                 │              │ (Process Input) │
                                 │              └────────┬────────┘
                                 │                        │
                                 │                        ▼
                                 │              ┌─────────────────┐
                                 │◀─────────────│ Response        │
                                                │ (TTS)           │
                                                └─────────────────┘
```

This simplified architecture shows how voice calls flow through the system using ConversationRelay's reliable HTTP webhooks.