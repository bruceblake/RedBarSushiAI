#!/bin/bash
# Docker health check script for RedBarSushiAI

# Set the path to the docker-compose.yml file
COMPOSE_FILE="./docker/compose/docker-compose.yml"

# Check if the docker-compose.yml file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi

echo "===== Checking Docker Container Health ====="

# Check container status
echo "Container Status:"
docker-compose -f $COMPOSE_FILE ps

# Check if app is running
if ! docker-compose -f $COMPOSE_FILE ps | grep -q "app.*Up"; then
    echo "❌ Error: App container is not running!"
    docker-compose -f $COMPOSE_FILE logs app --tail 50
    exit 1
fi

# Check if postgres is running
if ! docker-compose -f $COMPOSE_FILE ps | grep -q "postgres.*Up"; then
    echo "❌ Error: PostgreSQL container is not running!"
    docker-compose -f $COMPOSE_FILE logs postgres --tail 50
    exit 1
fi

# Check if redis is running
if ! docker-compose -f $COMPOSE_FILE ps | grep -q "redis.*Up"; then
    echo "❌ Error: Redis container is not running!"
    docker-compose -f $COMPOSE_FILE logs redis --tail 50
    exit 1
fi

echo "✅ All required containers are running"

# Check API health
echo "Checking API health..."
if curl -s http://localhost:8080/healthcheck | grep -q '"status": "ok"'; then
    echo "✅ API health check passed"
else
    echo "⚠️ API health check failed"
    echo "API response:"
    curl -s http://localhost:8080/healthcheck | json_pp
fi

# Check database connection
echo "Checking database connection..."
DB_HEALTH=$(docker-compose -f $COMPOSE_FILE exec -T app bash -c 'python -c "from app import create_app; from app.db import db; app = create_app(); with app.app_context(): try: db.session.execute(\"SELECT 1\"); print(\"OK\"); except Exception as e: print(f\"ERROR: {e}\")"')

if echo "$DB_HEALTH" | grep -q "OK"; then
    echo "✅ Database connection working"
else
    echo "❌ Database connection error: $DB_HEALTH"
fi

# Check Redis connection
echo "Checking Redis connection..."
REDIS_HEALTH=$(docker-compose -f $COMPOSE_FILE exec -T app bash -c 'python -c "import os, redis; url = os.environ.get(\"REDIS_URL\"); client = redis.from_url(url); try: response = client.ping(); print(f\"OK: {response}\"); except Exception as e: print(f\"ERROR: {e}\")"')

if echo "$REDIS_HEALTH" | grep -q "OK"; then
    echo "✅ Redis connection working"
else
    echo "❌ Redis connection error: $REDIS_HEALTH"
fi

# Check OpenAI API key
echo "Checking OpenAI API access..."
OPENAI_CHECK=$(docker-compose -f $COMPOSE_FILE exec -T app bash -c 'python -c "import os, openai; key = os.environ.get(\"OPENAI_API_KEY\", \"None\"); print(f\"API Key present: {key != \"None\" and len(key) > 10}\"); if key != \"None\" and len(key) > 10: print(f\"API Key starts with: {key[:5]}...\")"')

if echo "$OPENAI_CHECK" | grep -q "API Key present: True"; then
    echo "✅ OpenAI API key is present"
else
    echo "❌ OpenAI API key is missing"
fi

echo "===== Health Check Completed ====="