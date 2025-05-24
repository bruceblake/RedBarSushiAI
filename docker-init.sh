#!/bin/bash

# docker-init.sh - Initialize RedBarSushiAI with Docker Compose
# This script sets up the complete environment and runs tests

set -e  # Exit on error

echo "======================================"
echo "RedBarSushiAI Docker Initialization"
echo "======================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.example to .env and add your API keys:"
    echo "  cp .env.example .env"
    echo "  Then edit .env and add at least OPENAI_API_KEY"
    exit 1
fi

# Check for required OPENAI_API_KEY
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "ERROR: OPENAI_API_KEY not set in .env file!"
    echo "Please add your OpenAI API key to the .env file"
    exit 1
fi

echo "✓ Environment file found"

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down -v

# Build the containers
echo "Building containers..."
docker-compose build --no-cache

# Start the services
echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 10

# Check if postgres is ready
echo "Checking PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✓ PostgreSQL is ready"

# Check if Redis is ready
echo "Checking Redis..."
until docker-compose exec -T redis redis-cli ping | grep -q PONG; do
    echo "Waiting for Redis..."
    sleep 2
done
echo "✓ Redis is ready"

# Wait for the app to be ready
echo "Checking FastAPI app..."
until curl -f http://localhost:8000/health > /dev/null 2>&1; do
    echo "Waiting for FastAPI app..."
    sleep 2
done
echo "✓ FastAPI app is ready"

# Initialize the database
echo "Initializing database schema..."
docker-compose exec -T app python -c "
import asyncio
from app.db_async import init_database
asyncio.run(init_database())
print('Database initialized')
"

# Seed menu data
echo "Seeding menu data..."
docker-compose exec -T app python seed_menu_db.py

echo ""
echo "======================================"
echo "✓ Docker setup complete!"
echo "======================================"
echo ""
echo "Services running:"
echo "- FastAPI app: http://localhost:8000"
echo "- PostgreSQL: localhost:5432"
echo "- Redis: localhost:6379"
echo ""
echo "Useful commands:"
echo "- View logs: docker-compose logs -f app"
echo "- Stop services: docker-compose down"
echo "- Run tests: ./run-tests.sh"
echo ""