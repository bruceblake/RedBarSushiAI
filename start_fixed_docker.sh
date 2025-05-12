#!/bin/bash
# Start Docker with optimized configuration

set -e

echo "===== Starting RedBarSushiAI with Fixed Configuration ====="

# Check if .env.development exists
if [ ! -f .env.development ]; then
    echo "Creating .env.development file..."
    cat > .env.development << EOF_ENV
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1
OPENAI_API_KEY=sk-mytestapikey
TWILIO_ACCOUNT_SID=ACb8391ed8d92871d85180ca9adea481b6
TWILIO_AUTH_TOKEN=8bbdc0c60316d163ee36c58af5f35154
TWILIO_PHONE_NUMBER=+17036467799
STRIPE_API_KEY=dummy-key-for-development
SECRET_KEY=supersecretkey123
FASTAPI_ENV=development
FLASK_ENV=development
LOG_LEVEL=DEBUG
VOICE_HANDLER=realtime
EOF_ENV
    echo "✅ .env.development created"
fi

# Start containers
echo "Starting Docker containers..."
docker-compose -f docker-compose.fixed.yml down -v
docker-compose -f docker-compose.fixed.yml up -d

# Wait for containers to initialize
echo "Waiting for containers to initialize..."
sleep 10

# Check container status
echo "Checking container status..."
docker-compose -f docker-compose.fixed.yml ps

# Copy diagnostic scripts to container
echo "Copying diagnostic scripts to app container..."
docker cp check_docker_services.py redbarsushi-app:/app/
docker cp verify_openai_api.py redbarsushi-app:/app/

# Run diagnostics inside container
echo "Running service diagnostics..."
docker exec redbarsushi-app python /app/check_docker_services.py

echo "Running OpenAI API verification..."
docker exec redbarsushi-app python /app/verify_openai_api.py

# View logs
echo "Viewing application logs..."
docker-compose -f docker-compose.fixed.yml logs --tail=100 app

echo "===== Setup Complete ====="
echo "To view logs in real-time: docker-compose -f docker-compose.fixed.yml logs -f app"
echo "To stop the containers: docker-compose -f docker-compose.fixed.yml down"
