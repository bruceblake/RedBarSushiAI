#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RedBarSushiAI MCP Server

Implements Model Context Protocol (MCP) for RedBarSushiAI using the FastMCP framework.
This server provides tools for testing and debugging the RedBarSushiAI system.
"""

from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import json
import os
import logging
import sys
import redis
import subprocess
import datetime
import time
import docker
import base64
import hashlib
import hmac
import shlex
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Configure logging
log_dir = os.environ.get("LOG_DIR", "mcp")
os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist

# Configure logging with both file and stdout handlers
handlers = [logging.StreamHandler(sys.stdout)]
try:
    handlers.append(logging.FileHandler(f"{log_dir}/redbarsushi_mcp.log"))
except Exception as e:
    print(f"Warning: Could not create log file: {e}")
    print("Continuing with console logging only")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger("redbarsushi_mcp")

# Load environment variables
project_root = Path(__file__).resolve().parent.parent.parent
dotenv_path = project_root / '.env'

if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)
    logger.info(f"Loaded environment from {dotenv_path}")

# Constants
DEFAULT_PROJECT_PATH = str(project_root)
TIMEOUT = 30  # Default operation timeout in seconds

# Create the Redis and SQL connection configuration
REDIS_PORT = 16379
POSTGRES_PORT = 15432

# Global docker client
docker_client = None
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {e}")

# Create application context
@dataclass
class RedBarSushiContext:
    """Context for the RedBarSushi MCP server"""
    docker_client: Optional[docker.DockerClient] = None
    redis_client: Optional[redis.Redis] = None
    db_engine: Optional[Any] = None
    db_session: Optional[Session] = None

@asynccontextmanager
async def redbarsushi_lifespan(server: FastMCP) -> AsyncIterator[RedBarSushiContext]:
    """
    Sets up and tears down the RedBarSushi context for the MCP server
    
    Args:
        server: The FastMCP server
    
    Yields:
        Context for the RedBarSushi MCP server
    """
    # Initialize the context
    context = RedBarSushiContext(
        docker_client=docker_client,
    )
    
    # Try to set up the Redis client
    try:
        context.redis_client = redis.Redis(host='localhost', port=REDIS_PORT, db=0)
        context.redis_client.ping()
        logger.info("Redis client initialized successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        context.redis_client = None
    
    # Try to set up the database connection
    try:
        context.db_engine = create_engine(f'postgresql://redbarsushi:password@localhost:{POSTGRES_PORT}/redbarsushi_test')
        Session = sessionmaker(bind=context.db_engine)
        context.db_session = Session()
        # Test the connection
        context.db_session.execute(text("SELECT 1"))
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        context.db_engine = None
        context.db_session = None
    
    try:
        yield context
    finally:
        # Clean up resources
        if context.db_session:
            context.db_session.close()
        logger.info("Context resources cleaned up")

# Initialize the FastMCP server
mcp = FastMCP(
    "redbarsushi-mcp",
    description="MCP server for RedBarSushiAI testing and debugging",
    lifespan=redbarsushi_lifespan,
    host=os.getenv("HOST", "127.0.0.1"),
    port=int(os.getenv("PORT", "4244"))  # Changed port to avoid conflicts
)

# We'll add health endpoint during server startup instead

@mcp.tool()
async def echo(ctx: Context, message: str) -> str:
    """
    Simple echo tool for testing connectivity.
    
    Args:
        ctx: The MCP server provided context
        message: The message to echo back
    
    Returns:
        The message that was passed in
    """
    return json.dumps({"message": message})

@mcp.tool()
async def check_docker_status(ctx: Context) -> str:
    """
    Check if Docker is running and list running containers.
    
    This tool verifies that Docker is available and returns information about running containers,
    with a focus on the Redis and PostgreSQL containers needed for testing.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with Docker status information
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        if not app_ctx.docker_client:
            return json.dumps({
                "status": "error", 
                "message": "Docker client not initialized."
            })
        
        containers = app_ctx.docker_client.containers.list()
        redis_running = False
        postgres_running = False
        
        container_info = []
        for container in containers:
            image_name = container.image.tags[0] if container.image.tags else str(container.image.id)
            container_info.append({
                "name": container.name,
                "image": image_name,
                "status": container.status
            })
            
            if "redis" in image_name.lower():
                redis_running = True
            if "postgres" in image_name.lower():
                postgres_running = True
        
        return json.dumps({
            "status": "success",
            "docker_running": True,
            "containers": container_info,
            "redis_available": redis_running,
            "postgres_available": postgres_running
        })
    except Exception as e:
        logger.exception(f"Error checking Docker status: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to check Docker status: {str(e)}"
        })

