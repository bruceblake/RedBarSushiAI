#!/bin/bash
# Script to help set up ngrok for RedBarSushiAI

set -e  # Exit on any error

echo "===== ngrok Setup Helper for RedBarSushiAI ====="

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

# Check if ngrok is installed
if command -v ngrok &> /dev/null; then
    log "✅ ngrok is already installed"
    ngrok_version=$(ngrok --version)
    log "Version: $ngrok_version"
else
    log "❌ ngrok is not installed"
    
    # Check the operating system
    case "$(uname -s)" in
        Linux*)
            log "📥 Install ngrok on Linux with these commands:"
            echo "curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
            echo "echo \"deb https://ngrok-agent.s3.amazonaws.com buster main\" | sudo tee /etc/apt/sources.list.d/ngrok.list"
            echo "sudo apt update && sudo apt install ngrok"
            ;;
        Darwin*)
            log "📥 Install ngrok on macOS with these commands:"
            echo "brew install ngrok/ngrok/ngrok"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            log "📥 Install ngrok on Windows with these commands:"
            echo "winget install ngrok.ngrok"
            echo "# Or download the installer from https://ngrok.com/download"
            ;;
        *)
            log "📥 Download ngrok from https://ngrok.com/download"
            ;;
    esac
    
    log "After installation, visit https://dashboard.ngrok.com/get-started/your-authtoken to get your authtoken"
    log "Then run: ngrok config add-authtoken YOUR_AUTHTOKEN"
    log "Then return to this script."
    exit 1
fi

# Check ngrok auth
if ngrok config check &> /dev/null; then
    log "✅ ngrok is configured with an authtoken"
else
    log "⚠️ ngrok may not be configured with an authtoken. This is required for tunneling."
    log "Visit https://dashboard.ngrok.com/get-started/your-authtoken to get your authtoken"
    log "Then run: ngrok config add-authtoken YOUR_AUTHTOKEN"
    
    # Prompt for authtoken
    echo
    read -p "Enter your ngrok authtoken (or press Enter to skip): " authtoken
    
    if [ -n "$authtoken" ]; then
        ngrok config add-authtoken "$authtoken"
        log "✅ Authtoken added"
    else
        log "⚠️ No authtoken provided. You may face limitations without it."
    fi
fi

# Check .env.development file
ENV_FILE=".env.development"
if [ -f "$ENV_FILE" ]; then
    log "✅ Found $ENV_FILE file"
    
    # Check if it has ngrok authtoken
    if grep -q "NGROK_AUTHTOKEN" "$ENV_FILE"; then
        log "✅ NGROK_AUTHTOKEN is present in $ENV_FILE"
    else
        log "⚠️ NGROK_AUTHTOKEN is not in $ENV_FILE"
        
        # Get authtoken from ngrok config
        authtoken=$(ngrok config inspect | grep -o "authtoken: [a-zA-Z0-9]*" | awk '{print $2}' || echo "")
        
        if [ -n "$authtoken" ]; then
            log "🔄 Adding ngrok authtoken to $ENV_FILE"
            echo "NGROK_AUTHTOKEN=$authtoken" >> "$ENV_FILE"
        else
            log "⚠️ Could not find ngrok authtoken to add to $ENV_FILE"
        fi
    fi
else
    log "❌ $ENV_FILE not found"
    log "Please copy .env.development.template to .env.development and configure it"
    log "Then run this script again"
    
    if [ -f ".env.development.template" ]; then
        log "📝 Template file exists. Copy it with: cp .env.development.template .env.development"
    else
        log "❌ .env.development.template not found either. Please create the file manually."
    fi
    exit 1
fi

# Test ngrok connection
log "🔄 Testing ngrok connection..."
# Kill any running ngrok processes
pkill -f ngrok || true
# Start a temporary ngrok tunnel
ngrok http 8080 --log=stdout &
NGROK_PID=$!

# Give it a moment to start
sleep 3

# Check if the tunnel is up
if curl -s http://localhost:4040/api/tunnels | grep -q "public_url"; then
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'http[^"]*')
    log "✅ ngrok is working correctly! Test URL: $NGROK_URL"
    
    # Kill the test tunnel
    kill $NGROK_PID || true
    
    log "✅ You're ready to run start_docker_with_ngrok.sh"
else
    log "❌ Failed to start ngrok tunnel. Please check your ngrok installation and network."
    # Kill the test tunnel
    kill $NGROK_PID || true
    
    log "Try running ngrok manually: ngrok http 8080"
    exit 1
fi

echo
echo "===== ngrok Setup Complete ====="
echo "You can now run: ./start_docker_with_ngrok.sh"
echo
echo "When the application is running with ngrok, you can configure Twilio:"
echo "1. Go to https://www.twilio.com/console/voice/twiml/apps"
echo "2. Update your TwiML app's Voice 'REQUEST URL' to: <NGROK_URL>/voice/incoming"
echo "3. Update your TwiML app's Voice 'STATUS CALLBACK URL' to: <NGROK_URL>/voice/status-callback"
echo
echo "Note: Free ngrok URLs change each time you restart the tunnel."
echo "For persistent URLs, upgrade to a paid ngrok plan."