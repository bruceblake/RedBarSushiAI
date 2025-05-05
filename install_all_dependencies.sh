#\!/bin/bash
# Comprehensive dependency installation script for RedBarSushiAI
# Works in both local development and Render environments

set -e  # Exit on any error

echo "=== Installing ALL dependencies for RedBarSushiAI ==="
echo "=============================================="

# Detect environment
IS_RENDER=false
if [ "$RENDER" = "true" ] || [ -n "$RENDER_SERVICE_ID" ]; then
    IS_RENDER=true
    echo "Detected Render environment"
else
    echo "Detected local environment"
fi

# Function to install system dependencies
install_system_dependencies() {
    echo "Installing system dependencies..."
    if [ "$IS_RENDER" = "true" ]; then
        # On Render, use apt-get
        apt-get update && \
        apt-get install -y --no-install-recommends \
            git \
            gcc \
            g++ \
            libpq-dev \
            curl \
            ffmpeg \
            portaudio19-dev \
            libportaudio2 \
            libportaudiocpp0 \
            python3-dev \
            build-essential
    elif command -v apt-get > /dev/null; then
        # Ubuntu/Debian local environment
        sudo apt-get update && \
        sudo apt-get install -y --no-install-recommends \
            git \
            gcc \
            g++ \
            libpq-dev \
            curl \
            ffmpeg \
            portaudio19-dev \
            libportaudio2 \
            libportaudiocpp0 \
            python3-dev \
            build-essential
    elif command -v pacman > /dev/null; then
        # Arch Linux
        sudo pacman -S --needed --noconfirm \
            git \
            gcc \
            postgresql-libs \
            curl \
            ffmpeg \
            portaudio \
            python-pip \
            base-devel
    elif command -v dnf > /dev/null; then
        # Fedora/RHEL/CentOS
        sudo dnf install -y \
            git \
            gcc \
            gcc-c++ \
            libpq-devel \
            curl \
            ffmpeg \
            portaudio-devel \
            python3-devel \
            redhat-rpm-config
    elif command -v brew > /dev/null; then
        # macOS with Homebrew
        brew install \
            git \
            gcc \
            postgresql \
            curl \
            ffmpeg \
            portaudio \
            python3
    else
        echo "WARNING: Cannot install system dependencies. You may need to install these manually:"
        echo "  - portaudio19-dev"
        echo "  - libportaudio2"
        echo "  - libportaudiocpp0"
        echo "  - python3-dev"
        echo "  - ffmpeg"
        echo "  - build-essential"
    fi
}

# Function to set up virtual environment
setup_venv() {
    echo "Setting up Python virtual environment..."
    
    # Check if venv directory exists
    if [ \! -d "venv" ]; then
        python3 -m venv venv
        echo "Created new virtual environment in 'venv' directory"
    else
        echo "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    else
        echo "ERROR: Could not find activation script for virtual environment"
        exit 1
    fi
    
    echo "Upgrading pip, setuptools, and wheel..."
    pip install --upgrade pip setuptools wheel
}

# Function to install Python dependencies
install_python_dependencies() {
    echo "Installing Python dependencies..."
    
    # Determine which requirements file to use
    REQ_FILE="requirements.strict.txt"
    if [ \! -f "$REQ_FILE" ]; then
        echo "Strict requirements file not found, using regular requirements.txt"
        REQ_FILE="requirements.txt"
        
        if [ \! -f "$REQ_FILE" ]; then
            echo "ERROR: No requirements file found"
            exit 1
        fi
    fi
    
    # Install dependencies
    if [ "$IS_RENDER" = "true" ]; then
        # On Render, use --no-cache-dir to save space
        pip install --no-cache-dir -r "$REQ_FILE"
    else
        pip install -r "$REQ_FILE"
    fi
    
    echo "Python dependencies installed successfully"
}

