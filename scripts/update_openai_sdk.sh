#!/bin/bash

echo "Updating OpenAI SDK for RedBarSushiAI..."

# Check if running in a virtual environment
if [[ -d "venv" ]]; then
    echo "Using virtual environment: venv"
    SOURCE_CMD="source venv/bin/activate"
    $SOURCE_CMD || { echo "Failed to activate virtual environment"; exit 1; }
elif [[ -d ".venv" ]]; then
    echo "Using virtual environment: .venv"
    SOURCE_CMD="source .venv/bin/activate"
    $SOURCE_CMD || { echo "Failed to activate virtual environment"; exit 1; }
else
    echo "No virtual environment found, proceeding with system Python"
    SOURCE_CMD=""
fi

# Install the latest compatible version of the OpenAI SDK
echo "Installing OpenAI SDK version 1.0.0 or later..."
pip install "openai>=1.0.0,<2.0.0" || { echo "Failed to install OpenAI SDK"; exit 1; }

# Check if running in production (Docker/Render)
if [[ -f "/app/app/__init__.py" ]]; then
    echo "Production environment detected"
    RESTART_CMD="touch /app/wsgi.py"  # Trigger Gunicorn reload
    $RESTART_CMD && echo "Application restart triggered"
else
    echo "Development environment detected"
    echo "Please restart your application manually if needed"
fi

echo "Update complete! The application is now compatible with the latest OpenAI SDK."
echo "You can test the application by running: python run.py"