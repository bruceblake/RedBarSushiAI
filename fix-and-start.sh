#!/bin/bash
# One-time fix for Pydantic issue, then start everything

echo "🔧 Fixing Pydantic issue..."

# Stop everything
docker-compose -f docker-compose.dev.yml down

# Fix the config.py file to work with any Pydantic version
cat > app/config_fixed.py << 'EOF'
"""
Configuration for the RedBarSushiAI FastAPI application.
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Simple config class that works without Pydantic BaseSettings
class Settings:
    def __init__(self):
        # Load from environment with defaults
        self.PROJECT_NAME = "RedBarSushiAI"
        self.VERSION = "1.0.0"
        self.API_V1_STR = "/api/v1"
        
        # Required settings
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/sushi_restaurant")
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
        
        # Twilio settings
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
        
        # ConversationRelay settings
        self.CONVERSATION_RELAY_TTS_PROVIDER = os.getenv("CONVERSATION_RELAY_TTS_PROVIDER", "ElevenLabs")
        self.CONVERSATION_RELAY_TTS_VOICE = os.getenv("CONVERSATION_RELAY_TTS_VOICE", "rachel")
        self.CONVERSATION_RELAY_LANGUAGE = os.getenv("CONVERSATION_RELAY_LANGUAGE", "en-US")
        self.CONVERSATION_RELAY_STT_PROVIDER = os.getenv("CONVERSATION_RELAY_STT_PROVIDER", "Google")
        self.CONVERSATION_RELAY_SPEECH_MODEL = os.getenv("CONVERSATION_RELAY_SPEECH_MODEL", "telephony")
        self.CONVERSATION_RELAY_INTERRUPTIBLE = os.getenv("CONVERSATION_RELAY_INTERRUPTIBLE", "any")
        self.CONVERSATION_RELAY_DTMF_DETECTION = os.getenv("CONVERSATION_RELAY_DTMF_DETECTION", "false").lower() == "true"
        
        # Optional Twilio settings
        self.TWILIO_CONVERSATION_SERVICE_SID = os.getenv("TWILIO_CONVERSATION_SERVICE_SID", "")
        self.TWILIO_CONNECTOR_NAME = os.getenv("TWILIO_CONNECTOR_NAME", "")
        
        # Deliverect settings
        self.DELIVERECT_API_KEY = os.getenv("DELIVERECT_API_KEY", "")
        self.DELIVERECT_CHANNEL_NAME = os.getenv("DELIVERECT_CHANNEL_NAME", "redbarsushi")
        
        # App settings
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.INITIALIZE_MENU_DATABASE = os.getenv("INITIALIZE_MENU_DATABASE", "false").lower() == "true"
        
        # Menu cache settings
        self.MENU_CACHE_ENABLED = True
        self.MENU_CACHE_TTL = 3600
        
        # Models
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-0613")
        self.OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

    def dict(self):
        """Return settings as dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

# Create settings instance
settings = Settings()

# Log loaded settings (mask sensitive values)
logger.info("Settings loaded successfully")
for key, value in settings.dict().items():
    if any(sensitive in key.lower() for sensitive in ['key', 'token', 'secret', 'password']):
        logger.debug(f"{key}: {'*' * 8 if value else 'NOT SET'}")
    else:
        logger.debug(f"{key}: {value}")
EOF

# Backup original and use fixed version
mv app/config.py app/config_original.py 2>/dev/null
mv app/config_fixed.py app/config.py

# Also install pydantic-settings in the container as a quick fix
echo "📦 Installing pydantic-settings..."
docker-compose -f docker-compose.dev.yml run --rm app pip install pydantic-settings

# Start everything
echo "🚀 Starting services..."
docker-compose -f docker-compose.dev.yml up -d

# Wait for app
echo "⏳ Waiting for app to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n✅ App is ready!"
        break
    fi
    echo -n "."
    sleep 2
done

# Initialize database if needed
echo "🗄️ Checking database..."
if ! docker-compose -f docker-compose.dev.yml exec postgres psql -U postgres -d sushi_restaurant -c "SELECT 1 FROM locations LIMIT 1;" > /dev/null 2>&1; then
    echo "Initializing database..."
    docker-compose -f docker-compose.dev.yml exec app python init_db.py
    docker-compose -f docker-compose.dev.yml exec app python seed_menu_db.py
fi

# Show status
echo -e "\n✅ Everything is running!"
echo "======================================"
echo "📱 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
echo "======================================"

# Get ngrok URL if available
python get_ngrok_url.py 2>/dev/null || echo "ℹ️  Add NGROK_AUTHTOKEN to .env for public URL"

echo -e "\n📋 Showing app logs (Ctrl+C to exit):"
docker-compose -f docker-compose.dev.yml logs -f app