# Install Portaudio separately to ensure compatibility
install_portaudio() {
    echo "Installing PortAudio dependencies..."
    
    # Try to install PyAudio with pip
    if pip install pyaudio; then
        echo "PyAudio installed successfully"
    else
        echo "PyAudio installation failed, trying with specific compiler flags..."
        
        # On some systems, we need to specify the portaudio path
        if [ "$IS_RENDER" = "true" ]; then
            # On Render, try with system libraries
            PORTAUDIO_PATH="/usr/lib/x86_64-linux-gnu"
            pip install --global-option="build_ext" --global-option="-I/usr/include" --global-option="-L$PORTAUDIO_PATH" pyaudio
        elif [ -d "/usr/lib/x86_64-linux-gnu" ]; then
            # Debian/Ubuntu
            PORTAUDIO_PATH="/usr/lib/x86_64-linux-gnu"
            pip install --global-option="build_ext" --global-option="-I/usr/include" --global-option="-L$PORTAUDIO_PATH" pyaudio
        elif [ -d "/usr/lib64" ]; then
            # RHEL/CentOS/Fedora
            PORTAUDIO_PATH="/usr/lib64"
            pip install --global-option="build_ext" --global-option="-I/usr/include" --global-option="-L$PORTAUDIO_PATH" pyaudio
        elif [ -d "/usr/local/lib" ]; then
            # macOS with Homebrew
            PORTAUDIO_PATH="/usr/local/lib"
            pip install --global-option="build_ext" --global-option="-I/usr/local/include" --global-option="-L$PORTAUDIO_PATH" pyaudio
        else
            echo "WARNING: Could not install PyAudio automatically. You may need to install it manually."
        fi
    fi
}

# Verify critical packages
verify_critical_packages() {
    echo "Verifying critical packages..."
    python -c "
import sys

critical_packages = [
    'flask',
    'flask_sqlalchemy',
    'flask_sock',
    'openai',
    'redis',
    'psycopg2',
    'stripe',
    'pyaudio',
    'celery',
    'twilio',
    'sqlalchemy'
]

missing = []
for package in critical_packages:
    try:
        __import__(package)
        print(f'✓ {package}')
    except ImportError:
        missing.append(package)
        print(f'✗ {package}')

if missing:
    print(f'ERROR: Missing {len(missing)} critical packages: {missing}')
    sys.exit(1)
else:
    print(f'All {len(critical_packages)} critical packages verified successfully')
"
}

# Check for database utilities
check_database_utilities() {
    echo "Checking database utilities..."
    
    # Try to import database libraries
    python -c "
import sqlalchemy
import psycopg2

print('SQLAlchemy version:', sqlalchemy.__version__)
print('psycopg2 version:', psycopg2.__version__)
print('Database utilities verified successfully')
"
}

# Install audio processing utilities
install_audio_utilities() {
    echo "Installing audio processing utilities..."
    
    # Try to install ffmpeg-python
    pip install ffmpeg-python
    
    # Verify ffmpeg
    if command -v ffmpeg > /dev/null; then
        echo "ffmpeg found in PATH"
    else
        echo "WARNING: ffmpeg not found in PATH. Audio processing may not work correctly."
    fi
}

# Main installation flow
main() {
    # Install system dependencies
    install_system_dependencies
    
    # Set up virtual environment if not in Render
    if [ "$IS_RENDER" \!= "true" ]; then
        setup_venv
    fi
    
    # Install Python dependencies
    install_python_dependencies
    
    # Install PortAudio
    install_portaudio
    
    # Install audio utilities
    install_audio_utilities
    
    # Verify critical packages
    verify_critical_packages
    
    # Check database utilities
    check_database_utilities
    
    echo ""
    echo "=== Installation Complete ==="
    echo "All dependencies for RedBarSushiAI have been installed."
    
    if [ "$IS_RENDER" \!= "true" ]; then
        echo ""
        echo "To activate the virtual environment, run:"
        echo "  source venv/bin/activate"
    fi
}

# Run main function
main
