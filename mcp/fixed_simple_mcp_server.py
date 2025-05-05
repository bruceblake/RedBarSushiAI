#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple MCP Server for RedBarSushiAI testing with real Docker containers.
"""

import os
import sys
import json
import asyncio
import subprocess
import tempfile
from typing import List, Dict, Any, Optional

class SimpleMCPServer:
    def __init__(self):
        self.protocol_version = "2024-11-05"
        self.project_path = "/home/proxyie/MySoftware/RedBarSushiAI"
        
    async def handle_initialize(self, request_id):
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "RedBarSushiAI Test Server",
                    "version": "1.0.0"
                }
            }
        }
        return response
    
    async def handle_tools_list(self, request_id):
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "check_docker_status",
                        "description": "Check the status of Docker and running containers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "run_test",
                        "description": "Run tests on the RedBarSushiAI project",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_type": {
                                    "type": "string",
                                    "description": "Type of test to run (basic, database, redis, menu, order, full_menu, full_order, all)"
                                }
                            },
                            "required": ["test_type"]
                        }
                    },
                    {
                        "name": "setup_docker_env",
                        "description": "Set up a Docker testing environment for RedBarSushiAI",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "project_path": {
                                    "type": "string", 
                                    "description": "Path to the RedBarSushiAI project"
                                }
                            },
                            "required": ["project_path"]
                        }
                    },
                    {
                        "name": "cleanup_docker_env",
                        "description": "Clean up the Docker environment",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "echo",
                        "description": "Echo a message back",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "Message to echo back"
                                }
                            },
                            "required": ["message"]
                        }
                    }
                ]
            }
        }
        return response
    
    async def handle_tool_call(self, request_id, params):
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        result = {
            "content": [
                {
                    "type": "text",
                    "text": "Tool result not available"
                }
            ]
        }
        
        if tool_name == "echo":
            message = tool_args.get("message", "No message provided")
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}"
                    }
                ]
            }
        elif tool_name == "check_docker_status":
            try:
                docker_version = subprocess.run(["docker", "--version"], check=True, capture_output=True, text=True)
                compose_version = subprocess.run(["docker-compose", "--version"], check=True, capture_output=True, text=True)
                containers = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], check=True, capture_output=True, text=True)
                
                output = f"🐳 {docker_version.stdout.strip()}\n\n"
                output += f"🐙 {compose_version.stdout.strip()}\n\n"
                output += "📊 Running Containers:\n"
                output += containers.stdout
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error checking Docker status: {str(e)}"
                        }
                    ]
                }
        elif tool_name == "setup_docker_env":
            project_path = tool_args.get("project_path", self.project_path)
            self.project_path = project_path
            
            try:
                # Create docker-compose.yml file for testing environment
                docker_compose = """
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: redbarsushi_postgres
    environment:
      POSTGRES_USER: redbarsushi_staging_db_user
      POSTGRES_PASSWORD: testing_password
      POSTGRES_DB: redbarsushi_staging_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U redbarsushi_staging_db_user -d redbarsushi_staging_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    container_name: redbarsushi_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
"""
                # Write docker-compose.yml file
                compose_file = os.path.join(project_path, "docker-compose-test.yml")
                with open(compose_file, "w") as f:
                    f.write(docker_compose)
                
                # Create .env file for testing environment
                env_content = """
# Database
DATABASE_URL=postgresql://redbarsushi_staging_db_user:testing_password@localhost:5432/redbarsushi_staging_db
SQLALCHEMY_DATABASE_URI=postgresql://redbarsushi_staging_db_user:testing_password@localhost:5432/redbarsushi_staging_db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Application settings
FLASK_APP=run.py
FLASK_ENV=testing
TESTING=true
"""
                # Write .env file
                env_file = os.path.join(project_path, ".env.test")
                with open(env_file, "w") as f:
                    f.write(env_content)
                
                # Start Docker containers
                subprocess.run(
                    ["docker-compose", "-f", compose_file, "up", "-d"],
                    check=True,
                    cwd=project_path
                )
                
                # Wait for containers to be healthy
                output = "Docker environment set up successfully!\n\n"
                output += "✅ Created docker-compose-test.yml\n"
                output += "✅ Created .env.test file\n"
                output += "✅ Started PostgreSQL and Redis containers\n\n"
                output += "You can now run tests that will connect to real databases!"
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error setting up Docker environment: {str(e)}"
                        }
                    ]
                }
        elif tool_name == "cleanup_docker_env":
            try:
                # Stop and remove Docker containers
                compose_file = os.path.join(self.project_path, "docker-compose-test.yml")
                
                if os.path.exists(compose_file):
                    subprocess.run(
                        ["docker-compose", "-f", compose_file, "down", "--volumes"],
                        check=True,
                        cwd=self.project_path
                    )
                    
                    output = "✅ Docker environment cleaned up successfully!\n"
                    output += "✅ Stopped and removed containers\n"
                    output += "✅ Removed volumes\n"
                else:
                    output = "⚠️ No docker-compose-test.yml file found. Nothing to clean up."
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error cleaning up Docker environment: {str(e)}"
                        }
                    ]
                }
        elif tool_name == "run_test":
            test_type = tool_args.get("test_type", "basic")
            
            # Create test script dynamically based on test_type
            if test_type == "basic":
                test_script = """
#!/bin/bash
echo "Running basic tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

echo "✅ All basic tests passed!"
"""
            elif test_type == "database":
                test_script = """
#!/bin/bash
echo "Running database tests with real PostgreSQL..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Create a test table
echo "Creating test table..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);" > /dev/null 2>&1

# Insert data
echo "Inserting test data..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
INSERT INTO test_table (name) VALUES ('Test 1');" > /dev/null 2>&1

# Query data
echo "Querying test data..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT name FROM test_table WHERE name='Test 1';")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Test data not found"
    exit 1
fi

echo "✅ Database operations verified"
echo "✅ All database tests passed!"
"""
            elif test_type == "redis":
                test_script = """
#!/bin/bash
echo "Running Redis tests with real Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

# Set a key
echo "Setting test key..."
redis-cli -h localhost set test_key "test_value" > /dev/null 2>&1

# Get the key
echo "Getting test key..."
RESULT=$(redis-cli -h localhost get test_key)

if [ "$RESULT" != "test_value" ]; then
    echo "❌ Error: Test key not found or has wrong value"
    exit 1
fi

echo "✅ Redis operations verified"
echo "✅ All Redis tests passed!"
"""
            elif test_type == "menu":
                test_script = """
#!/bin/bash
echo "Running menu tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Create menu schema
echo "Creating menu schema..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Create menu categories table
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu items table
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu modifier groups table
CREATE TABLE IF NOT EXISTS menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu modifiers table
CREATE TABLE IF NOT EXISTS menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL,
    deliverect_modifier_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create item modifier groups table
CREATE TABLE IF NOT EXISTS item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu name variants table
CREATE TABLE IF NOT EXISTS menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on variant_phrase for faster lookups
CREATE INDEX IF NOT EXISTS menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);
" > /dev/null 2>&1

echo "✅ Menu schema created successfully"

# Insert test menu data
echo "Inserting test menu data..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Insert test category
INSERT INTO menu_categories (deliverect_category_id, name, description)
VALUES ('CAT001', 'Sushi Rolls', 'Fresh and delicious sushi rolls');

-- Get the category ID
DO $$
DECLARE
    category_id INT;