@mcp.tool()
async def setup_docker_env(ctx: Context, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Set up Docker environment with PostgreSQL and Redis for testing.
    
    This tool creates and starts Docker containers with PostgreSQL and Redis that match
    the configuration of the Render staging environment. It also initializes the database
    schema and loads seed data.
    
    Args:
        ctx: The MCP server provided context
        project_path: Path to the RedBarSushiAI project
        
    Returns:
        JSON string with the setup results
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        if not app_ctx.docker_client:
            return json.dumps({
                "status": "error", 
                "message": "Docker client not initialized."
            })
        
        # Check if project path exists
        project_path = str(project_path)
        if not os.path.exists(project_path):
            return json.dumps({
                "status": "error", 
                "message": f"Project path {project_path} does not exist."
            })
        
        # Create docker-compose file if needed
        compose_file = Path(project_path) / "docker-compose-test.yml"
        if not compose_file.exists():
            docker_compose_content = """
version: '3.9'

services:
  redis:
    image: redis:6.2
    ports:
      - "16379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    networks:
      - redbarsushi_network

  postgres:
    image: postgres:14
    ports:
      - "15432:5432"
    environment:
      - POSTGRES_USER=redbarsushi
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=redbarsushi_test
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./mcp/db/init:/docker-entrypoint-initdb.d
    networks:
      - redbarsushi_network

networks:
  redbarsushi_network:
    driver: bridge

volumes:
  redis_data:
  postgres_data:
"""
            with open(compose_file, 'w') as f:
                f.write(docker_compose_content)
            
            logger.info(f"Created docker-compose file at {compose_file}")
        
        # Create DB init directory and SQL files if needed
        db_init_dir = Path(project_path) / "mcp" / "db" / "init"
        db_init_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if schema.sql exists, if not create it
        schema_file = db_init_dir / "01_schema.sql"
        if not schema_file.exists():
            schema_sql = """
-- Create menu tables
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

-- Create order tables
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
    menu_item_plu VARCHAR(255) REFERENCES menu_items(plu),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255) REFERENCES menu_modifiers(plu),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create locations table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    zip VARCHAR(10) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    deliverect_channel_link_id VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""
            with open(schema_file, 'w') as f:
                f.write(schema_sql)
            
            logger.info(f"Created schema file at {schema_file}")
        
        # Check if seed data exists, if not create it
        seed_file = db_init_dir / "02_seed_data.sql"
        if not seed_file.exists():
            seed_sql = """
-- Seed data for testing

-- Insert menu categories
INSERT INTO menu_categories (name, description) VALUES
    ('Sushi Rolls', 'Classic and specialty sushi rolls'),
    ('Nigiri', 'Traditional hand-pressed sushi'),
    ('Appetizers', 'Starters and small plates'),
    ('Beverages', 'Drinks and refreshments');

-- Insert menu items
INSERT INTO menu_items (category_id, name, description, price, plu, is_available) VALUES
    (1, 'California Roll', 'Crab, avocado, cucumber', 1200, 'CALI-ROLL', TRUE),
    (1, 'Spicy Tuna Roll', 'Spicy tuna, cucumber', 1400, 'SPICY-TUNA', TRUE),
    (1, 'Dragon Roll', 'Eel, crab, avocado', 1800, 'DRAGON-ROLL', TRUE),
    (2, 'Salmon Nigiri', 'Fresh salmon', 800, 'SALMON-NIGIRI', TRUE),
    (2, 'Tuna Nigiri', 'Fresh tuna', 900, 'TUNA-NIGIRI', TRUE),
    (3, 'Edamame', 'Steamed soybeans with salt', 600, 'EDAMAME', TRUE),
    (3, 'Miso Soup', 'Traditional Japanese soup', 500, 'MISO-SOUP', TRUE),
    (4, 'Green Tea', 'Hot Japanese green tea', 300, 'GREEN-TEA', TRUE),
    (4, 'Ramune Soda', 'Japanese marble soda', 450, 'RAMUNE', TRUE);

-- Insert modifier groups
INSERT INTO menu_modifier_groups (name, min_selection, max_selection, multi_max, is_variant_group) VALUES
    ('Spice Level', 0, 1, 1, FALSE),
    ('Extras', 0, 5, 1, FALSE),
    ('Substitutions', 0, 1, 1, FALSE);

-- Insert modifiers
INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu) VALUES
    (1, 'Mild', 0, 'SPICE-MILD'),
    (1, 'Medium', 0, 'SPICE-MEDIUM'),
    (1, 'Hot', 0, 'SPICE-HOT'),
    (2, 'Extra Avocado', 150, 'EXTRA-AVO'),
    (2, 'Extra Fish', 300, 'EXTRA-FISH'),
    (2, 'Extra Sauce', 100, 'EXTRA-SAUCE'),
    (3, 'Soy Wrapper', 100, 'SOY-WRAP'),
    (3, 'No Rice', 0, 'NO-RICE');

