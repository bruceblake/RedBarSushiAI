#!/bin/bash
# Simple startup script for RedBarSushiAI with Docker

echo "🚀 Starting RedBarSushiAI with Docker..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Creating from template..."
    cp .env.docker.example .env
    echo "⚠️  Please edit .env and add your API keys!"
    exit 1
fi

# Check for required environment variables
source .env
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY not set in .env!"
    echo "Please add your OpenAI API key to .env"
    exit 1
fi

# Clean up any existing containers
echo "🧹 Cleaning up old containers..."
docker-compose -f docker-compose.dev.yml down

# Start PostgreSQL first
echo "🐘 Starting PostgreSQL..."
docker-compose -f docker-compose.dev.yml up -d postgres

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 10

# Check PostgreSQL
if docker-compose -f docker-compose.dev.yml exec postgres pg_isready -U postgres; then
    echo "✅ PostgreSQL is ready!"
else
    echo "❌ PostgreSQL failed to start. Checking logs..."
    docker-compose -f docker-compose.dev.yml logs postgres
    exit 1
fi

# Start Redis
echo "🔴 Starting Redis..."
docker-compose -f docker-compose.dev.yml up -d redis

# Start the app
echo "🍱 Starting the application..."
docker-compose -f docker-compose.dev.yml up -d app

# Wait a bit for app to start
sleep 5

# Initialize database
echo "🗄️  Initializing database..."
docker-compose -f docker-compose.dev.yml exec app python init_db.py
docker-compose -f docker-compose.dev.yml exec app python seed_menu_db.py

# Start ngrok if auth token is set
if [ ! -z "$NGROK_AUTHTOKEN" ]; then
    echo "🌐 Starting ngrok..."
    docker-compose -f docker-compose.dev.yml up -d ngrok
    
    # Wait for ngrok
    sleep 5
    
    # Get ngrok URL
    echo "📡 Getting ngrok URL..."
    python get_ngrok_url.py
else
    echo "⚠️  NGROK_AUTHTOKEN not set - skipping ngrok"
    echo "Add it to .env to enable public URL"
fi

# Show status
echo -e "\n📊 Service Status:"
docker-compose -f docker-compose.dev.yml ps

echo -e "\n✅ Setup complete!"
echo "API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"

# Show logs
echo -e "\nShowing logs (Ctrl+C to exit)..."
docker-compose -f docker-compose.dev.yml logs -f