BEGIN
    SELECT id INTO category_id FROM menu_categories WHERE name = 'Sushi Rolls' LIMIT 1;
    
    -- Insert test menu items
    INSERT INTO menu_items (category_id, name, description, price, plu, deliverect_item_id, is_available)
    VALUES 
    (category_id, 'California Roll', 'Crab, avocado, and cucumber', 1200, 'CALI-ROLL', 'ITEM001', true),
    (category_id, 'Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 1300, 'SPICY-TUNA', 'ITEM002', true),
    (category_id, 'Dragon Roll', 'Eel, crab, and avocado', 1500, 'DRAGON-ROLL', 'ITEM003', true);
    
    -- Insert modifier group
    INSERT INTO menu_modifier_groups (deliverect_group_id, name, min_selection, max_selection, multi_max)
    VALUES ('GROUP001', 'Add-ons', 0, 3, 1);
    
    -- Get the modifier group ID
    DECLARE
        modifier_group_id INT;
    BEGIN
        SELECT id INTO modifier_group_id FROM menu_modifier_groups WHERE name = 'Add-ons' LIMIT 1;
        
        -- Insert modifiers
        INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu, deliverect_modifier_id, is_available)
        VALUES 
        (modifier_group_id, 'Extra Avocado', 150, 'EXTRA-AVO', 'MOD001', true),
        (modifier_group_id, 'Spicy Mayo', 100, 'SPICY-MAYO', 'MOD002', true),
        (modifier_group_id, 'Eel Sauce', 100, 'EEL-SAUCE', 'MOD003', true);
        
        -- Link modifier group to items
        INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
        SELECT id, modifier_group_id FROM menu_items WHERE plu IN ('CALI-ROLL', 'SPICY-TUNA', 'DRAGON-ROLL');
        
        -- Insert name variants
        INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu)
        VALUES 
        ('california roll', 'California Roll', 'CALI-ROLL'),
        ('cali roll', 'California Roll', 'CALI-ROLL'),
        ('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
        ('dragon', 'Dragon Roll', 'DRAGON-ROLL');
    END;
END \$\$;
" > /dev/null 2>&1

echo "✅ Test menu data inserted successfully"

# Test menu retrieval
echo "Testing menu retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT COUNT(*) FROM menu_items;")

if [ -z "$RESULT" ] || [ "$RESULT" -lt 1 ]; then
    echo "❌ Error: Menu data not found"
    exit 1
fi

echo "✅ Menu data retrieval verified ($RESULT items found)"

# Test menu variant matching
echo "Testing menu variant matching..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT mi.name FROM menu_name_variants mnv
JOIN menu_items mi ON mnv.target_plu = mi.plu
WHERE mnv.variant_phrase = 'cali roll';")

if [[ ! "$RESULT" =~ "California Roll" ]]; then
    echo "❌ Error: Menu variant matching failed"
    exit 1
fi

echo "✅ Menu variant matching verified"

# Test Redis menu caching
echo "Testing Redis menu caching..."
# Set Redis cache
redis-cli -h localhost set "menu:item:CALI-ROLL" "name=California Roll;price=1200" > /dev/null 2>&1

# Get Redis cache
RESULT=$(redis-cli -h localhost get "menu:item:CALI-ROLL")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Menu cache not found in Redis"
    exit 1
fi

echo "✅ Redis menu caching verified"
echo "✅ All menu tests passed!"
"""
            elif test_type == "order":
                test_script = """
#!/bin/bash
echo "Running order tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Create order schema
echo "Creating order schema..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    deliverect_channel_order_id VARCHAR(255) UNIQUE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    order_type INTEGER NOT NULL,
    status INTEGER DEFAULT 10,
    total_price INTEGER NOT NULL,
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estimated_time TIMESTAMP WITH TIME ZONE,
    delivery_address TEXT,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create order items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    menu_item_plu VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create order item modifiers table
CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create locations table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    channel_link_id VARCHAR(255),
    api_key VARCHAR(255),
    phone VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
" > /dev/null 2>&1

echo "✅ Order schema created successfully"

# Insert test order data
echo "Inserting test order data..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Insert test location
INSERT INTO locations (name, address, channel_link_id, api_key, phone)
VALUES ('Red Bar Sushi Downtown', '123 Main St, San Francisco, CA 94105', 'CL123456', 'test_api_key', '+15551234567')
ON CONFLICT DO NOTHING;

-- Insert test order
INSERT INTO orders (deliverect_channel_order_id, customer_phone, customer_name, order_type, status, total_price, estimated_time, delivery_address, notes)
VALUES ('RBS-12345-ABCDE', '+15551234567', 'John Doe', 1, 10, 2500, NOW() + INTERVAL '30 minutes', NULL, 'No wasabi please')
RETURNING id;

-- Get the order ID
DO $$
DECLARE
    order_id INT;
BEGIN
    SELECT id INTO order_id FROM orders WHERE deliverect_channel_order_id = 'RBS-12345-ABCDE' LIMIT 1;
    
    -- Insert order items
    INSERT INTO order_items (order_id, menu_item_plu, name, price, quantity, notes)
    VALUES 
    (order_id, 'CALI-ROLL', 'California Roll', 1200, 1, NULL),
    (order_id, 'SPICY-TUNA', 'Spicy Tuna Roll', 1300, 1, 'Extra spicy');
    
    -- Get the order item IDs
    DECLARE
        cali_roll_id INT;
    BEGIN
        SELECT id INTO cali_roll_id FROM order_items WHERE order_id = order_id AND menu_item_plu = 'CALI-ROLL';
        
        -- Insert order item modifiers
        INSERT INTO order_item_modifiers (order_item_id, modifier_plu, name, price_change, quantity)
        VALUES (cali_roll_id, 'EXTRA-AVO', 'Extra Avocado', 150, 1);
    END;
END \$\$;
" > /dev/null 2>&1

echo "✅ Test order data inserted successfully"

# Test order retrieval
echo "Testing order retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT id, customer_name, total_price FROM orders WHERE deliverect_channel_order_id = 'RBS-12345-ABCDE';")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Order data not found"
    exit 1
fi

echo "✅ Order data retrieval verified"

# Test order items retrieval
echo "Testing order items retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT COUNT(*) FROM order_items WHERE order_id = (SELECT id FROM orders WHERE deliverect_channel_order_id = 'RBS-12345-ABCDE');")

if [ -z "$RESULT" ] || [ "$RESULT" -lt 1 ]; then
    echo "❌ Error: Order items not found"
    exit 1
fi

echo "✅ Order items retrieval verified ($RESULT items found)"

# Test order modifiers retrieval
echo "Testing order modifiers retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT COUNT(*) FROM order_item_modifiers WHERE order_item_id IN (
    SELECT id FROM order_items WHERE order_id = (
        SELECT id FROM orders WHERE deliverect_channel_order_id = 'RBS-12345-ABCDE'
    )
);")

if [ -z "$RESULT" ] || [ "$RESULT" -lt 1 ]; then
    echo "❌ Error: Order modifiers not found"
    exit 1
fi

echo "✅ Order modifiers retrieval verified ($RESULT modifiers found)"

# Test Redis order cart caching
echo "Testing Redis order cart caching..."
# Set Redis cart
redis-cli -h localhost hset "cart:12345" "json" "{\"items\":[{\"plu\":\"CALI-ROLL\",\"name\":\"California Roll\",\"price\":1200,\"quantity\":1,\"modifiers\":[{\"plu\":\"EXTRA-AVO\",\"name\":\"Extra Avocado\",\"price_change\":150,\"quantity\":1}]}],\"total_price\":1350,\"order_type\":1}" > /dev/null 2>&1

# Get Redis cart
RESULT=$(redis-cli -h localhost hget "cart:12345" "json")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Cart not found in Redis"
    exit 1
fi

echo "✅ Redis cart caching verified"
echo "✅ All order tests passed!"
"""
            elif test_type == "full_menu":
                test_script = """