-- Connect items to modifier groups
INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id) VALUES
    (1, 2), -- California Roll + Extras
    (1, 3), -- California Roll + Substitutions
    (2, 1), -- Spicy Tuna + Spice Level
    (2, 2), -- Spicy Tuna + Extras
    (2, 3), -- Spicy Tuna + Substitutions
    (3, 2), -- Dragon Roll + Extras
    (3, 3); -- Dragon Roll + Substitutions

-- Add name variants
INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu) VALUES
    ('california', 'California Roll', 'CALI-ROLL'),
    ('cali roll', 'California Roll', 'CALI-ROLL'),
    ('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
    ('dragon', 'Dragon Roll', 'DRAGON-ROLL'),
    ('salmon', 'Salmon Nigiri', 'SALMON-NIGIRI'),
    ('tuna', 'Tuna Nigiri', 'TUNA-NIGIRI'),
    ('edamame', 'Edamame', 'EDAMAME'),
    ('miso', 'Miso Soup', 'MISO-SOUP'),
    ('green tea', 'Green Tea', 'GREEN-TEA'),
    ('tea', 'Green Tea', 'GREEN-TEA'),
    ('ramune', 'Ramune Soda', 'RAMUNE'),
    ('soda', 'Ramune Soda', 'RAMUNE');

-- Insert test location
INSERT INTO locations (name, address, city, state, zip, phone, deliverect_channel_link_id, is_active) 
VALUES ('Red Bar Sushi - Test', '123 Main St', 'Seattle', 'WA', '98101', '2065551234', 'test-channel-link-123', TRUE);
"""
            with open(seed_file, 'w') as f:
                f.write(seed_sql)
            
            logger.info(f"Created seed data file at {seed_file}")
        
        # Start the Docker containers
        logger.info("Starting Docker containers...")
        
        try:
            # Check if containers are already running
            existing_containers = app_ctx.docker_client.containers.list(
                filters={"name": ["redbarsushiai_redis_1", "redbarsushiai_postgres_1"]}
            )
            
            if existing_containers:
                logger.info("Containers are already running.")
                return json.dumps({
                    "status": "success",
                    "message": "Docker environment is already set up.",
                    "containers": [container.name for container in existing_containers]
                })
            
            # Start containers using docker-compose
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "up", "-d"],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to start Docker containers: {result.stderr}")
                return json.dumps({
                    "status": "error",
                    "message": f"Failed to start Docker containers: {result.stderr}"
                })
            
            logger.info(f"Docker containers started: {result.stdout}")
            
            # Wait for PostgreSQL and Redis to be ready
            logger.info("Waiting for services to be ready...")
            
            # Try to connect to PostgreSQL
            db_ready = False
            redis_ready = False
            retries = 0
            max_retries = 10
            
            while retries < max_retries and (not db_ready or not redis_ready):
                # Check PostgreSQL
                if not db_ready:
                    try:
                        engine = create_engine(f'postgresql://redbarsushi:password@localhost:{POSTGRES_PORT}/redbarsushi_test')
                        with engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        db_ready = True
                        logger.info("PostgreSQL is ready")
                    except Exception as e:
                        logger.warning(f"PostgreSQL not ready yet: {e}")
                
                # Check Redis
                if not redis_ready:
                    try:
                        r = redis.Redis(host='localhost', port=REDIS_PORT, db=0)
                        r.ping()
                        redis_ready = True
                        logger.info("Redis is ready")
                    except Exception as e:
                        logger.warning(f"Redis not ready yet: {e}")
                
                # If both are ready, break out of the loop
                if db_ready and redis_ready:
                    break
                
                # Sleep before retrying
                retries += 1
                await asyncio.sleep(2)
            
            # Refresh the app context connections
            if db_ready:
                app_ctx.db_engine = create_engine(f'postgresql://redbarsushi:password@localhost:{POSTGRES_PORT}/redbarsushi_test')
                Session = sessionmaker(bind=app_ctx.db_engine)
                app_ctx.db_session = Session()
            
            if redis_ready:
                app_ctx.redis_client = redis.Redis(host='localhost', port=REDIS_PORT, db=0)
            
            return json.dumps({
                "status": "success",
                "message": "Docker environment set up successfully.",
                "postgres_ready": db_ready,
                "redis_ready": redis_ready,
                "compose_file": str(compose_file)
            })
            
        except Exception as e:
            logger.exception(f"Error starting Docker containers: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to set up Docker environment: {str(e)}"
            })
    
    except Exception as e:
        logger.exception(f"Error in setup_docker_env: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to set up Docker environment: {str(e)}"
        })

@mcp.tool()
async def run_test(ctx: Context, test_type: str = "all", maxfail: int = 1, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Executes pytest against everything present under the ./tests directory at call-time.
    
    This tool runs different types of tests against the RedBarSushiAI application,
    from basic connectivity tests to comprehensive system tests.
    
    Args:
        ctx: The MCP server provided context
        test_type: Type of test to run (all, unit, db, voice, webhook)
        maxfail: Maximum number of failed tests before stopping (default: 1)
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        JSON string with test results
    """
    try:
        # 1️⃣ Verify that ./tests exists – pull whatever is there *right now*
        tests_path = Path(project_path) / "tests"
        if not tests_path.exists():
            return json.dumps({
                "passed": False,
                "output": "No tests/ directory found – nothing to run."
            })

        # 2️⃣ Build command dynamically
        if test_type == "all":
            cmd = f"pytest {tests_path} --maxfail={maxfail} --disable-warnings"
        else:
            cmd = f"pytest {tests_path} -m {test_type} --maxfail={maxfail} --disable-warnings"
        
        # 3️⃣ Run
        logger.info(f"Running test command: {cmd}")
        proc = subprocess.run(
            shlex.split(cmd), 
            capture_output=True, 
            text=True, 
            timeout=600,
            cwd=project_path
        )

        return json.dumps({
            "passed": proc.returncode == 0,
            "output": proc.stdout + proc.stderr
        })
    
    except Exception as e:
        logger.exception(f"Error in run_test: {e}")
        return json.dumps({
            "passed": False,
            "output": f"Failed to run test: {str(e)}"
        })

@mcp.tool()
async def list_tests(ctx: Context, marker: str = None, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Return a list of nodeids discovered by pytest --collect-only.
    Optional pytest -m <marker> filter.
    
    Args:
        ctx: The MCP server provided context
        marker: Optional pytest marker to filter tests
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        JSON string with the list of available tests
    """
    try:
        # Verify that ./tests exists
        tests_path = Path(project_path) / "tests"
        if not tests_path.exists():
            return json.dumps({
                "status": "error",
                "message": "No tests/ directory found."
            })

        # Build command dynamically
        if marker:
            cmd = f"pytest {tests_path} --collect-only -m {marker} -q"
        else:
            cmd = f"pytest {tests_path} --collect-only -q"
        
        # Run
        logger.info(f"Running test collection command: {cmd}")
        proc = subprocess.run(
            shlex.split(cmd), 
            capture_output=True, 
            text=True, 
            cwd=project_path
        )

        # Parse the output to extract test nodeids
        tests = []
        for line in proc.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith('[') and not line.startswith('='):
                tests.append(line)

        return json.dumps({
            "status": "success",
            "tests": tests
        })
    
    except Exception as e:
        logger.exception(f"Error in list_tests: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to list tests: {str(e)}"
        })

@mcp.tool()
async def twilio_mock(ctx: Context, payload: str, path: str = "/webhook/voice") -> str:
    """
    Performs an HTTP POST with Twilio-like params to web container; returns {status:int, body:str}.
    
    This tool simulates a Twilio webhook call to test the application's handling of Twilio webhooks.
    
    Args:
        ctx: The MCP server provided context
        payload: The Twilio webhook payload (URL-encoded form data)
        path: The webhook path (default: "/webhook/voice")
        
    Returns:
        JSON string with the response status and body
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        # Parse the payload into a dictionary
        params = {}
        for param in payload.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        # Determine the target URL (default to localhost)
        target_url = f"http://localhost:5000{path}"
        
        # Set up headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'TwilioProxy/1.1'
        }
        
        # Send the request
        logger.info(f"Sending mock Twilio request to {target_url}")
        response = requests.post(target_url, data=payload, headers=headers)
        
        return json.dumps({
            "status": response.status_code,
            "body": response.text
        })
    
    except Exception as e:
        logger.exception(f"Error in twilio_mock: {e}")
        return json.dumps({
            "status": 0,
            "body": f"Failed to send mock Twilio request: {str(e)}"
        })

@mcp.tool()
async def twilio_sig_mock(ctx: Context, payload: str, url: str, auth_token: str = "fake_auth_token") -> str:
    """
    Generates X-Twilio-Signature for given URL/body so signature tests don't fail.
    
    This tool calculates a valid Twilio signature for a given payload and URL.
    
    Args:
        ctx: The MCP server provided context
        payload: The Twilio webhook payload (URL-encoded form data)
        url: The full URL of the webhook endpoint
        auth_token: The Twilio auth token (default: "fake_auth_token")
        
    Returns:
        JSON string with the generated X-Twilio-Signature
    """
    try:
        # Sort the payload params
        param_dict = {}
        for param in payload.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                param_dict[key] = value
        
        # Create the signature payload (url + sorted params)
        validation_payload = url
        for k in sorted(param_dict.keys()):
            validation_payload += k + param_dict[k]
        
        # Calculate the HMAC signature
        signature = hmac.new(
            auth_token.encode('utf-8'),
            validation_payload.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode the signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return json.dumps({
            "status": "success",
            "signature": signature_b64,
            "headers": {
                "X-Twilio-Signature": signature_b64
            }
        })
    
    except Exception as e:
        logger.exception(f"Error in twilio_sig_mock: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to generate Twilio signature: {str(e)}"
        })

@mcp.tool()
async def simulate_media_stream(ctx: Context, file: str, sid: str = None, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Streams assets/<file> (8 kHz μ-law) through ws://web:port/ws/voice/media; returns {"transcript": "...", "agent_response": "..."}.
    
    This tool simulates a real-time media stream to test the application's WebSocket media handling.
    
    Args:
        ctx: The MCP server provided context
        file: The raw audio file to stream (from tests/assets/)
        sid: The call SID to use (default: generated)
        project_path: Path to the RedBarSushiAI project
        
    Returns:
        JSON string with the transcript and agent response
    """
    try:
        import websockets
        import uuid
        import time
        from pathlib import Path
        
        # Generate a random SID if not provided
        if not sid:
            sid = f"CA{uuid.uuid4().hex}"
        
        # Get the path to the audio file
        audio_path = Path(project_path) / "tests" / "assets" / file
        if not audio_path.exists():
            return json.dumps({
                "status": "error",
                "message": f"Audio file not found: {audio_path}"
            })
        
        # Prepare the connection
        ws_url = "ws://localhost:5000/ws/voice/media"
        logger.info(f"Connecting to WebSocket at {ws_url} with SID {sid}")
        
        # This is a placeholder for the actual WebSocket communication
        # In a real implementation, we would:
        # 1. Read the audio file in 20ms chunks
        # 2. Base64 encode each chunk
        # 3. Send as JSON events to the WebSocket
        # 4. Capture responses
        # 5. Stop after server_vad "speech_stopped"
        
        # Simulate the response (in a real implementation, this would come from the WebSocket)
        return json.dumps({
            "status": "success",
            "sid": sid,
            "transcript": "hello i'd like a sushi roll",
            "agent_response": "Sure, what kind of roll would you like?",
            "note": "This is a simulated response. In a real implementation, this would use a WebSocket client to stream the audio file and capture the responses."
        })
    
    except Exception as e:
        logger.exception(f"Error in simulate_media_stream: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to simulate media stream: {str(e)}"
        })

@mcp.tool()
async def openai_realtime_ping(ctx: Context) -> str:
    """
    Opens a short Realtime session (server VAD) from mcp-server to OpenAI; returns latency stats.
    
    This tool tests the connection to OpenAI's Realtime API.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with latency statistics
    """
    try:
        # This is a placeholder for the actual OpenAI Realtime API communication
        # In a real implementation, we would:
        # 1. Open a connection to the OpenAI Realtime API
        # 2. Send a test event
        # 3. Wait for a response
        # 4. Measure the latency
        
        # Simulate the response
        return json.dumps({
            "status": "success",
            "latency_ms": 120,  # Simulated latency
            "timestamp": time.time(),
            "note": "This is a simulated response. In a real implementation, this would connect to the OpenAI Realtime API and measure actual latency."
        })
    
    except Exception as e:
        logger.exception(f"Error in openai_realtime_ping: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to ping OpenAI Realtime API: {str(e)}"
        })

@mcp.tool()
async def deliverect_mock(ctx: Context, payload: str) -> str:
    """
    Posts to a local Flask route /mock/deliverect that imitates 201 Created; toggled by env TESTING=True.
    
    This tool simulates a Deliverect API call to test the application's interaction with Deliverect.
    
    Args:
        ctx: The MCP server provided context
        payload: The Deliverect API payload (JSON string)
        
    Returns:
        JSON string with the response
    """
    try:
        # Parse the payload
        payload_data = json.loads(payload)
        
        # Determine the target URL (default to localhost)
        target_url = "http://localhost:5000/mock/deliverect"
        
        # Set up headers
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer fake_deliverect_token'
        }
        
        # Send the request
        logger.info(f"Sending mock Deliverect request to {target_url}")
        
        # In testing mode, we don't actually need to make the request
        # Instead, we simulate a successful response
        return json.dumps({
            "status": "success",
            "response": {
                "status": 201,
                "body": {
                    "orderId": "mock-order-id-12345",
                    "status": 10,  # Received
                    "channelOrderId": payload_data.get("channelOrderId", "unknown"),
                    "message": "Order created successfully"
                }
            },
            "note": "This is a simulated response. In a real implementation, this would post to the mock Deliverect endpoint in the Flask application."
        })
    
    except Exception as e:
        logger.exception(f"Error in deliverect_mock: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to send mock Deliverect request: {str(e)}"
        })

@mcp.tool()
async def cleanup_docker_env(ctx: Context, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Clean up Docker environment after testing.
    
    This tool stops and removes the Docker containers created for testing.
    
    Args:
        ctx: The MCP server provided context
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        JSON string with cleanup results
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        if not app_ctx.docker_client:
            return json.dumps({
                "status": "error", 
                "message": "Docker client not initialized."
            })
        
        # Check if project path exists
        project_path = str(project_path)
        if not os.path.exists(project_path):
            return json.dumps({
                "status": "error", 
                "message": f"Project path {project_path} does not exist."
            })
        
        # Get compose file path
        compose_file = Path(project_path) / "docker-compose-test.yml"
        if not compose_file.exists():
            return json.dumps({
                "status": "error",
                "message": f"Docker compose file {compose_file} does not exist."
            })
        
        # Stop containers using docker-compose
        logger.info("Stopping Docker containers...")
        
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "down"],
            cwd=project_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to stop Docker containers: {result.stderr}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to stop Docker containers: {result.stderr}"
            })
        
        logger.info(f"Docker containers stopped: {result.stdout}")
        
        # Clean up the context connections
        if app_ctx.db_session:
            app_ctx.db_session.close()
            app_ctx.db_session = None
            app_ctx.db_engine = None
        
        app_ctx.redis_client = None
        
        return json.dumps({
            "status": "success",
            "message": "Docker environment cleaned up successfully."
        })
    
    except Exception as e:
        logger.exception(f"Error cleaning up Docker environment: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to clean up Docker environment: {str(e)}"
        })

@mcp.tool()
async def inspect_db_tables(ctx: Context, table_name: Optional[str] = None) -> str:
    """
    Inspect database tables and their contents.
    
    This tool provides information about database tables and their contents,
    which is useful for debugging database-related issues.
    
    Args:
        ctx: The MCP server provided context
        table_name: Optional name of a specific table to inspect
    
    Returns:
        JSON string with information about database tables
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        if not app_ctx.db_session:
            # Try to reconnect
            try:
                app_ctx.db_engine = create_engine(f'postgresql://redbarsushi:password@localhost:{POSTGRES_PORT}/redbarsushi_test')
                Session = sessionmaker(bind=app_ctx.db_engine)
                app_ctx.db_session = Session()
                app_ctx.db_session.execute(text("SELECT 1"))
            except Exception as e:
                return json.dumps({
                    "status": "error", 
                    "message": f"Database connection failed: {e}. Please run setup_docker_env first."
                })
        
        if table_name:
            # Check if table exists
            exists_result = app_ctx.db_session.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
            ), {"table_name": table_name})
            
            exists = exists_result.scalar()
            
            if not exists:
                return json.dumps({
                    "status": "error",
                    "message": f"Table '{table_name}' does not exist."
                })
            
            # Get table schema
            schema_result = app_ctx.db_session.execute(text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position
                """
            ), {"table_name": table_name})
            
            schema = [dict(row._mapping) for row in schema_result]
            
            # Get row count
            count_result = app_ctx.db_session.execute(text(
                f"SELECT COUNT(*) FROM {table_name}"
            ))
            
            count = count_result.scalar()
            
            # Get sample data (up to 10 rows)
            sample_result = app_ctx.db_session.execute(text(
                f"SELECT * FROM {table_name} LIMIT 10"
            ))
            
            sample = [dict(row._mapping) for row in sample_result]
            
            return json.dumps({
                "status": "success",
                "table_name": table_name,
                "schema": schema,
                "row_count": count,
                "sample_data": sample
            })
        else:
            # Get all tables
            tables_result = app_ctx.db_session.execute(text(
                """
                SELECT table_name, 
                       (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) AS column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            ))
            
            tables = []
            for row in tables_result:
                table_info = dict(row._mapping)
                
                # Get row count for each table
                count_result = app_ctx.db_session.execute(text(
                    f"SELECT COUNT(*) FROM {table_info['table_name']}"
                ))
                
                table_info['row_count'] = count_result.scalar()
                tables.append(table_info)
            
            return json.dumps({
                "status": "success",
                "tables": tables
            })
    
    except Exception as e:
        logger.exception(f"Error inspecting database tables: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to inspect database tables: {str(e)}"
        })

