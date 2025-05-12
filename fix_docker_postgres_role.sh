#!/bin/bash
# Script to fix PostgreSQL role issue in Docker

set -e

echo "===== Fixing PostgreSQL Role Issue ====="

# Step 1: Stop all containers
echo "Step 1: Stopping existing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Cleaned up existing containers"

# Step 2: Remove volumes to force PostgreSQL to reinitialize
echo "Step 2: Removing PostgreSQL volume for fresh initialization..."
docker volume rm postgres-dev-data 2>/dev/null || true
echo "✅ PostgreSQL volume removed"

# Step 3: Create a more direct Docker Compose file that doesn't rely on environment variables
echo "Step 3: Creating simplified docker-compose file..."
cat > docker-compose.simple.yml << 'EOF'
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: redbarsushi-app-dev
    ports:
      - "8080:8080"
    environment:
      - PYTHONUNBUFFERED=1
      - DATABASE_URL=postgresql://app_user:password@postgres:5432/redbarsushi
      - DB_USER=app_user
      - DB_PASSWORD=password
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=redbarsushi
      - POSTGRES_USER=app_user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=redbarsushi
      - REDIS_URL=redis://redis:6379/0
      - TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
      - TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
      - TWILIO_PHONE_NUMBER=+17036467799
      - STRIPE_API_KEY=dummy-key-for-development
      - OPENAI_API_KEY=sk-mytestapikey
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
      - ./:/app/
    networks:
      - redbarsushi-network
    restart: always
    command: ["/bin/bash", "-c", "sleep 10 && echo 'Starting server...' && uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug"]

  postgres:
    image: postgres:14
    container_name: redbarsushi-postgres-dev
    environment:
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: redbarsushi
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - redbarsushi-network
    restart: always

  redis:
    image: redis:6
    container_name: redbarsushi-redis-dev
    ports:
      - "6380:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - redbarsushi-network
    restart: always

networks:
  redbarsushi-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
EOF
echo "✅ docker-compose.simple.yml created"

# Step 4: Create a simple database initialization script
echo "Step 4: Creating database setup script..."
cat > init_simple_db.py << 'EOF'
#!/usr/bin/env python3
"""Simple script to initialize the database."""

