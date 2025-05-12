#!/bin/bash
set -e

echo "*** Creating database schema and users ***"

# Create database and roles
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL
  CREATE DATABASE redbarsushi;
  GRANT ALL PRIVILEGES ON DATABASE redbarsushi TO postgres;
EOSQL

# Connect to the redbarsushi database and create tables
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "redbarsushi" << EOSQL
  CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    plu VARCHAR(50) UNIQUE,
    is_available BOOLEAN DEFAULT TRUE
  );
  
  INSERT INTO menu_items (name, description, price, plu)
  VALUES 
    ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
    ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICYTUNA')
  ON CONFLICT (plu) DO NOTHING;
EOSQL

echo "*** Database initialization completed ***"
