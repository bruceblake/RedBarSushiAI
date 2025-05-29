#!/bin/bash
# Initialize test database

echo "Creating test database..."
docker-compose exec -T postgres psql -U postgres -c "CREATE DATABASE redbarsushi_test;" 2>/dev/null || true

echo "Running schema on test database..."
docker-compose exec -T postgres psql -U postgres -d redbarsushi_test < db/init/01_schema.sql

echo "Test database initialized."