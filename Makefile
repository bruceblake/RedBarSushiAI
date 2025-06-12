# RedBarSushiAI Makefile for Docker Development

.PHONY: help up down restart logs shell clean build init test ngrok-url health

# Default target
help:
	@echo "RedBarSushiAI Docker Development Commands:"
	@echo ""
	@echo "  make up          - Start all services with Docker Compose"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make logs-app    - View only app logs"
	@echo "  make shell       - Open shell in app container"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make build       - Rebuild Docker images"
	@echo "  make init        - Initialize database and seed data"
	@echo "  make test        - Run system tests"
	@echo "  make ngrok-url   - Get ngrok public URL"
	@echo "  make health      - Check system health"
	@echo "  make psql        - Connect to PostgreSQL"
	@echo "  make redis-cli   - Connect to Redis"

# Start all services
up:
	@echo "Starting all services..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@make health
	@echo ""
	@echo "Services are running!"
	@echo "API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo "Ngrok Inspector: http://localhost:4040"
	@echo ""
	@make ngrok-url

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose -f docker-compose.dev.yml down

# Restart all services
restart:
	@make down
	@make up

# View logs
logs:
	docker-compose -f docker-compose.dev.yml logs -f

# View only app logs
logs-app:
	docker-compose -f docker-compose.dev.yml logs -f app

# Open shell in app container
shell:
	docker-compose -f docker-compose.dev.yml exec app /bin/bash

# Clean everything (including volumes)
clean:
	@echo "Stopping and removing all containers and volumes..."
	docker-compose -f docker-compose.dev.yml down -v
	@echo "Clean complete!"

# Build/rebuild images
build:
	@echo "Building Docker images..."
	docker-compose -f docker-compose.dev.yml build

# Initialize database
init:
	@echo "Initializing database..."
	docker-compose -f docker-compose.dev.yml run --rm app python init_db.py
	@echo "Seeding menu data..."
	docker-compose -f docker-compose.dev.yml run --rm app python seed_menu_db.py
	@echo "Database initialization complete!"

# Run system tests
test:
	@echo "Running system tests..."
	docker-compose -f docker-compose.dev.yml run --rm app python test_system.py

# Get ngrok URL
ngrok-url:
	@echo "Getting ngrok public URL..."
	@curl -s http://localhost:4040/api/tunnels | python -c "import sys, json; data = json.load(sys.stdin); tunnels = data.get('tunnels', []); https_tunnel = next((t for t in tunnels if t.get('proto') == 'https'), None); print('\nNgrok Public URL:', https_tunnel['public_url'] if https_tunnel else 'No HTTPS tunnel found'); print('Twilio Webhook URL:', https_tunnel['public_url'] + '/voice/webhook' if https_tunnel else 'Configure ngrok first')" 2>/dev/null || echo "Ngrok not ready yet. Check http://localhost:4040"

# Check system health
health:
	@echo "Checking system health..."
	@curl -s http://localhost:8000/healthcheck | python -m json.tool || echo "API not ready yet"

# Connect to PostgreSQL
psql:
	docker-compose -f docker-compose.dev.yml exec postgres psql -U postgres -d sushi_restaurant

# Connect to Redis CLI
redis-cli:
	docker-compose -f docker-compose.dev.yml exec redis redis-cli

# One-command setup for new developers
setup: build up init
	@echo ""
	@echo "🎉 Setup complete!"
	@echo ""
	@make ngrok-url
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy the Twilio Webhook URL above"
	@echo "2. Configure it in your Twilio phone number settings"
	@echo "3. Make a test call!"

# Watch logs and ngrok URL
watch:
	@make ngrok-url
	@make logs