@mcp.tool()
async def inspect_redis_keys(ctx: Context, pattern: str = "*") -> str:
    """
    Inspect Redis keys and their values.
    
    This tool provides information about Redis keys and their values,
    which is useful for debugging Redis-related issues.
    
    Args:
        ctx: The MCP server provided context
        pattern: Optional pattern to filter keys (default: "*")
    
    Returns:
        JSON string with information about Redis keys
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        
        if not app_ctx.redis_client:
            # Try to reconnect
            try:
                app_ctx.redis_client = redis.Redis(host='localhost', port=REDIS_PORT, db=0)
                app_ctx.redis_client.ping()
            except Exception as e:
                return json.dumps({
                    "status": "error", 
                    "message": f"Redis connection failed: {e}. Please run setup_docker_env first."
                })
        
        # Get keys matching the pattern
        keys = app_ctx.redis_client.keys(pattern)
        
        results = []
        for key in keys:
            key_str = key.decode('utf-8')
            key_type = app_ctx.redis_client.type(key).decode('utf-8')
            
            # Get appropriate value based on type
            value = None
            if key_type == 'string':
                value = app_ctx.redis_client.get(key).decode('utf-8')
            elif key_type == 'hash':
                hash_value = app_ctx.redis_client.hgetall(key)
                value = {k.decode('utf-8'): v.decode('utf-8') for k, v in hash_value.items()}
            elif key_type == 'list':
                value = [item.decode('utf-8') for item in app_ctx.redis_client.lrange(key, 0, -1)]
            elif key_type == 'set':
                value = [item.decode('utf-8') for item in app_ctx.redis_client.smembers(key)]
            elif key_type == 'zset':
                value = {item[0].decode('utf-8'): item[1] for item in app_ctx.redis_client.zrange(key, 0, -1, withscores=True)}
            
            # Get TTL (Time To Live)
            ttl = app_ctx.redis_client.ttl(key)
            
            results.append({
                "key": key_str,
                "type": key_type,
                "ttl": ttl,
                "value": value
            })
        
        return json.dumps({
            "status": "success",
            "keys_count": len(keys),
            "keys": results
        })
    
    except Exception as e:
        logger.exception(f"Error inspecting Redis keys: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to inspect Redis keys: {str(e)}"
        })

@mcp.tool()
async def system_diagnostics(ctx: Context, project_path: str = DEFAULT_PROJECT_PATH) -> str:
    """
    Run comprehensive system diagnostics on the RedBarSushiAI application.
    
    This tool runs a series of diagnostic tests on the RedBarSushiAI application,
    checking for common configuration and dependency issues.
    
    Args:
        ctx: The MCP server provided context
        project_path: Path to the RedBarSushiAI project
    
    Returns:
        JSON string with diagnostic results
    """
    try:
        app_ctx: RedBarSushiContext = ctx.app_context
        results = {}
        
        # Check Python version
        python_version = sys.version
        results["python_version"] = {
            "status": "success",
            "version": python_version
        }
        
        # Check dependencies
        try:
            req_file = Path(project_path) / "requirements.txt"
            if req_file.exists():
                with open(req_file, 'r') as f:
                    requirements = f.read().strip().split('\n')
                
                missing_deps = []
                installed_deps = []
                
                for req in requirements:
                    if req and not req.startswith('#'):
                        # Parse requirement name
                        req_name = req.split('==')[0].split('>=')[0].split('<=')[0].strip()
                        try:
                            __import__(req_name.replace('-', '_'))
                            installed_deps.append(req_name)
                        except ImportError:
                            missing_deps.append(req_name)
                
                results["dependencies"] = {
                    "status": "success" if not missing_deps else "error",
                    "installed": installed_deps,
                    "missing": missing_deps
                }
        except Exception as e:
            results["dependencies"] = {
                "status": "error",
                "message": f"Failed to check dependencies: {str(e)}"
            }
        
        # Check configuration files
        config_files = [
            ".env",
            "docker-compose.yml",
            "Procfile",
            "render.yaml"
        ]
        
        existing_configs = []
        missing_configs = []
        
        for config in config_files:
            config_path = Path(project_path) / config
            if config_path.exists():
                existing_configs.append(config)
            else:
                missing_configs.append(config)
        
        results["config_files"] = {
            "status": "success" if not missing_configs else "warning",
            "existing": existing_configs,
            "missing": missing_configs
        }
        
        # Check database connection
        db_status = "success" if app_ctx.db_session else "error"
        results["database"] = {
            "status": db_status,
            "message": "Connected to PostgreSQL database" if app_ctx.db_session else "Database connection failed"
        }
        
        # Check Redis connection
        redis_status = "success" if app_ctx.redis_client else "error"
        results["redis"] = {
            "status": redis_status,
            "message": "Connected to Redis" if app_ctx.redis_client else "Redis connection failed"
        }
        
        # Check for Docker
        docker_status = "success" if app_ctx.docker_client else "error"
        results["docker"] = {
            "status": docker_status,
            "message": "Docker is available" if app_ctx.docker_client else "Docker is not available"
        }
        
        # Check if application can be imported
        try:
            sys.path.insert(0, project_path)
            from wsgi import app
            results["application"] = {
                "status": "success",
                "message": "Flask application imported successfully"
            }
        except Exception as e:
            results["application"] = {
                "status": "error",
                "message": f"Failed to import Flask application: {str(e)}"
            }
        
        # Overall status
        error_count = sum(1 for result in results.values() if result.get("status") == "error")
        warning_count = sum(1 for result in results.values() if result.get("status") == "warning")
        
        if error_count > 0:
            overall_status = "error"
            overall_message = f"System diagnostics found {error_count} errors and {warning_count} warnings"
        elif warning_count > 0:
            overall_status = "warning"
            overall_message = f"System diagnostics found {warning_count} warnings"
        else:
            overall_status = "success"
            overall_message = "All system diagnostics passed successfully"
        
        return json.dumps({
            "status": overall_status,
            "message": overall_message,
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results
        })
    
    except Exception as e:
        logger.exception(f"Error running system diagnostics: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to run system diagnostics: {str(e)}"
        })

async def main():
    transport = os.getenv("TRANSPORT", "sse")
    port = int(os.getenv("PORT", "4244"))
    host = os.getenv("HOST", "127.0.0.1")
    logger.info(f"Starting RedBarSushi MCP Server with {transport} transport on {host}:{port}")
    
    # No need for explicit health endpoint - we'll use the SSE endpoint for health checks
    
    if transport == 'sse':
        # Run the MCP server with sse transport
        await mcp.run_sse_async()
    else:
        # Run the MCP server with stdio transport
        await mcp.run_stdio_async()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())