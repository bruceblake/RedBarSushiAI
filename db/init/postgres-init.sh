#!/bin/bash
set -e

echo "=== Beginning PostgreSQL initialization ==="

# Create user and database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL
  CREATE USER postgres WITH PASSWORD 'postgres' SUPERUSER;
  CREATE DATABASE redbarsushi;
  GRANT ALL PRIVILEGES ON DATABASE redbarsushi TO postgres;
EOSQL

echo "=== User and database created successfully ==="
echo "=== PostgreSQL initialization complete ==="