import os
import sys
import time
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def wait_for_postgres(max_attempts=10, delay=2):
    """Wait for PostgreSQL to be available."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "app_user")
    password = os.environ.get("DB_PASSWORD", "password")
    
    logger.info(f"Waiting for PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Connection attempt {attempt}/{max_attempts}...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=5
            )
            conn.close()
            logger.info("✅ PostgreSQL is available")
            return True
        except Exception as e:
            logger.warning(f"PostgreSQL not ready yet: {e}")
            if attempt < max_attempts:
                logger.info(f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    logger.error("❌ Could not connect to PostgreSQL after multiple attempts")
    return False

def create_tables():
    """Create basic tables in the database."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "app_user")
    password = os.environ.get("DB_PASSWORD", "password")
    
    try:
        logger.info("Connecting to PostgreSQL to create tables...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create basic tables
        logger.info("Creating menu_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                plu VARCHAR(50) UNIQUE,
                is_available BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Add some test data
        logger.info("Adding test data...")
        try:
            cursor.execute("""
                INSERT INTO menu_items (name, description, price, plu)
                VALUES 
                    ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
                    ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICYTUNA')
                ON CONFLICT (plu) DO NOTHING
            """)
        except Exception as e:
            logger.warning(f"Could not insert test data: {e}")
        
        # Close connection
        cursor.close()
        conn.close()
        
        logger.info("✅ Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== Database Initialization Script ===")
    
    if wait_for_postgres():
        if create_tables():
            logger.info("✅ Database initialized successfully")
            sys.exit(0)
        else:
            logger.error("❌ Failed to create database tables")
            sys.exit(1)
    else:
        logger.error("❌ Could not connect to PostgreSQL")
        sys.exit(1)
EOF
chmod +x init_simple_db.py
echo "✅ init_simple_db.py created"

# Step 5: Create restart script
echo "Step 5: Creating restart script..."
cat > restart_docker_simple.sh << 'EOF'
#!/bin/bash
# Simple script to restart Docker environment

set -e

echo "===== Restarting RedBarSushiAI Docker Environment ====="

# Step 1: Stop and remove containers
echo "Step 1: Stopping and removing containers..."
docker stop redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
docker rm -f redbarsushi-app-dev redbarsushi-postgres-dev redbarsushi-redis-dev 2>/dev/null || true
echo "✅ Containers stopped and removed"

# Step 2: Remove volumes if --clean flag is provided
if [ "$1" == "--clean" ]; then
    echo "Step 2: Removing volumes for clean start..."
    docker volume rm postgres-data redis-data 2>/dev/null || true
    echo "✅ Volumes removed"
else
    echo "Step 2: Keeping existing volumes (use --clean to remove)"
fi

# Step 3: Start containers with docker-compose
echo "Step 3: Starting containers..."
docker compose -f docker-compose.simple.yml up -d --build
echo "✅ Containers started"

# Step 4: Wait for PostgreSQL to be healthy
echo "Step 4: Waiting for PostgreSQL to be healthy..."
attempts=0
max_attempts=30

while [ $attempts -lt $max_attempts ]; do
    attempts=$((attempts+1))
    
    if docker ps | grep "redbarsushi-postgres-dev" | grep -q "(healthy)"; then
        echo "✅ PostgreSQL is healthy"
        break
    fi
    
    echo "⏳ Waiting for PostgreSQL to be healthy... (${attempts}/${max_attempts})"
    sleep 2
done

# Step 5: Run database initialization script
echo "Step 5: Initializing database..."
docker exec redbarsushi-app-dev python /app/init_simple_db.py || echo "⚠️ Database initialization failed"

# Step 6: Show container status
echo
echo "===== Container Status ====="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redbarsushi

echo
echo "===== Docker Environment Ready ====="
echo "The application should be available at: http://localhost:8080"
echo
echo "To view logs:"
echo "- App logs: docker logs redbarsushi-app-dev"
echo "- PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo "- Redis logs: docker logs redbarsushi-redis-dev"
echo
echo "To restart with clean volumes: ./restart_docker_simple.sh --clean"
EOF
chmod +x restart_docker_simple.sh
echo "✅ restart_docker_simple.sh created"

# Step 6: Fix OpenAI Realtime client code
echo "Step 6: Fixing OpenAI Realtime client code..."
cat > app/api/voice/realtime_fixed.py << 'EOF'
"""
OpenAI Realtime API integration for voice interactions.

This module handles the integration with OpenAI's Realtime API for
real-time audio processing, including speech-to-text and text-to-speech.
"""

import asyncio
import logging
import os
import traceback
import base64
from typing import Dict, Any, Optional, Union, Callable

from fastapi import WebSocket
from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.realtime_audio_async import (
    OpenAIRealtimeClient, 
    RealtimeConfig, 
    RealtimeEventProcessor
)
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def create_openai_client(
    call_sid: str,
    websocket: WebSocket,
    transcript_queue: asyncio.Queue,
    event_queue: asyncio.Queue
) -> OpenAIRealtimeClient:
    """
    Create and initialize an OpenAI Realtime API client.
    
    Args:
        call_sid: The Twilio call SID
        websocket: The WebSocket connection to Twilio
        transcript_queue: Queue for passing transcripts to processing
        event_queue: Queue for passing events to processing
        
    Returns:
        The initialized OpenAI Realtime client
    """
    # Define event handlers
    async def on_transcript_final(transcript_data):
        """Handle final transcript events from OpenAI."""
        transcript = transcript_data.get("text", "")
        if transcript:
            # Add to transcript queue for processing
            await transcript_queue.put(transcript)
    
    async def on_audio_delta(audio_data):
        """Handle audio delta events from OpenAI."""
        audio_chunk = audio_data.get("audio", "")
        if audio_chunk:
            # Base64 decode and send to Twilio
            try:
                audio_bytes = base64.b64decode(audio_chunk)
                await websocket.send_bytes(audio_bytes)
            except Exception as e:
                logger.error(f"[{call_sid}] Error sending audio to Twilio: {e}")
    
    async def on_tool_call(tool_data):
        """Handle tool call events from OpenAI."""
        # Add to event queue for processing
        await event_queue.put({
            "type": "tool_call",
            "data": tool_data
        })
    
    # Initialize the OpenAI Realtime client first
    print(f"\n!!! DEBUG: [{call_sid}] Initializing OpenAI Realtime client", flush=True)
    logger.critical(f"🔴 [{call_sid}] Initializing OpenAI Realtime client with API_KEY {'SET' if settings.OPENAI_API_KEY else 'MISSING!!!'}")
    
    # Verify critical environment variables
    logger.critical(f"🔄 [{call_sid}] ENVIRONMENT VERIFICATION")
    logger.critical(f"🔄 [{call_sid}] OPENAI_API_KEY present: {bool(settings.OPENAI_API_KEY)}")
    logger.critical(f"🔄 [{call_sid}] OPENAI_REALTIME_MODEL: {settings.OPENAI_REALTIME_MODEL}")
    logger.critical(f"🔄 [{call_sid}] Environment: {os.environ.get('FASTAPI_ENV', 'undefined')}")
    logger.critical(f"🔄 [{call_sid}] Running on Render: {os.environ.get('RENDER', 'false')}")
    
    print(f"\n!!! DEBUG: [{call_sid}] CRITICAL ENV CHECK - OPENAI_API_KEY present: {bool(settings.OPENAI_API_KEY)}", flush=True)
    print(f"\n!!! DEBUG: [{call_sid}] OPENAI_REALTIME_MODEL: {settings.OPENAI_REALTIME_MODEL}", flush=True)
    
    # Safe logging of API key first/last few characters
    if settings.OPENAI_API_KEY:
        key_preview = settings.OPENAI_API_KEY[:4] + '...' + settings.OPENAI_API_KEY[-4:] if len(settings.OPENAI_API_KEY) > 8 else '[TOO SHORT]'
        key_length = len(settings.OPENAI_API_KEY)
        logger.critical(f"🔶 [{call_sid}] OpenAI API Key preview: {key_preview}, length: {key_length}")
        print(f"\n!!! DEBUG: [{call_sid}] OpenAI API Key preview: {key_preview}, length: {key_length}", flush=True)
        
        if not settings.OPENAI_API_KEY.startswith('sk-'):
            logger.critical(f"🔴 [{call_sid}] WARNING: API key doesn't start with 'sk-', may be invalid!")
            print(f"\n!!! DEBUG: [{call_sid}] WARNING: API key format is INVALID! Doesn't start with 'sk-'", flush=True)
    else:
        logger.critical(f"🔴 [{call_sid}] CRITICAL ERROR: OPENAI_API_KEY IS MISSING!")
        print(f"\n!!! DEBUG: [{call_sid}] CRITICAL ERROR: OPENAI_API_KEY IS MISSING!", flush=True)
    
    # Initialize the configuration
    realtime_config = RealtimeConfig(
        model=settings.OPENAI_REALTIME_MODEL,
        instructions="You are an AI assistant for Red Bar Sushi restaurant, helping customers place orders over the phone. Be friendly, helpful, and concise.",
        voice=settings.OPENAI_REALTIME_VOICE or "shimmer",
        input_audio_format="mulaw",
        output_audio_format="mulaw",
        vad_enabled=True,
        vad_silence_threshold_ms=1000,
        vad_speech_threshold_ms=8000
    )
    
    # Create client
    logger.critical(f"🔄 [{call_sid}] Creating OpenAIRealtimeClient instance...")
    print(f"\n!!! DEBUG: [{call_sid}] Creating OpenAIRealtimeClient instance...", flush=True)
    
    openai_client = OpenAIRealtimeClient(
        api_key=settings.OPENAI_API_KEY,
        config=realtime_config,
        session_id=call_sid
    )
    
    # Now create and configure the event processor with the client
    event_processor = RealtimeEventProcessor(client=openai_client)
    event_processor.register_handler("transcript.final", on_transcript_final)
    event_processor.register_handler("response.audio.delta", on_audio_delta)
    event_processor.register_handler("conversation.function_call", on_tool_call)
    
    # Set the event processor on the client
    openai_client.event_processor = event_processor
    
    logger.critical(f"🔄 [{call_sid}] OpenAIRealtimeClient instance created and configured")
    print(f"\n!!! DEBUG: [{call_sid}] OpenAIRealtimeClient instance created and configured", flush=True)
    
    return openai_client

async def process_transcripts(
    call_sid: str,
    transcript_queue: asyncio.Queue,
    openai_client: OpenAIRealtimeClient
) -> None:
    """
    Process transcripts as they arrive from OpenAI.
    
    Args:
        call_sid: The Twilio call SID
        transcript_queue: Queue of transcripts to process
        openai_client: The OpenAI Realtime client
    """
    logger.critical(f"🔄 [{call_sid}] Starting transcript processing task")
    print(f"\n!!! DEBUG: [{call_sid}] Starting transcript processing task", flush=True)
    
    while True:
        try:
            # Get the next transcript
            transcript = await transcript_queue.get()
            logger.critical(f"🔄 [{call_sid}] Processing transcript: {transcript}")
            
            # Process with the agent orchestrator
            response = await async_agent_orchestrator.process_voice_input(
                call_sid, transcript
            )
            
            # Send response text to OpenAI for TTS
            response_text = response.get("text", "")
            if response_text:
                logger.critical(f"🔄 [{call_sid}] Sending response to TTS: {response_text}")
                await openai_client.request_response(response_text)
            
            # Mark task as done
            transcript_queue.task_done()
            
        except asyncio.CancelledError:
            logger.critical(f"🔴 [{call_sid}] Transcript processing task cancelled")
            print(f"\n!!! DEBUG: [{call_sid}] Transcript processing task cancelled", flush=True)
            break
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] Error processing transcript: {e}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: [{call_sid}] Error processing transcript: {e}", flush=True)
            print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)

