#!/bin/bash
set -e

# This script ensures ALL dependencies are installed properly without any fallbacks

echo "=== Installing ALL dependencies for RedBarSushiAI ==="
echo "=============================================="

# Check if we have sudo access for system packages
if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
    echo "Installing system dependencies with sudo..."
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev libportaudio2 libportaudiocpp0 python3-dev ffmpeg build-essential
elif [ "$(id -u)" -eq 0 ]; then
    echo "Installing system dependencies as root..."
    apt-get update
    apt-get install -y portaudio19-dev libportaudio2 libportaudiocpp0 python3-dev ffmpeg build-essential
else
    echo "WARNING: Cannot install system dependencies. You may need to install these manually:"
    echo "  - portaudio19-dev"
    echo "  - libportaudio2"
    echo "  - libportaudiocpp0"
    echo "  - python3-dev"
    echo "  - ffmpeg"
    echo "  - build-essential"
fi

# Upgrade pip, setuptools, and wheel
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install all dependencies from strict requirements
echo "Installing all dependencies from requirements.strict.txt..."
pip install -r requirements.strict.txt

# Verify critical packages
echo "Verifying critical packages..."
python -c "
import sys

critical_packages = [
    'flask',
    'flask_sqlalchemy',
    'flask_sock',
    'gevent',
    'gunicorn',
    'openai',
    'stripe',
    'twilio',
    'psycopg2',
    'redis',
    'sqlalchemy',
    'celery'
]

missing = []
for package in critical_packages:
    try:
        __import__(package)
        print(f'✓ {package}')
    except ImportError:
        missing.append(package)
        print(f'✗ {package} - MISSING')

if missing:
    print('ERROR: Some critical packages are missing!')
    sys.exit(1)
else:
    print('All critical packages verified successfully!')
"

# Install PyAudio if system dependencies are available
echo "Installing PyAudio..."
pip install pyaudio==0.2.14 || echo "WARNING: PyAudio installation failed, but this is not critical"

# Install OpenAI Realtime client
echo "Installing OpenAI Realtime client..."
pip install --upgrade openai-realtime-client==0.1.0

echo "=== All dependencies installed successfully! ==="