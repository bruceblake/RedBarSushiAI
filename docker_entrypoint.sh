#!/bin/bash
set -e

# Set environment variable to indicate we're in a Docker container
export DOCKER_CONTAINER=true

# Wait for PostgreSQL (if separate)
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for PostgreSQL to be ready..."
  wait-for-it.sh "$DB_HOST:$DB_PORT" -t 60
  echo "PostgreSQL is ready."
fi

# Check if menu file exists
if [ ! -f /app/menu_data.json ]; then
  echo "No menu file found, creating initial menu file..."
  # Copy from backup if it exists
  if [ -f /app/redbar_menu_data.json ]; then
    echo "Found backup menu file, copying..."
    cp /app/redbar_menu_data.json /app/menu_data.json
  elif [ -f /tmp/menu_data.json ]; then
    echo "Found menu file in /tmp, copying..."
    cp /tmp/menu_data.json /app/menu_data.json
  else
    echo "No backup found, creating default menu..."
    # Create a dummy menu file that will be replaced by the default menu on first run
    echo '{"items":[],"modifiers":[],"modifierGroups":[]}' > /app/menu_data.json
  fi
  chmod 644 /app/menu_data.json
  echo "Menu file ready at /app/menu_data.json"
else
  echo "Menu file already exists at /app/menu_data.json"
fi

# Run database migrations
if [ "$FLASK_ENV" != "development" ]; then
  echo "Running database migrations..."
  flask db upgrade
fi

# Run the application
exec "$@"