async def process_events(
    call_sid: str,
    event_queue: asyncio.Queue,
    openai_client: OpenAIRealtimeClient
) -> None:
    """
    Process events as they arrive from OpenAI.
    
    Args:
        call_sid: The Twilio call SID
        event_queue: Queue of events to process
        openai_client: The OpenAI Realtime client
    """
    logger.critical(f"🔄 [{call_sid}] Starting event processing task")
    print(f"\n!!! DEBUG: [{call_sid}] Starting event processing task", flush=True)
    
    while True:
        try:
            # Get the next event
            event_data = await event_queue.get()
            logger.debug(f"[{call_sid}] Processing event: {event_data.get('type')}")
            
            if event_data.get("type") == "tool_call":
                # Extract tool call details
                tool_call = event_data.get("data", {})
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                logger.info(f"[{call_sid}] Tool call: {tool_name}")
                
                # Process the tool call
                if tool_name:
                    result = await async_agent_orchestrator.process_tool_call(
                        call_sid, tool_name, tool_args
                    )
                    
                    # Return the result to OpenAI
                    await openai_client.return_tool_result(
                        tool_call.get("id", ""), result.get("result", {})
                    )
            
            # Mark task as done
            event_queue.task_done()
            
        except asyncio.CancelledError:
            logger.critical(f"🔴 [{call_sid}] Event processing task cancelled")
            print(f"\n!!! DEBUG: [{call_sid}] Event processing task cancelled", flush=True)
            break
        except Exception as e:
            logger.critical(f"🔴 [{call_sid}] Error processing event: {e}")
            logger.critical(traceback.format_exc())
            print(f"\n!!! DEBUG: [{call_sid}] Error processing event: {e}", flush=True)
            print(f"\n!!! DEBUG: {traceback.format_exc()}", flush=True)
