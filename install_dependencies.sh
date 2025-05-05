#!/bin/bash
set -e

# Display a message indicating that we're installing dependencies
echo "Installing dependencies for RedBarSushiAI..."
echo "====================================================="

# Make sure pip is up to date
echo "Upgrading pip, setuptools, and wheel..."
pip install --no-cache-dir --upgrade pip setuptools wheel

# Try to install the regular requirements first
echo "Attempting to install full requirements..."
if pip install -r requirements.txt; then
    echo "✅ Successfully installed all requirements"
    exit 0
else
    echo "⚠️ Failed to install full requirements. Analyzing the issue..."
    
    # Check for specific conflicts
    echo "Checking for package conflicts in anyio..."
    if pip install anyio>=3.6.2,\<4.0.0; then
        echo "✅ anyio installed successfully with compatible version"
    else
        echo "❌ anyio installation failed"
    fi
    
    echo "Testing openai installation..."
    if pip install 'openai>=1.0.0,<2.0.0'; then
        echo "✅ openai installed successfully"
    else
        echo "❌ openai installation failed"
    fi
    
    # Checking compatibility of starlette and httpx
    echo "Testing starlette and httpx compatibility..."
    pip install starlette==0.46.0 httpx==0.28.1 || echo "❌ starlette and httpx have conflicts"
    
    # Attempting to install minimal requirements
    echo "Attempting to install minimal requirements for WebSocket functionality..."
    if pip install -r requirements_minimal.txt; then
        echo "✅ Successfully installed minimal requirements"
        echo "⚠️ Some functionality may be limited"
        exit 0
    else
        echo "❌ Even minimal requirements failed. This is a critical error."
        exit 1
    fi
fi