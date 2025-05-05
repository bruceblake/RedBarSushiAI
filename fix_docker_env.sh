#!/bin/bash
# Fix Docker environment for RedBarSushiAI

set -e

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   FIXING DOCKER ENVIRONMENT       ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

echo -e "${YELLOW}Project directory: ${PROJECT_DIR}${NC}"

# Step 1: Fix agent_utils/__init__.py to include OPENAI_API_KEY
echo -e "${YELLOW}Step 1: Fixing agent_utils/__init__.py...${NC}"
AGENT_UTILS_INIT="${PROJECT_DIR}/app/utils/agent_utils/__init__.py"

if [ -f "$AGENT_UTILS_INIT" ]; then
    # Check if OPENAI_API_KEY is already in the file
    if grep -q "OPENAI_API_KEY" "$AGENT_UTILS_INIT"; then
        echo -e "${GREEN}✅ OPENAI_API_KEY already exists in agent_utils/__init__.py${NC}"
    else
        # Add OPENAI_API_KEY to the file
        TMP_FILE=$(mktemp)
        cat > "$TMP_FILE" << 'EOF'
"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.
"""

# Import required modules
import os

# Export OpenAI API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

EOF

        # Append the rest of the original file
        cat "$AGENT_UTILS_INIT" | grep -v '"""' | tail -n +4 >> "$TMP_FILE"

        # Replace the original file
        mv "$TMP_FILE" "$AGENT_UTILS_INIT"

        echo -e "${GREEN}✅ Added OPENAI_API_KEY to agent_utils/__init__.py${NC}"
        
        # Now update the __all__ list if it exists
        if grep -q "__all__" "$AGENT_UTILS_INIT"; then
            TMP_FILE=$(mktemp)
            awk '{
                if ($0 ~ /__all__ = \[/) {
                    print $0;
                    print "    # Environment variables";
                    print "    \"OPENAI_API_KEY\",";
                }
                else print $0;
            }' "$AGENT_UTILS_INIT" > "$TMP_FILE"
            mv "$TMP_FILE" "$AGENT_UTILS_INIT"
            echo -e "${GREEN}✅ Updated __all__ list in agent_utils/__init__.py${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Could not find agent_utils/__init__.py${NC}"
fi

# Step 2: Create menu_data.json if it doesn't exist
echo -e "${YELLOW}Step 2: Checking menu_data.json...${NC}"
MENU_DATA_PATH="${PROJECT_DIR}/menu_data.json"

if [ -f "$MENU_DATA_PATH" ]; then
    echo -e "${GREEN}✅ menu_data.json already exists${NC}"
else
    echo -e "${YELLOW}Creating basic menu_data.json...${NC}"
    # Copy from a template if available or create a basic one
    if [ -f "${PROJECT_DIR}/testing_data/sample_menu.json" ]; then
        cp "${PROJECT_DIR}/testing_data/sample_menu.json" "$MENU_DATA_PATH"
        echo -e "${GREEN}✅ Copied menu_data.json from template${NC}"
    else
        # Create a minimal sample
        cat > "$MENU_DATA_PATH" << EOF
{
  "categories": {
    "sushi_rolls": {
      "_id": "sushi_rolls",
      "name": "Sushi Rolls",
      "posCategoryId": "SR100",
      "subProducts": ["california_roll"]
    }
  },
  "products": {
    "california_roll": {
      "_id": "california_roll",
      "name": "California Roll",
      "description": "Crab, avocado, and cucumber wrapped in seaweed and rice",
      "price": 750,
      "plu": "CALI-ROLL",
      "productType": "menuItem",
      "subProducts": []
    }
  },
  "modifierGroups": {},
  "modifiers": {},
  "menuNameVariants": [
    {
      "variant_phrase": "california roll",
      "canonical_name": "California Roll",
      "target_plu": "CALI-ROLL"
    },
    {
      "variant_phrase": "cali roll",
      "canonical_name": "California Roll",
      "target_plu": "CALI-ROLL"
    }
  ]
}
EOF
        echo -e "${GREEN}✅ Created basic menu_data.json${NC}"
    fi
    
    # Also create a symlink to /app for Docker
    if [ -d "/app" ]; then
        ln -sf "$MENU_DATA_PATH" "/app/menu_data.json" || cp "$MENU_DATA_PATH" "/app/menu_data.json"
        echo -e "${GREEN}✅ Created menu_data.json symlink for Docker${NC}"
    fi
fi

