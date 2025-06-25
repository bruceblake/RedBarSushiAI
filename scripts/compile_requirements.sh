#!/bin/bash
# Script to compile requirements files using pip-tools

echo "🔧 Compiling requirements files..."

# Check if pip-tools is installed
if ! command -v pip-compile &> /dev/null; then
    echo "❌ pip-tools not installed. Installing..."
    pip install pip-tools
fi

# Compile production requirements
echo "📦 Compiling production requirements..."
pip-compile requirements.in -o requirements.txt \
    --resolver=backtracking \
    --verbose \
    --strip-extras

# Compile development requirements
echo "🛠️  Compiling development requirements..."
pip-compile requirements-dev.in -o requirements-dev.txt \
    --resolver=backtracking \
    --verbose \
    --strip-extras

echo "✅ Requirements compilation complete!"
echo ""
echo "To install:"
echo "  Production: pip install -r requirements.txt"
echo "  Development: pip install -r requirements-dev.txt"