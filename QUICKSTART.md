# RedBarSushiAI Quick Start Guide

Get your AI sushi ordering system running in 10 minutes!

## Choose Your Setup Method

### 🐳 Option A: Docker Setup (Recommended - 5 minutes)
Everything runs in containers - no manual installation needed!

**Prerequisites:**
- Docker Desktop
- Twilio account with phone number  
- OpenAI API key
- ngrok account (free)

**[Jump to Docker Setup](#docker-setup)**

### 🖥️ Option B: Local Setup (10 minutes)
Run directly on your machine.

**Prerequisites:**
- Python 3.8+
- PostgreSQL
- Redis
- Twilio account with phone number
- OpenAI API key

**[Continue with Local Setup](#local-setup)**

---

## Docker Setup

### 1. Clone and Configure (2 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd RedBarSushiAI

# Copy environment template
cp .env.docker.example .env

# Edit .env with your API keys
nano .env  # Add your OpenAI key, Twilio credentials, and ngrok token
```

### 2. Start Everything (2 minutes)

```bash
# One command to rule them all
make setup
```

This command will:
- Build Docker images
- Start all services (PostgreSQL, Redis, App, ngrok)
- Initialize the database
- Show you the ngrok URL for Twilio

### 3. Configure Twilio (1 minute)

After setup completes, you'll see:
```
Twilio Webhook URL: https://abc123.ngrok.io/voice/webhook
```

Copy this URL and configure it in Twilio Console as your phone number's webhook.

### 4. Test!

Call your Twilio phone number. You should hear the AI greeting!

**[See Docker Commands](#useful-docker-commands)**

---

## Local Setup

## Step 1: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd RedBarSushiAI

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure Environment (3 minutes)

Create a `.env` file in the project root:

```bash
# Required for AI
OPENAI_API_KEY=sk-proj-xxxxx  # Get from https://platform.openai.com/api-keys

# Required for voice calls
TWILIO_ACCOUNT_SID=ACxxxxx    # Get from Twilio Console
TWILIO_AUTH_TOKEN=xxxxx       # Get from Twilio Console
TWILIO_PHONE_NUMBER=+1xxxxxx  # Your Twilio phone number

# Database (adjust if needed)
DATABASE_URL=postgresql://postgres:postgres@localhost/sushi_restaurant

# Redis (adjust if needed)
REDIS_URL=redis://localhost:6379

# Optional but recommended
CONVERSATION_RELAY_TTS_VOICE=rachel  # Or your preferred voice
CONVERSATION_RELAY_LANGUAGE=en-US
```

## Step 3: Initialize Database (2 minutes)

```bash
# Make sure PostgreSQL is running
# Create database if it doesn't exist
createdb sushi_restaurant  # Or use psql

# Initialize tables
python init_db.py

# Load sample menu data
python seed_menu_db.py

# Verify setup
python test_system.py
```

## Step 4: Start the Server (1 minute)

```bash
# For development
uvicorn app.main:app --reload --port 8000

# Or use Docker Compose
docker-compose up
```

## Step 5: Configure Twilio (2 minutes)

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Click on your phone number
4. In the "Voice Configuration" section:
   - **Configure with**: Webhooks, TwiML Bins, Functions, Studio, or Proxy
   - **A call comes in**: Webhook
   - **URL**: `https://your-domain.ngrok.io/voice/webhook` (or your public URL)
   - **HTTP Method**: POST
5. Click "Save configuration"

### For Local Development with ngrok:

```bash
# Install ngrok if you haven't
# https://ngrok.com/download

# Expose your local server
ngrok http 8000

# Use the HTTPS URL from ngrok in Twilio
# Example: https://abc123.ngrok.io/voice/webhook
```

## Step 6: Test Your System

1. **Check API is running**: http://localhost:8000/docs
2. **Verify voice integration**: 
   ```bash
   python verify_voice_integration.py
   ```
3. **Make a test call**: Call your Twilio phone number!

## What to Expect

When you call:
1. "Welcome to Red Bar Sushi AI!"
2. "How can I help you today?"
3. Say: "I'd like to order some sushi"
4. The AI will guide you through the menu and take your order

## Troubleshooting

### API won't start
- Check PostgreSQL and Redis are running
- Verify DATABASE_URL in .env is correct
- Run `python test_system.py` to diagnose

### Twilio webhook errors
- Make sure your server is publicly accessible (use ngrok for local dev)
- Check the webhook URL ends with `/voice/webhook`
- Look at Twilio Console debugger for errors

### No response from AI
- Verify OPENAI_API_KEY is set correctly
- Check logs: `docker-compose logs -f app` or console output
- Ensure menu data is loaded: `python seed_menu_db.py`

### Voice quality issues
- Try different TTS voices in .env
- Check your internet connection
- Use ConversationRelay for better latency (already configured!)

## Useful Docker Commands

### Basic Operations
```bash
make up          # Start all services
make down        # Stop all services  
make restart     # Restart everything
make logs        # View all logs
make logs-app    # View only app logs
```

### Development
```bash
make shell       # Open shell in app container
make psql        # Connect to PostgreSQL
make redis-cli   # Connect to Redis
make test        # Run system tests
```

### ngrok Management
```bash
make ngrok-url   # Get current ngrok URL
python get_ngrok_url.py  # Detailed ngrok info
```

### Troubleshooting
```bash
docker-compose -f docker-compose.dev.yml ps  # Check service status
make health      # Check system health
make clean       # Remove everything and start fresh
```

## Next Steps

- Customize the menu in `seed_menu_db.py`
- Modify greeting messages in agents
- Add your restaurant's specific business logic
- Deploy to production (Render, AWS, etc.)

## Need Help?

- **Docker Setup**: See `DOCKER_SETUP.md` for detailed guide
- **System Architecture**: Review `CODEBASE_EXPLANATION.md`
- **Check Logs**: `make logs` for debugging
- **Test System**: `make test` to verify setup
- **Enable Debug**: Set `LOG_LEVEL=DEBUG` in `.env`

Happy ordering! 🍱