# Step 3: Fix X server for Docker
echo -e "${YELLOW}Step 3: Setting up X server for Docker...${NC}"
if [ -f "${PROJECT_DIR}/fix_x_server.sh" ]; then
    chmod +x "${PROJECT_DIR}/fix_x_server.sh"
    "${PROJECT_DIR}/fix_x_server.sh"
else
    echo -e "${YELLOW}Creating fix_x_server.sh...${NC}"
    cat > "${PROJECT_DIR}/fix_x_server.sh" << 'EOF'
#!/bin/bash
# Fix X server connection issues for OpenAI Realtime client

set -e

echo "===== Fixing X Server Connection for Docker Environment ====="

# Install Xvfb and related X11 packages if not present
if ! command -v Xvfb &> /dev/null; then
    echo "Installing Xvfb and X11 dependencies..."
    apt-get update -y && apt-get install -y xvfb x11-utils xorg dbus-x11 libxrender1 libxtst6 libxi6
fi

# Kill any existing Xvfb processes
echo "Stopping any existing Xvfb processes..."
pkill Xvfb 2>/dev/null || true

# Find a free display number
for display_num in 1 2 3 4 5 99 0; do
    echo "Trying display :${display_num}..."
    
    # Check if display is already in use
    if [ -e "/tmp/.X${display_num}-lock" ]; then
        echo "Display :${display_num} is already in use (lock file exists)"
        continue
    fi
    
    # Start Xvfb on this display with extended parameters for better compatibility
    Xvfb :${display_num} -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
    XVFB_PID=$!
    echo "Started Xvfb process with PID $XVFB_PID"
    
    # Set the DISPLAY environment variable
    export DISPLAY=:${display_num}
    
    # Wait for Xvfb to initialize
    sleep 2
    
    # Test the X server connection
    if xdpyinfo >/dev/null 2>&1; then
        echo "✅ Successfully connected to display :${display_num}"
        
        # Set environment variables for OpenAI Realtime client
        echo "export DISPLAY=:${display_num}" > ~/.xdisplay
        echo "export PYNPUT_HEADLESS=0" >> ~/.xdisplay
        echo "export NO_X11=0" >> ~/.xdisplay
        echo "export HEADLESS=0" >> ~/.xdisplay
        echo "export OPENAI_REALTIME_NO_DISPLAY=0" >> ~/.xdisplay
        echo "export X11_SETUP_SUCCESS=true" >> ~/.xdisplay
        echo "export OPENAI_REALTIME_AVAILABLE=1" >> ~/.xdisplay
        
        # Source the file to set environment variables in the current shell
        source ~/.xdisplay
        
        exit 0
    else
        echo "❌ Failed to connect to display :${display_num}"
        kill $XVFB_PID 2>/dev/null || true
    fi
done

# If we get here, all display attempts failed
echo "❌ Could not set up working X display after trying multiple displays"
echo "Setting up fallback environment variables for headless mode..."

# Set headless mode environment variables
cat > ~/.xdisplay << EOF
export PYNPUT_HEADLESS=1
export NO_X11=1
export HEADLESS=1
export OPENAI_REALTIME_NO_DISPLAY=1
export X11_SETUP_SUCCESS=false
# Still mark realtime as available since we'll use our custom implementation
export OPENAI_REALTIME_AVAILABLE=1
EOF

source ~/.xdisplay

echo "💻 Set up for headless mode operation"
echo "⚠️ OpenAI Realtime client will use fallback WebSocket implementation"
EOF
    chmod +x "${PROJECT_DIR}/fix_x_server.sh"
    "${PROJECT_DIR}/fix_x_server.sh"
fi

# Step 4: Run diagnostics
echo -e "${YELLOW}Step 4: Running diagnostics...${NC}"
if [ -f "${PROJECT_DIR}/diagnose.py" ]; then
    chmod +x "${PROJECT_DIR}/diagnose.py"
    python3 "${PROJECT_DIR}/diagnose.py"
else
    echo -e "${YELLOW}Creating diagnose.py...${NC}"
    cat > "${PROJECT_DIR}/diagnose.py" << 'EOF'
#!/usr/bin/env python3
"""
Quick diagnostics script for RedBarSushiAI Docker environment.
"""
import os
import sys
import subprocess
import importlib

def check_env():
    print("=== Checking Environment Variables ===")
    vars_to_check = ["DISPLAY", "OPENAI_API_KEY", "DATABASE_URL", "REDIS_URL"]
    for var in vars_to_check:
        val = os.environ.get(var, "Not set")
        if var == "OPENAI_API_KEY" and len(val) > 8:
            masked = f"{val[:4]}...{val[-4:]}"
        else:
            masked = val
        print(f"{var}: {masked}")