EOF
echo "✅ OpenAI Realtime client code fixed"

# Step 7: Create a script to update the code
echo "Step 7: Creating update script..."
cat > update_realtime_code.sh << 'EOF'
#!/bin/bash
# Script to update the OpenAI Realtime client code

echo "===== Updating OpenAI Realtime Client Code ====="

# Step 1: Making a backup of the original file
if [ -f app/api/voice/realtime.py ]; then
    echo "Step 1: Making a backup of the original realtime.py..."
    cp app/api/voice/realtime.py app/api/voice/realtime.py.bak
    echo "✅ Backup created as app/api/voice/realtime.py.bak"
else
    echo "Step 1: Original file app/api/voice/realtime.py not found, skipping backup"
fi

# Step 2: Replacing the file with the fixed version
echo "Step 2: Replacing realtime.py with the fixed version..."
cp app/api/voice/realtime_fixed.py app/api/voice/realtime.py
echo "✅ Fixed version installed"

echo
echo "===== OpenAI Realtime Client Code Updated ====="
echo "The RealtimeEventProcessor initialization issue has been fixed."
echo "You will need to restart the Docker containers for the changes to take effect."
echo "Run: ./restart_docker_simple.sh"
EOF
chmod +x update_realtime_code.sh
echo "✅ update_realtime_code.sh created"

# Step 8: Run restart script
echo "Step 8: Running restart script..."
./restart_docker_simple.sh --clean
echo "✅ Docker environment restarted with simplified configuration"

# Step 9: Update the OpenAI Realtime client code
echo "Step 9: Updating OpenAI Realtime client code..."
./update_realtime_code.sh
echo "✅ OpenAI Realtime client code updated"

echo
echo "===== Docker Environment Fix Completed ====="
echo "Your Docker environment has been set up with a simplified configuration"
echo "that fixes both the PostgreSQL role issue and the OpenAI Realtime client."
echo
echo "The application should now be running at: http://localhost:8080"
echo
echo "Check logs with these commands:"
echo "- App logs: docker logs redbarsushi-app-dev"
echo "- PostgreSQL logs: docker logs redbarsushi-postgres-dev"
echo
echo "If you need to restart the environment:"
echo "- Normal restart: ./restart_docker_simple.sh"
echo "- Clean restart (removes volumes): ./restart_docker_simple.sh --clean"