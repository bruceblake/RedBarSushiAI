#!/bin/bash

# Script to apply database fixes for the RedBarSushiAI system

echo "Applying database fixes..."

# Get the database connection string from environment or use a default
# This assumes your DB connection is in an environment variable or use a fallback
DB_URL=${DATABASE_URL:-"postgresql://postgres:postgres@postgres:5432/redbarsushi"}

# Apply the SQL migration to add missing column
echo "Adding 'reference_handler' column to menu_modifiers table if needed..."
docker exec -i postgres psql "$DB_URL" < add_reference_handler_column.sql

echo "Database fixes applied."

# Restart the application to apply changes
echo "Restarting Docker containers to apply changes..."
./restart_docker.sh

echo "Done! Database fixes have been applied and the application restarted."