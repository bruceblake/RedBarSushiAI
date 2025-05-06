#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=${POSTGRES_PASSWORD:-postgres} psql -h postgres -U postgres -d redbarsushi -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if redis-cli -h redis ping | grep -q PONG; then
    echo "Redis is ready!"
    break
  fi
  attempt=$((attempt+1))
  echo "Redis is unavailable - sleeping (attempt $attempt/$max_attempts)"
  sleep 1
  
  # If we've reached max attempts, continue anyway
  if [ $attempt -eq $max_attempts ]; then
    echo "WARNING: Redis check timed out, but continuing anyway..."
  fi
done

# Run database migrations if not already done
if [ ! -f /data/migrations_applied ]; then
  echo "Running database migrations..."
  python db_init.py
  touch /data/migrations_applied
fi

# Start the MCP server
echo "Starting MCP server..."
python enhanced_mcp_server.py