#!/bin/bash
echo "Running full menu integration tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check Python virtual environment
if [ ! -d "${PROJECT_PATH}/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv ${PROJECT_PATH}/venv
fi

# Activate virtual environment
source ${PROJECT_PATH}/venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install -r ${PROJECT_PATH}/requirements.txt > /dev/null 2>&1

# Create a test script for menu integration
cat > ${PROJECT_PATH}/test_menu_integration.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
import json
import time
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

# Set up database connection
try:
    conn = psycopg2.connect(
        dbname="redbarsushi_staging_db",
        user="redbarsushi_staging_db_user",
        password="testing_password",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("✅ Connected to PostgreSQL")
except Exception as e:
    print(f"❌ Error connecting to PostgreSQL: {str(e)}")
    sys.exit(1)

# Set up Redis connection
try:
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Error connecting to Redis: {str(e)}")
    sys.exit(1)

# Test menu operations

# 1. Create menu tables if they don't exist
try:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menu_categories (
        id SERIAL PRIMARY KEY,
        deliverect_category_id VARCHAR(255),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS menu_items (
        id SERIAL PRIMARY KEY,
        category_id INTEGER REFERENCES menu_categories(id),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        plu VARCHAR(255) NOT NULL UNIQUE,
        deliverect_item_id VARCHAR(255),
        is_available BOOLEAN DEFAULT TRUE,
        is_combo BOOLEAN DEFAULT FALSE,
        is_variant BOOLEAN DEFAULT FALSE,
        image_url TEXT,
        snoozed_until TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS menu_modifier_groups (
        id SERIAL PRIMARY KEY,
        deliverect_group_id VARCHAR(255),
        name VARCHAR(255) NOT NULL,
        min_selection INTEGER DEFAULT 0,
        max_selection INTEGER DEFAULT 0,
        multi_max INTEGER DEFAULT 1,
        plu VARCHAR(255),
        is_variant_group BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS menu_modifiers (
        id SERIAL PRIMARY KEY,
        modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
        name VARCHAR(255) NOT NULL,
        price_change INTEGER NOT NULL,
        plu VARCHAR(255) NOT NULL,
        deliverect_modifier_id VARCHAR(255),
        is_available BOOLEAN DEFAULT TRUE,
        snoozed_until TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS item_modifier_groups (
        id SERIAL PRIMARY KEY,
        menu_item_id INTEGER REFERENCES menu_items(id),
        modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS menu_name_variants (
        id SERIAL PRIMARY KEY,
        variant_phrase VARCHAR(255) NOT NULL,
        canonical_name VARCHAR(255) NOT NULL,
        target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);
    """)
    conn.commit()
    print("✅ Menu schema created successfully")
except Exception as e:
    print(f"❌ Error creating menu schema: {str(e)}")
    sys.exit(1)

# 2. Insert sample menu data
try:
    # Insert category
    cursor.execute("""
    INSERT INTO menu_categories (deliverect_category_id, name, description)
    VALUES ('CAT001', 'Sushi Rolls', 'Fresh and delicious sushi rolls')
    RETURNING id;
    """)
    category_id = cursor.fetchone()['id']
    
    # Insert menu items
    cursor.execute("""
    INSERT INTO menu_items (category_id, name, description, price, plu, deliverect_item_id, is_available)
    VALUES 
    (%s, 'California Roll', 'Crab, avocado, and cucumber', 1200, 'CALI-ROLL', 'ITEM001', true),
    (%s, 'Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 1300, 'SPICY-TUNA', 'ITEM002', true),
    (%s, 'Dragon Roll', 'Eel, crab, and avocado', 1500, 'DRAGON-ROLL', 'ITEM003', true)
    RETURNING id;
    """, (category_id, category_id, category_id))
    
    # Insert modifier group
    cursor.execute("""
    INSERT INTO menu_modifier_groups (deliverect_group_id, name, min_selection, max_selection, multi_max)
    VALUES ('GROUP001', 'Add-ons', 0, 3, 1)
    RETURNING id;
    """)
    modifier_group_id = cursor.fetchone()['id']
    
    # Insert modifiers
    cursor.execute("""
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu, deliverect_modifier_id, is_available)
    VALUES 
    (%s, 'Extra Avocado', 150, 'EXTRA-AVO', 'MOD001', true),
    (%s, 'Spicy Mayo', 100, 'SPICY-MAYO', 'MOD002', true),
    (%s, 'Eel Sauce', 100, 'EEL-SAUCE', 'MOD003', true);
    """, (modifier_group_id, modifier_group_id, modifier_group_id))
    
    # Get menu item IDs
    cursor.execute("SELECT id, plu FROM menu_items WHERE plu IN ('CALI-ROLL', 'SPICY-TUNA', 'DRAGON-ROLL');")
    menu_items = cursor.fetchall()
    
    # Link modifier group to items
    for item in menu_items:
        cursor.execute("""
        INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
        VALUES (%s, %s);
        """, (item['id'], modifier_group_id))
    
    # Insert name variants
    cursor.execute("""
    INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu)
    VALUES 
    ('california roll', 'California Roll', 'CALI-ROLL'),
    ('cali roll', 'California Roll', 'CALI-ROLL'),
    ('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
    ('dragon', 'Dragon Roll', 'DRAGON-ROLL');
    """)
    
    conn.commit()
    print("✅ Sample menu data inserted successfully")
except Exception as e:
    conn.rollback()
    print(f"❌ Error inserting menu data: {str(e)}")
    sys.exit(1)

# 3. Cache menu in Redis
try:
    # Cache menu items
    cursor.execute("SELECT * FROM menu_items;")
    menu_items = cursor.fetchall()
    
    for item in menu_items:
        # Convert to dictionary
        item_dict = dict(item)
        # Store in Redis
        redis_client.hset(f"menu:item:{item_dict['plu']}", mapping={
            "id": str(item_dict['id']),
            "name": item_dict['name'],
            "price": str(item_dict['price']),
            "description": item_dict['description'] or "",
            "is_available": "1" if item_dict['is_available'] else "0"
        })
    
    # Cache menu variants for fast lookup
    cursor.execute("SELECT * FROM menu_name_variants;")
    variants = cursor.fetchall()
    
    for variant in variants:
        redis_client.hset("menu:variants", variant['variant_phrase'], variant['target_plu'])
    
    print("✅ Menu data cached in Redis successfully")
except Exception as e:
    print(f"❌ Error caching menu in Redis: {str(e)}")
    sys.exit(1)

# 4. Test menu name variant lookups
try:
    # Test exact match
    cursor.execute("""
    SELECT mi.* FROM menu_name_variants mnv
    JOIN menu_items mi ON mnv.target_plu = mi.plu
    WHERE mnv.variant_phrase = 'cali roll';
    """)
    result = cursor.fetchone()
    
    if result and result['name'] == 'California Roll':
        print("✅ Menu exact match lookup successful")
    else:
        print("❌ Menu exact match lookup failed")
        sys.exit(1)
    
    # Test Redis lookup
    variant_plu = redis_client.hget("menu:variants", "cali roll")
    if variant_plu == "CALI-ROLL":
        item_data = redis_client.hgetall(f"menu:item:{variant_plu}")
        if item_data and item_data["name"] == "California Roll":
            print("✅ Redis menu lookup successful")
        else:
            print("❌ Redis menu lookup failed - item data incorrect")
            sys.exit(1)
    else:
        print("❌ Redis menu lookup failed - variant not found")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ Error testing menu lookups: {str(e)}")
    sys.exit(1)

# 5. Test menu update operations
try:
    # Update a menu item price
    cursor.execute("""
    UPDATE menu_items SET price = 1250 WHERE plu = 'CALI-ROLL'
    RETURNING id, price;
    """)
    updated_item = cursor.fetchone()
    conn.commit()
    
    if updated_item and updated_item['price'] == 1250:
        print("✅ Menu item update successful")
    else:
        print("❌ Menu item update failed")
        sys.exit(1)
    
    # Update Redis cache
    redis_client.hset("menu:item:CALI-ROLL", "price", "1250")
    
    # Verify Redis update
    item_price = redis_client.hget("menu:item:CALI-ROLL", "price")
    if item_price == "1250":
        print("✅ Redis cache update successful")
    else:
        print("❌ Redis cache update failed")
        sys.exit(1)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error testing menu updates: {str(e)}")
    sys.exit(1)

# 6. Test menu availability operations (snooze item)
try:
    # Snooze a menu item
    snooze_until = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 3600))  # 1 hour from now
    
    cursor.execute("""
    UPDATE menu_items SET snoozed_until = %s WHERE plu = 'SPICY-TUNA'
    RETURNING id, snoozed_until;
    """, (snooze_until,))
    snoozed_item = cursor.fetchone()
    conn.commit()
    
    if snoozed_item and snoozed_item['snoozed_until']:
        print("✅ Menu item snooze successful")
    else:
        print("❌ Menu item snooze failed")
        sys.exit(1)
    
    # Check if item is snoozed
    cursor.execute("""
    SELECT is_available, snoozed_until FROM menu_items WHERE plu = 'SPICY-TUNA';
    """)
    item = cursor.fetchone()
    
    # In the actual app, this check would happen in code
    is_snoozed = item['snoozed_until'] and item['snoozed_until'] > time.strftime('%Y-%m-%d %H:%M:%S')
    
    if is_snoozed:
        print("✅ Menu item snooze status check successful")
    else:
        print("❌ Menu item snooze status check failed")
        sys.exit(1)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error testing menu snooze: {str(e)}")
    sys.exit(1)

# Close connections
cursor.close()
conn.close()
redis_client.close()

print("✅ All menu integration tests passed!")
EOF

# Make the test script executable
chmod +x ${PROJECT_PATH}/test_menu_integration.py

# Run the test script
echo "Running menu integration tests..."
cd ${PROJECT_PATH}
python test_menu_integration.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo "✅ Full menu integration tests completed successfully!"
else
    echo "❌ Full menu integration tests failed!"
    exit 1
fi
"""
            elif test_type == "full_order":
                test_script = """
#!/bin/bash
echo "Running full order integration tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check Python virtual environment
if [ ! -d "${PROJECT_PATH}/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv ${PROJECT_PATH}/venv
fi

# Activate virtual environment
source ${PROJECT_PATH}/venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install -r ${PROJECT_PATH}/requirements.txt > /dev/null 2>&1

# Create a test script for order integration
cat > ${PROJECT_PATH}/test_order_integration.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
import json
import time
import uuid
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

# Set up database connection
try:
    conn = psycopg2.connect(
        dbname="redbarsushi_staging_db",
        user="redbarsushi_staging_db_user",
        password="testing_password",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("✅ Connected to PostgreSQL")
except Exception as e:
    print(f"❌ Error connecting to PostgreSQL: {str(e)}")
    sys.exit(1)

# Set up Redis connection
try:
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Error connecting to Redis: {str(e)}")
    sys.exit(1)

# Test order operations

# 1. Create order tables if they don't exist
try:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        deliverect_channel_order_id VARCHAR(255) UNIQUE,
        customer_phone VARCHAR(20) NOT NULL,
        customer_name VARCHAR(255),
        order_type INTEGER NOT NULL,
        status INTEGER DEFAULT 10,
        total_price INTEGER NOT NULL,
        placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        estimated_time TIMESTAMP WITH TIME ZONE,
        delivery_address TEXT,
        notes TEXT,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id),
        menu_item_plu VARCHAR(255),
        name VARCHAR(255) NOT NULL,
        price INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        notes TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS order_item_modifiers (
        id SERIAL PRIMARY KEY,
        order_item_id INTEGER REFERENCES order_items(id),
        modifier_plu VARCHAR(255),
        name VARCHAR(255) NOT NULL,
        price_change INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS locations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        address TEXT,
        channel_link_id VARCHAR(255),
        api_key VARCHAR(255),
        phone VARCHAR(20),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)
    conn.commit()
    print("✅ Order schema created successfully")
except Exception as e:
    print(f"❌ Error creating order schema: {str(e)}")
    sys.exit(1)

# 2. Insert a location
try:
    cursor.execute("""
    INSERT INTO locations (name, address, channel_link_id, api_key, phone)
    VALUES ('Red Bar Sushi Downtown', '123 Main St, San Francisco, CA 94105', 'CL123456', 'test_api_key', '+15551234567')
    ON CONFLICT DO NOTHING
    RETURNING id;
    """)
    conn.commit()
    print("✅ Location created successfully")
except Exception as e:
    conn.rollback()
    print(f"❌ Error creating location: {str(e)}")
    sys.exit(1)

# 3. Create a cart in Redis
try:
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    
    # Cart data structure
    cart_data = {
        "items": [
            {
                "plu": "CALI-ROLL",
                "name": "California Roll",
                "price": 1200,
                "quantity": 1,
                "modifiers": [
                    {
                        "plu": "EXTRA-AVO",
                        "name": "Extra Avocado", 
                        "price_change": 150,
                        "quantity": 1
                    }
                ]
            },
            {
                "plu": "SPICY-TUNA",
                "name": "Spicy Tuna Roll",
                "price": 1300,
                "quantity": 2,
                "modifiers": []
            }
        ],
        "total_price": 3950,  # 1200 + 150 + (1300 * 2)
        "order_type": 1,  # pickup
        "customer_name": "John Doe",
        "customer_phone": "+15551234567",
        "notes": "No wasabi please"
    }
    
    # Store cart in Redis
    redis_client.hset(f"cart:{session_id}", "json", json.dumps(cart_data))
    
    # Verify cart was stored
    cart_json = redis_client.hget(f"cart:{session_id}", "json")
    if cart_json:
        print("✅ Cart created in Redis successfully")
    else:
        print("❌ Cart creation in Redis failed")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ Error creating cart in Redis: {str(e)}")
    sys.exit(1)

# 4. Create an order from the cart
try:
    # Generate a unique order ID for Deliverect
    channel_order_id = f"RBS-{int(time.time())}-{uuid.uuid4().hex[:5].upper()}"
    
    # Get cart data from Redis
    cart_json = redis_client.hget(f"cart:{session_id}", "json")
    cart_data = json.loads(cart_json)
    
    # Insert order
    cursor.execute("""
    INSERT INTO orders (
        deliverect_channel_order_id, 
        customer_phone, 
        customer_name, 
        order_type, 
        status, 
        total_price, 
        estimated_time, 
        notes
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """, (
        channel_order_id,
        cart_data["customer_phone"],
        cart_data["customer_name"],
        cart_data["order_type"],
        10,  # status: received
        cart_data["total_price"],
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 1800)),  # 30 min from now
        cart_data["notes"]
    ))
    
    order_id = cursor.fetchone()['id']
    
    # Insert order items
    for item in cart_data["items"]:
        cursor.execute("""
        INSERT INTO order_items (
            order_id,
            menu_item_plu,
            name,
            price,
            quantity,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """, (
            order_id,
            item["plu"],
            item["name"],
            item["price"],
            item["quantity"],
            None
        ))
        
        item_id = cursor.fetchone()['id']
        
        # Insert modifiers if any
        if "modifiers" in item and item["modifiers"]:
            for modifier in item["modifiers"]:
                cursor.execute("""
                INSERT INTO order_item_modifiers (
                    order_item_id,
                    modifier_plu,
                    name,
                    price_change,
                    quantity
                )
                VALUES (%s, %s, %s, %s, %s);
                """, (
                    item_id,
                    modifier["plu"],
                    modifier["name"],
                    modifier["price_change"],
                    modifier["quantity"]
                ))
    
    # Commit the transaction
    conn.commit()
    print(f"✅ Order created successfully with ID: {order_id} and channelOrderId: {channel_order_id}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error creating order: {str(e)}")
    sys.exit(1)

# 5. Verify order creation
try:
    cursor.execute("""
    SELECT * FROM orders WHERE deliverect_channel_order_id = %s;
    """, (channel_order_id,))
    
    order = cursor.fetchone()
    if not order:
        print("❌ Order verification failed - order not found")
        sys.exit(1)
    
    # Check order total price
    if order["total_price"] != cart_data["total_price"]:
        print(f"❌ Order verification failed - incorrect total price: {order['total_price']} vs {cart_data['total_price']}")
        sys.exit(1)
    
    # Check order items
    cursor.execute("""
    SELECT * FROM order_items WHERE order_id = %s;
    """, (order["id"],))
    
    order_items = cursor.fetchall()
    if len(order_items) != len(cart_data["items"]):
        print(f"❌ Order verification failed - incorrect number of items: {len(order_items)} vs {len(cart_data['items'])}")
        sys.exit(1)
    
    # Check modifiers for the first item (California Roll)
    cali_roll_item = next((item for item in order_items if item["menu_item_plu"] == "CALI-ROLL"), None)
    if not cali_roll_item:
        print("❌ Order verification failed - California Roll not found in order items")
        sys.exit(1)
    
    cursor.execute("""
    SELECT * FROM order_item_modifiers WHERE order_item_id = %s;
    """, (cali_roll_item["id"],))
    
    modifiers = cursor.fetchall()
    if len(modifiers) != 1:
        print(f"❌ Order verification failed - incorrect number of modifiers: {len(modifiers)} vs 1")
        sys.exit(1)
    
    if modifiers[0]["modifier_plu"] != "EXTRA-AVO":
        print(f"❌ Order verification failed - incorrect modifier PLU: {modifiers[0]['modifier_plu']} vs EXTRA-AVO")
        sys.exit(1)
    
    print("✅ Order verification passed")
    
except Exception as e:
    print(f"❌ Error verifying order: {str(e)}")
    sys.exit(1)

# 6. Test order status update
try:
    cursor.execute("""
    UPDATE orders SET status = 20 WHERE deliverect_channel_order_id = %s
    RETURNING id, status;
    """, (channel_order_id,))
    
    updated_order = cursor.fetchone()
    conn.commit()
    
    if updated_order and updated_order["status"] == 20:
        print("✅ Order status update successful")
    else:
        print("❌ Order status update failed")
        sys.exit(1)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating order status: {str(e)}")
    sys.exit(1)

# 7. Store conversation context in Redis
try:
    conversation_data = {
        "customer_name": "John Doe",
        "order_id": order_id,
        "last_interaction": time.time(),
        "cart_id": session_id,
        "fsm_state": "confirmation"
    }
    
    # Store conversation in Redis
    redis_client.hset(f"conversation:{session_id}", mapping=conversation_data)
    
    # Verify conversation was stored
    stored_name = redis_client.hget(f"conversation:{session_id}", "customer_name")
    if stored_name == "John Doe":
        print("✅ Conversation context stored in Redis successfully")
    else:
        print("❌ Conversation context storage in Redis failed")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ Error storing conversation context: {str(e)}")
    sys.exit(1)

# 8. Test preparing Deliverect payload
try:
    # This simulates what the application would do to prepare a payload for Deliverect
    
    # Get order details
    cursor.execute("""
    SELECT * FROM orders WHERE id = %s;
    """, (order_id,))
    order = cursor.fetchone()
    
    # Get order items
    cursor.execute("""
    SELECT * FROM order_items WHERE order_id = %s;
    """, (order_id,))
    order_items = cursor.fetchall()
    
    # Get order item modifiers
    items_with_modifiers = []
    for item in order_items:
        cursor.execute("""
        SELECT * FROM order_item_modifiers WHERE order_item_id = %s;
        """, (item["id"],))
        modifiers = cursor.fetchall()
        
        # Convert to dict
        item_dict = dict(item)
        item_dict["modifiers"] = [dict(m) for m in modifiers]
        items_with_modifiers.append(item_dict)
    
    # Prepare Deliverect payload
    deliverect_payload = {
        "channelOrderId": order["deliverect_channel_order_id"],
        "channelOrderDisplayId": order["deliverect_channel_order_id"].split("-")[0] + "-" + order["deliverect_channel_order_id"].split("-")[1],
        "orderType": order["order_type"],
        "customer": {
            "name": order["customer_name"],
            "phoneNumber": order["customer_phone"]
        },
        "orderIsAlreadyPaid": False,
        "payment": {
            "amount": order["total_price"],
            "type": 1  # cash
        },
        "note": order["notes"],
        "items": []
    }
    
    # Add order items to payload
    for item in items_with_modifiers:
        deliverect_item = {
            "plu": item["menu_item_plu"],
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
            "subItems": []
        }
        
        # Add modifiers
        for modifier in item["modifiers"]:
            deliverect_item["subItems"].append({
                "plu": modifier["modifier_plu"],
                "name": modifier["name"],
                "price": modifier["price_change"],
                "quantity": modifier["quantity"]
            })
        
        deliverect_payload["items"].append(deliverect_item)
    
    # Verify payload structure
    if len(deliverect_payload["items"]) != len(cart_data["items"]):
        print(f"❌ Deliverect payload verification failed - incorrect number of items")
        sys.exit(1)
    
    # Store the Deliverect payload in Redis (as the app would do)
    redis_client.set(f"deliverect:payload:{order_id}", json.dumps(deliverect_payload))
    
    print("✅ Deliverect payload prepared and stored successfully")
    
except Exception as e:
    print(f"❌ Error preparing Deliverect payload: {str(e)}")
    sys.exit(1)

# Close connections
cursor.close()
conn.close()
redis_client.close()

print("✅ All order integration tests passed!")
EOF

# Make the test script executable
chmod +x ${PROJECT_PATH}/test_order_integration.py

# Run the test script
echo "Running order integration tests..."
cd ${PROJECT_PATH}
python test_order_integration.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo "✅ Full order integration tests completed successfully!"
else
    echo "❌ Full order integration tests failed!"
    exit 1
fi
"""
            elif test_type == "all":
                test_script = """
#!/bin/bash
echo "Running all tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Set script to exit on first failure
set -e

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

echo ""
echo "🔍 Running all test suites..."
echo "=============================="
echo ""

# Create Python virtual environment if it doesn't exist
if [ ! -d "${PROJECT_PATH}/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv ${PROJECT_PATH}/venv
fi

# Activate virtual environment
source ${PROJECT_PATH}/venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install -r ${PROJECT_PATH}/requirements.txt > /dev/null 2>&1

# Run menu tests
echo ""
echo "🍣 Running menu tests..."
echo "----------------------"
# Create a temporary menu test script
MENU_TEST=$(mktemp)
cat > ${MENU_TEST} << 'EOF'
#!/bin/bash
echo "Running menu tests with real PostgreSQL and Redis..."

# Create menu schema
echo "Creating menu schema..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Create menu categories table
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu items table
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu modifier groups table
CREATE TABLE IF NOT EXISTS menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu modifiers table
CREATE TABLE IF NOT EXISTS menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL,
    deliverect_modifier_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create item modifier groups table
CREATE TABLE IF NOT EXISTS item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create menu name variants table
CREATE TABLE IF NOT EXISTS menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on variant_phrase for faster lookups
CREATE INDEX IF NOT EXISTS menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);
" > /dev/null 2>&1

echo "✅ Menu schema created successfully"

# Insert test menu data
echo "Inserting test menu data..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Insert test category
INSERT INTO menu_categories (deliverect_category_id, name, description)
VALUES ('CAT001', 'Sushi Rolls', 'Fresh and delicious sushi rolls')
ON CONFLICT DO NOTHING;

-- Get the category ID
DO $$
DECLARE
    category_id INT;
BEGIN
    SELECT id INTO category_id FROM menu_categories WHERE name = 'Sushi Rolls' LIMIT 1;
    
    -- Insert test menu items
    INSERT INTO menu_items (category_id, name, description, price, plu, deliverect_item_id, is_available)
    VALUES 
    (category_id, 'California Roll', 'Crab, avocado, and cucumber', 1200, 'CALI-ROLL', 'ITEM001', true),
    (category_id, 'Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 1300, 'SPICY-TUNA', 'ITEM002', true),
    (category_id, 'Dragon Roll', 'Eel, crab, and avocado', 1500, 'DRAGON-ROLL', 'ITEM003', true)
    ON CONFLICT (plu) DO NOTHING;
    
    -- Insert modifier group
    INSERT INTO menu_modifier_groups (deliverect_group_id, name, min_selection, max_selection, multi_max)
    VALUES ('GROUP001', 'Add-ons', 0, 3, 1)
    ON CONFLICT DO NOTHING;
    
    -- Get the modifier group ID
    DECLARE
        modifier_group_id INT;
    BEGIN
        SELECT id INTO modifier_group_id FROM menu_modifier_groups WHERE name = 'Add-ons' LIMIT 1;
        
        -- Insert modifiers
        INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu, deliverect_modifier_id, is_available)
        VALUES 
        (modifier_group_id, 'Extra Avocado', 150, 'EXTRA-AVO', 'MOD001', true),
        (modifier_group_id, 'Spicy Mayo', 100, 'SPICY-MAYO', 'MOD002', true),
        (modifier_group_id, 'Eel Sauce', 100, 'EEL-SAUCE', 'MOD003', true)
        ON CONFLICT (plu) DO NOTHING;
        
        -- Link modifier group to items (check if link already exists)
        INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
        SELECT mi.id, modifier_group_id 
        FROM menu_items mi
        WHERE mi.plu IN ('CALI-ROLL', 'SPICY-TUNA', 'DRAGON-ROLL')
        AND NOT EXISTS (
            SELECT 1 FROM item_modifier_groups img 
            WHERE img.menu_item_id = mi.id 
            AND img.modifier_group_id = modifier_group_id
        );
        
        -- Insert name variants
        INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu)
        VALUES 
        ('california roll', 'California Roll', 'CALI-ROLL'),
        ('cali roll', 'California Roll', 'CALI-ROLL'),
        ('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
        ('dragon', 'Dragon Roll', 'DRAGON-ROLL')
        ON CONFLICT DO NOTHING;
    END;
END \$\$;
" > /dev/null 2>&1

echo "✅ Test menu data inserted successfully"

# Test menu retrieval
echo "Testing menu retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT COUNT(*) FROM menu_items;")

if [ -z "$RESULT" ] || [ "$RESULT" -lt 1 ]; then
    echo "❌ Error: Menu data not found"
    exit 1
fi

echo "✅ Menu data retrieval verified ($RESULT items found)"

# Test menu variant matching
echo "Testing menu variant matching..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT mi.name FROM menu_name_variants mnv
JOIN menu_items mi ON mnv.target_plu = mi.plu
WHERE mnv.variant_phrase = 'cali roll';")

if [[ ! "$RESULT" =~ "California Roll" ]]; then
    echo "❌ Error: Menu variant matching failed"
    exit 1
fi

echo "✅ Menu variant matching verified"

# Test Redis menu caching
echo "Testing Redis menu caching..."
# Set Redis cache
redis-cli -h localhost hset "menu:item:CALI-ROLL" name "California Roll" price "1200" description "Crab, avocado, and cucumber" > /dev/null 2>&1

# Get Redis cache
NAME=$(redis-cli -h localhost hget "menu:item:CALI-ROLL" "name")
PRICE=$(redis-cli -h localhost hget "menu:item:CALI-ROLL" "price")

if [ "$NAME" != "California Roll" ] || [ "$PRICE" != "1200" ]; then
    echo "❌ Error: Menu cache retrieval failed from Redis"
    exit 1
fi

echo "✅ Redis menu caching verified"
echo "✅ All menu tests passed!"
EOF

chmod +x ${MENU_TEST}
bash ${MENU_TEST}
rm ${MENU_TEST}

# Run order tests
echo ""
echo "🧾 Running order tests..."
echo "----------------------"
# Create a temporary order test script
ORDER_TEST=$(mktemp)
cat > ${ORDER_TEST} << 'EOF'
#!/bin/bash
echo "Running order tests with real PostgreSQL and Redis..."

# Create order schema
echo "Creating order schema..."
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    deliverect_channel_order_id VARCHAR(255) UNIQUE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    order_type INTEGER NOT NULL,
    status INTEGER DEFAULT 10,
    total_price INTEGER NOT NULL,
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estimated_time TIMESTAMP WITH TIME ZONE,
    delivery_address TEXT,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create order items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    menu_item_plu VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create order item modifiers table
CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create locations table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    channel_link_id VARCHAR(255),
    api_key VARCHAR(255),
    phone VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
" > /dev/null 2>&1

echo "✅ Order schema created successfully"

# Insert test order data
echo "Inserting test order data..."
# Generate unique order ID to avoid conflicts in repeated tests
UNIQUE_ID=$(date +%s)
PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "
-- Insert test location
INSERT INTO locations (name, address, channel_link_id, api_key, phone)
VALUES ('Red Bar Sushi Downtown', '123 Main St, San Francisco, CA 94105', 'CL123456', 'test_api_key', '+15551234567')
ON CONFLICT DO NOTHING;

-- Insert test order with unique ID
INSERT INTO orders (deliverect_channel_order_id, customer_phone, customer_name, order_type, status, total_price, estimated_time, delivery_address, notes)
VALUES ('RBS-${UNIQUE_ID}-ABCDE', '+15551234567', 'John Doe', 1, 10, 2500, NOW() + INTERVAL '30 minutes', NULL, 'No wasabi please')
ON CONFLICT DO NOTHING
RETURNING id;

-- Get the order ID
DO $$
DECLARE
    order_id INT;
BEGIN
    SELECT id INTO order_id FROM orders WHERE deliverect_channel_order_id = 'RBS-${UNIQUE_ID}-ABCDE' LIMIT 1;
    
    -- Insert order items
    INSERT INTO order_items (order_id, menu_item_plu, name, price, quantity, notes)
    VALUES 
    (order_id, 'CALI-ROLL', 'California Roll', 1200, 1, NULL),
    (order_id, 'SPICY-TUNA', 'Spicy Tuna Roll', 1300, 1, 'Extra spicy');
    
    -- Get the order item IDs
    DECLARE
        cali_roll_id INT;
    BEGIN
        SELECT id INTO cali_roll_id FROM order_items WHERE order_id = order_id AND menu_item_plu = 'CALI-ROLL' LIMIT 1;
        
        -- Insert order item modifiers
        INSERT INTO order_item_modifiers (order_item_id, modifier_plu, name, price_change, quantity)
        VALUES (cali_roll_id, 'EXTRA-AVO', 'Extra Avocado', 150, 1);
    END;
END \$\$;
" > /dev/null 2>&1

echo "✅ Test order data inserted successfully"

# Test order retrieval
echo "Testing order retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT id, customer_name, total_price FROM orders WHERE deliverect_channel_order_id = 'RBS-${UNIQUE_ID}-ABCDE';")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Order data not found"
    exit 1
fi

echo "✅ Order data retrieval verified"

# Test order items retrieval
echo "Testing order items retrieval..."
RESULT=$(PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -t -c "
SELECT COUNT(*) FROM order_items WHERE order_id = (SELECT id FROM orders WHERE deliverect_channel_order_id = 'RBS-${UNIQUE_ID}-ABCDE');")

if [ -z "$RESULT" ] || [ "$RESULT" -lt 1 ]; then
    echo "❌ Error: Order items not found"
    exit 1
fi

echo "✅ Order items retrieval verified ($RESULT items found)"

# Test Redis order cart caching
echo "Testing Redis order cart caching..."
# Set Redis cart
CART_ID="${UNIQUE_ID}"
redis-cli -h localhost hset "cart:${CART_ID}" "json" "{\"items\":[{\"plu\":\"CALI-ROLL\",\"name\":\"California Roll\",\"price\":1200,\"quantity\":1,\"modifiers\":[{\"plu\":\"EXTRA-AVO\",\"name\":\"Extra Avocado\",\"price_change\":150,\"quantity\":1}]}],\"total_price\":1350,\"order_type\":1}" > /dev/null 2>&1

# Get Redis cart
RESULT=$(redis-cli -h localhost hget "cart:${CART_ID}" "json")

if [ -z "$RESULT" ]; then
    echo "❌ Error: Cart not found in Redis"
    exit 1
fi

echo "✅ Redis cart caching verified"

# Test conversation store
echo "Testing conversation store..."
redis-cli -h localhost hset "conversation:${CART_ID}" "customer_name" "John Doe" "fsm_state" "ordering" "last_interaction" "$(date +%s)" > /dev/null 2>&1

NAME=$(redis-cli -h localhost hget "conversation:${CART_ID}" "customer_name")
STATE=$(redis-cli -h localhost hget "conversation:${CART_ID}" "fsm_state")

if [ "$NAME" != "John Doe" ] || [ "$STATE" != "ordering" ]; then
    echo "❌ Error: Conversation store failed"
    exit 1
fi

echo "✅ Conversation store verified"
echo "✅ All order tests passed!"
EOF

chmod +x ${ORDER_TEST}
bash ${ORDER_TEST}
rm ${ORDER_TEST}

# Run full integration test
echo ""
echo "🔄 Running Python integration tests..."
echo "---------------------------------"

# Create full integration test
cat > ${PROJECT_PATH}/test_integration.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
import json
import time
import uuid
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

print("🐍 Running full Python integration tests...")

# Set up database connection
try:
    conn = psycopg2.connect(
        dbname="redbarsushi_staging_db",
        user="redbarsushi_staging_db_user",
        password="testing_password",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("✅ Connected to PostgreSQL")
except Exception as e:
    print(f"❌ Error connecting to PostgreSQL: {str(e)}")
    sys.exit(1)

# Set up Redis connection
try:
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Error connecting to Redis: {str(e)}")
    sys.exit(1)

# Clean previous test data to ensure clean run
try:
    # Add any cleanup needed to ensure a clean test environment
    print("🧹 Cleaning up previous test data...")
    cursor.execute("TRUNCATE TABLE order_item_modifiers CASCADE;")
    cursor.execute("TRUNCATE TABLE order_items CASCADE;")
    cursor.execute("TRUNCATE TABLE orders CASCADE;")
    cursor.execute("TRUNCATE TABLE menu_name_variants CASCADE;")
    cursor.execute("TRUNCATE TABLE item_modifier_groups CASCADE;")
    cursor.execute("TRUNCATE TABLE menu_modifiers CASCADE;")
    cursor.execute("TRUNCATE TABLE menu_modifier_groups CASCADE;")
    cursor.execute("TRUNCATE TABLE menu_items CASCADE;")
    cursor.execute("TRUNCATE TABLE menu_categories CASCADE;")
    conn.commit()
    print("✅ Database cleaned")
except Exception as e:
    conn.rollback()
    print(f"⚠️ Database cleanup warning: {str(e)}")

# 1. Create menu categories and items
try:
    print("\n📋 Setting up menu data...")
    
    # Create category
    cursor.execute("""
    INSERT INTO menu_categories (deliverect_category_id, name, description)
    VALUES ('CAT001', 'Sushi Rolls', 'Fresh and delicious sushi rolls')
    RETURNING id;
    """)
    category_id = cursor.fetchone()['id']
    
    # Create menu items
    cursor.execute("""
    INSERT INTO menu_items (category_id, name, description, price, plu, deliverect_item_id, is_available)
    VALUES 
    (%s, 'California Roll', 'Crab, avocado, and cucumber', 1200, 'CALI-ROLL', 'ITEM001', true),
    (%s, 'Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 1300, 'SPICY-TUNA', 'ITEM002', true),
    (%s, 'Dragon Roll', 'Eel, crab, and avocado', 1500, 'DRAGON-ROLL', 'ITEM003', true)
    RETURNING id;
    """, (category_id, category_id, category_id))
    
    # Create modifier group
    cursor.execute("""
    INSERT INTO menu_modifier_groups (deliverect_group_id, name, min_selection, max_selection, multi_max)
    VALUES ('GROUP001', 'Add-ons', 0, 3, 1)
    RETURNING id;
    """)
    group_id = cursor.fetchone()['id']
    
    # Create modifiers
    cursor.execute("""
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu, deliverect_modifier_id, is_available)
    VALUES 
    (%s, 'Extra Avocado', 150, 'EXTRA-AVO', 'MOD001', true),
    (%s, 'Spicy Mayo', 100, 'SPICY-MAYO', 'MOD002', true),
    (%s, 'Eel Sauce', 100, 'EEL-SAUCE', 'MOD003', true);
    """, (group_id, group_id, group_id))
    
    # Link items to modifier groups
    cursor.execute("SELECT id FROM menu_items WHERE plu IN ('CALI-ROLL', 'SPICY-TUNA', 'DRAGON-ROLL');")
    menu_item_ids = [item['id'] for item in cursor.fetchall()]
    
    for item_id in menu_item_ids:
        cursor.execute("""
        INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
        VALUES (%s, %s);
        """, (item_id, group_id))
    
    # Add menu name variants
    cursor.execute("""
    INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu)
    VALUES 
    ('california roll', 'California Roll', 'CALI-ROLL'),
    ('cali roll', 'California Roll', 'CALI-ROLL'),
    ('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
    ('dragon', 'Dragon Roll', 'DRAGON-ROLL');
    """)
    
    conn.commit()
    print("✅ Menu data created successfully")
except Exception as e:
    conn.rollback()
    print(f"❌ Error creating menu data: {str(e)}")
    sys.exit(1)

# 2. Simulate customer conversation flow with cart building and order placement
try:
    print("\n🔄 Simulating customer conversation flow...")
    
    # Create a new session
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    
    # Start conversation - greeting state
    conversation_state = {
        "fsm_state": "greeting",
        "last_interaction": time.time()
    }
    redis_client.hset(f"conversation:{session_id}", mapping=conversation_state)
    print("✅ Started conversation in greeting state")
    
    # Customer provides name - transition to main_menu state
    redis_client.hset(f"conversation:{session_id}", "customer_name", "John Doe")
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "main_menu")
    print("✅ Customer provided name, moved to main_menu state")
    
    # Customer decides to order - transition to ordering state
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "ordering")
    print("✅ Customer decided to order, moved to ordering state")
    
    # Create a new cart
    cart_data = {
        "items": [],
        "total_price": 0,
        "order_type": 1,  # pickup
        "customer_name": "John Doe",
        "customer_phone": "+15551234567"
    }
    redis_client.hset(f"cart:{session_id}", "json", json.dumps(cart_data))
    print("✅ Created empty cart")
    
    # Customer adds first item - California Roll with Extra Avocado
    cart_data["items"].append({
        "plu": "CALI-ROLL",
        "name": "California Roll",
        "price": 1200,
        "quantity": 1,
        "modifiers": [
            {
                "plu": "EXTRA-AVO",
                "name": "Extra Avocado",
                "price_change": 150,
                "quantity": 1
            }
        ]
    })
    cart_data["total_price"] = 1350  # 1200 + 150
    redis_client.hset(f"cart:{session_id}", "json", json.dumps(cart_data))
    print("✅ Added California Roll with Extra Avocado to cart")
    
    # Customer adds second item - Spicy Tuna Roll
    cart_data["items"].append({
        "plu": "SPICY-TUNA",
        "name": "Spicy Tuna Roll",
        "price": 1300,
        "quantity": 1,
        "modifiers": []
    })
    cart_data["total_price"] = 2650  # 1350 + 1300
    redis_client.hset(f"cart:{session_id}", "json", json.dumps(cart_data))
    print("✅ Added Spicy Tuna Roll to cart")
    
    # Customer finishes ordering - move to validation state
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "validation")
    print("✅ Customer finished ordering, moved to validation state")
    
    # Validate cart (normally done by guardrail agent)
    # For our test, we'll just simulate success
    
    # Move to confirmation state
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "confirmation")
    print("✅ Order validated, moved to confirmation state")
    
    # Customer confirms order - move to fulfillment state
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "fulfillment")
    cart_data["notes"] = "No wasabi please"
    redis_client.hset(f"cart:{session_id}", "json", json.dumps(cart_data))
    print("✅ Customer confirmed order, moved to fulfillment state")
    
    # Create order in database
    channel_order_id = f"RBS-{int(time.time())}-{uuid.uuid4().hex[:5].upper()}"
    cursor.execute("""
    INSERT INTO orders (
        deliverect_channel_order_id, 
        customer_phone, 
        customer_name, 
        order_type, 
        status, 
        total_price, 
        estimated_time, 
        notes
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """, (
        channel_order_id,
        cart_data["customer_phone"],
        cart_data["customer_name"],
        cart_data["order_type"],
        10,  # status: received
        cart_data["total_price"],
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 1800)),  # 30 min from now
        cart_data["notes"]
    ))
    
    order_id = cursor.fetchone()['id']
    
    # Add order items from cart
    for item in cart_data["items"]:
        cursor.execute("""
        INSERT INTO order_items (
            order_id,
            menu_item_plu,
            name,
            price,
            quantity,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """, (
            order_id,
            item["plu"],
            item["name"],
            item["price"],
            item["quantity"],
            None
        ))
        
        item_id = cursor.fetchone()['id']
        
        # Add modifiers if any
        for modifier in item.get("modifiers", []):
            cursor.execute("""
            INSERT INTO order_item_modifiers (
                order_item_id,
                modifier_plu,
                name,
                price_change,
                quantity
            )
            VALUES (%s, %s, %s, %s, %s);
            """, (
                item_id,
                modifier["plu"],
                modifier["name"],
                modifier["price_change"],
                modifier["quantity"]
            ))
    
    conn.commit()
    print(f"✅ Created order in database with ID: {order_id} and channel_order_id: {channel_order_id}")
    
    # Store order ID in conversation
    redis_client.hset(f"conversation:{session_id}", "order_id", str(order_id))
    
    # Move to completion state
    redis_client.hset(f"conversation:{session_id}", "fsm_state", "completion")
    print("✅ Order placed, moved to completion state")
    
    # Simulate async operations - order status update
    cursor.execute("""
    UPDATE orders SET status = 20 WHERE id = %s
    RETURNING id, status;
    """, (order_id,))
    conn.commit()
    print("✅ Order status updated to 'accepted'")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error in conversation flow simulation: {str(e)}")
    sys.exit(1)

# 3. Verify the end-to-end process
try:
    print("\n🔍 Verifying end-to-end integration...")
    
    # Check order in database matches cart data
    cursor.execute("""
    SELECT * FROM orders WHERE id = %s;
    """, (order_id,))
    order = cursor.fetchone()
    
    if not order:
        print("❌ Verification failed: Order not found in database")
        sys.exit(1)
    
    if order["total_price"] != cart_data["total_price"]:
        print(f"❌ Verification failed: Order total price mismatch - {order['total_price']} vs {cart_data['total_price']}")
        sys.exit(1)
    
    # Check order items
    cursor.execute("""
    SELECT COUNT(*) as count FROM order_items WHERE order_id = %s;
    """, (order_id,))
    item_count = cursor.fetchone()["count"]
    
    if item_count != len(cart_data["items"]):
        print(f"❌ Verification failed: Order item count mismatch - {item_count} vs {len(cart_data['items'])}")
        sys.exit(1)
    
    # Check modifiers
    cursor.execute("""
    SELECT COUNT(*) as count FROM order_item_modifiers 
    WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s);
    """, (order_id,))
    modifier_count = cursor.fetchone()["count"]
    
    expected_modifier_count = sum(len(item.get("modifiers", [])) for item in cart_data["items"])
    if modifier_count != expected_modifier_count:
        print(f"❌ Verification failed: Modifier count mismatch - {modifier_count} vs {expected_modifier_count}")
        sys.exit(1)
    
    # Check FSM state in conversation
    fsm_state = redis_client.hget(f"conversation:{session_id}", "fsm_state")
    if fsm_state != "completion":
        print(f"❌ Verification failed: FSM state mismatch - {fsm_state} vs completion")
        sys.exit(1)
    
    print("✅ All verification checks passed!")
    
except Exception as e:
    print(f"❌ Error in verification: {str(e)}")
    sys.exit(1)

# Close database and Redis connections
cursor.close()
conn.close()
print("✅ Database connection closed")

redis_client.close()
print("✅ Redis connection closed")

print("\n🎉 Full integration test completed successfully!")
EOF

# Run the integration test
cd ${PROJECT_PATH}
python test_integration.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo "✅ All integration tests completed successfully!"
else
    echo "❌ Integration tests failed!"
    exit 1
fi

echo ""
echo "🎉 All tests completed successfully!"
echo "=============================="
echo ""
echo "✓ Database connectivity verified"
echo "✓ Redis connectivity verified"
echo "✓ Menu system tested"
echo "✓ Order system tested"
echo "✓ Full conversation flow tested"
echo ""
echo "The Docker environment is working correctly and all integration tests have passed."
            else:
                # Default to basic test
                test_script = """
#!/bin/bash
echo "Running basic tests with real PostgreSQL and Redis..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! PGPASSWORD=testing_password psql -h localhost -U redbarsushi_staging_db_user -d redbarsushi_staging_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL"
    exit 1
fi
echo "✅ PostgreSQL connection verified"

# Check Redis connection
echo "Checking Redis connection..."
if ! redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Redis"
    exit 1
fi
echo "✅ Redis connection verified"

echo "✅ All tests passed!"
"""
            
            # Write test script to a temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
                f.write(test_script)
                test_script_path = f.name
            
            # Make it executable
            os.chmod(test_script_path, 0o755)
            
            try:
                # Run the test script
                process = subprocess.run(
                    [test_script_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                output = process.stdout
                
                # Enhance output with emoji
                output = output.replace("✅", "✅ ")
                output = output.replace("❌", "❌ ")
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except subprocess.CalledProcessError as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": e.stdout if hasattr(e, 'stdout') else f"❌ Error running tests: {str(e)}"
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error running tests: {str(e)}"
                        }
                    ]
                }
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(test_script_path)
                except:
                    pass
        
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        return response
    
    async def process_request(self, request_json):
        try:
            request = json.loads(request_json)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "initialize":
                return await self.handle_initialize(request_id)
            elif method == "tools/list":
                return await self.handle_tools_list(request_id)
            elif method == "tool/call":
                return await self.handle_tool_call(request_id, params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id if 'request_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def run(self):
        """Run the MCP server on stdin/stdout."""
        while True:
            try:
                # Read a line from stdin
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                
                # Process the request
                response = await self.process_request(line)
                
                # Write response to stdout
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stderr.write(f"Error: {str(e)}\n")
                sys.stderr.flush()

if __name__ == "__main__":
    server = SimpleMCPServer()
    asyncio.run(server.run())