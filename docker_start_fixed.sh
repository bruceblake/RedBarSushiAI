#!/bin/bash
# Script to start the application in Docker with proper fixes

set -e  # Exit on any error

echo "===== Starting RedBarSushiAI with Fixes ====="

# Step 1: Fix Pydantic version
echo "Step 1: Fixing Pydantic version..."
python fix_pydantic.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to fix Pydantic version"
    exit 1
fi
echo "✅ Pydantic version fixed"

# Step 2: Verify environment variables
echo "Step 2: Verifying environment variables..."
echo "DATABASE_URL: ${DATABASE_URL:0:20}..."
echo "DB_USER: ${DB_USER}"
echo "DB_PASSWORD: ${DB_PASSWORD:0:2}..."
echo "DB_HOST: ${DB_HOST}"
echo "DB_PORT: ${DB_PORT}"
echo "DB_NAME: ${DB_NAME}"
echo "REDIS_URL: ${REDIS_URL}"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:5}..."

# Step 3: Test database connection
echo "Step 3: Testing database connection..."
python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${DB_HOST}',
        port=${DB_PORT},
        dbname='${DB_NAME}',
        user='${DB_USER}',
        password='${DB_PASSWORD}'
    )
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    # Continue anyway
"

# Step 4: Start with simple diagnostic app first
echo "Step 4: Starting with diagnostic app..."
cd /app

echo "Starting simplified app for testing..."
timeout 10s python docker/main_simplified.py || true
echo "Simplified app test complete (timeout expected)"

# Step 5: Start the main application
echo "Step 5: Starting main application..."
echo "Starting with Uvicorn (1 worker)..."
exec uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 --log-level debug