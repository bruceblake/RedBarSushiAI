#!/bin/bash
set -e

echo "💻 Starting FastAPI application"

# Set default PORT if not provided
if [ -z "$PORT" ]; then
    export PORT=8080
fi

echo "Starting FastAPI on port $PORT"

# Initialize database
echo "Initializing database..."
python -c "
import asyncio
from app.db_async import init_database

async def main():
    await init_database()
    print('Database initialized successfully')

asyncio.run(main())
"

# Start FastAPI with uvicorn
exec uvicorn app.main:app --host="0.0.0.0" --port="$PORT" --reload --log-level=info