def check_imports():
    print("\n=== Checking Required Imports ===")
    modules = [
        "flask", "openai", "openai_realtime_client", "websockets", 
        "sqlalchemy", "redis", "app.utils.agent_utils"
    ]
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}: Successfully imported")
        except ImportError as e:
            print(f"❌ {module}: Failed to import - {e}")

def check_x11():
    print("\n=== Checking X11 Connection ===")
    try:
        result = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ X11 display {os.environ.get('DISPLAY', 'Not set')} is working")
        else:
            print(f"❌ X11 display {os.environ.get('DISPLAY', 'Not set')} is not working")
    except Exception as e:
        print(f"❌ Error checking X11: {e}")

def check_agent_utils():
    print("\n=== Checking app.utils.agent_utils ===")
    try:
        # Try to import OPENAI_API_KEY
        from app.utils.agent_utils import OPENAI_API_KEY
        print("✅ Successfully imported OPENAI_API_KEY from app.utils.agent_utils")
    except ImportError as e:
        print(f"❌ Failed to import OPENAI_API_KEY from app.utils.agent_utils: {e}")
    except Exception as e:
        print(f"❌ Error checking app.utils.agent_utils: {e}")

if __name__ == "__main__":
    print("=== RedBarSushiAI Environment Diagnostics ===")
    print(f"Python version: {sys.version}")
    
    check_env()
    check_imports()
    check_x11()
    check_agent_utils()
EOF
    chmod +x "${PROJECT_DIR}/diagnose.py"
    python3 "${PROJECT_DIR}/diagnose.py"
fi

# Step 5: Start Docker environment
echo -e "${YELLOW}Step 5: Setting up Docker environment...${NC}"
DOCKER_COMPOSE_PATH="${PROJECT_DIR}/docker-compose-test.yml"

if [ -f "$DOCKER_COMPOSE_PATH" ]; then
    echo -e "${GREEN}✅ docker-compose-test.yml already exists${NC}"
else
    echo -e "${YELLOW}Creating docker-compose-test.yml...${NC}"
    cat > "$DOCKER_COMPOSE_PATH" << EOF
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

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: redbarsushi_app
    environment:
      - FLASK_APP=run.py
      - FLASK_ENV=testing
      - TESTING=true
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
      - USE_XVFB=true
      - DATABASE_URL=postgresql://redbarsushi_staging_db_user:testing_password@postgres:5432/redbarsushi_staging_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    volumes:
      - ./:/app
      - ./menu_data.json:/app/menu_data.json
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8080:8080"
    command: ["./docker-entrypoint.sh"]

volumes:
  postgres_data:
  redis_data:
EOF
    echo -e "${GREEN}✅ Created docker-compose-test.yml${NC}"
fi

# Check if Docker is running
if ! docker info &>/dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Start Docker containers
echo -e "${YELLOW}Starting Docker containers...${NC}"
docker-compose -f "$DOCKER_COMPOSE_PATH" up -d postgres redis
echo -e "${GREEN}✅ Started PostgreSQL and Redis containers${NC}"

# Create .env.test file
ENV_TEST_PATH="${PROJECT_DIR}/.env.test"
if [ -f "$ENV_TEST_PATH" ]; then
    echo -e "${GREEN}✅ .env.test already exists${NC}"
else
    echo -e "${YELLOW}Creating .env.test...${NC}"
    cat > "$ENV_TEST_PATH" << EOF
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
OPENAI_API_KEY=${OPENAI_API_KEY}
EOF
    echo -e "${GREEN}✅ Created .env.test${NC}"
fi

echo -e "${GREEN}✅ Docker environment setup complete!${NC}"
echo -e "${YELLOW}Your RedBarSushiAI Docker environment is now ready.${NC}"
echo -e "${YELLOW}You can now run tests or start the application.${NC}"
echo
echo -e "${YELLOW}To run tests:${NC}"
echo -e "  - ${GREEN}python -m pytest${NC}"
echo
echo -e "${YELLOW}To run the application:${NC}"
echo -e "  - ${GREEN}docker-compose -f docker-compose-test.yml up app${NC}"
echo
echo -e "${YELLOW}To clean up:${NC}"
echo -e "  - ${GREEN}docker-compose -f docker-compose-test.yml down --volumes${NC}"