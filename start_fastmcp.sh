#!/bin/bash
# Start the FastMCP server for RedBarSushiAI

# Activate the virtual environment
source mcp_venv/bin/activate

# Set environment variables
export FLASK_DEBUG=1
export HOST="0.0.0.0"
export PORT="8050"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/redbarsushi"
export REDIS_URL="redis://localhost:6379/0"

# Go to the mcp directory
cd mcp

# Set PYTHONPATH to include current directory
export PYTHONPATH=$(pwd):$PYTHONPATH

# Start the FastMCP server
python main.py