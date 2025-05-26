#!/bin/bash

echo "🍣 Red Bar Sushi - Deliverect Integration Setup"
echo "=============================================="
echo ""

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if the app is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ API server is not running. Starting it now..."
    ./start_docker.sh &
    echo "⏳ Waiting for API server to start..."
    sleep 10
    
    # Check again
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "❌ Failed to start API server. Please check logs."
        exit 1
    fi
fi

echo "✅ API server is running"
echo ""

# Test the menu webhook locally first
echo "📋 Testing menu webhook locally..."
python test_deliverect_menu.py

echo ""
echo "=============================================="
echo "📌 Next Steps for Deliverect Integration:"
echo ""
echo "1. EXPOSE YOUR LOCAL SERVER (for webhook testing):"
echo "   Option A - Using ngrok (recommended):"
echo "   - Install ngrok: https://ngrok.com/download"
echo "   - Run: ngrok http 8000"
echo "   - Copy the HTTPS URL (e.g., https://abc123.ngrok.io)"
echo ""
echo "   Option B - Using localtunnel:"
echo "   - Install: npm install -g localtunnel"
echo "   - Run: lt --port 8000"
echo "   - Copy the URL provided"
echo ""
echo "2. REGISTER THE WEBHOOK:"
echo "   python test_deliverect_menu.py --register --public-url https://your-public-url.ngrok.io"
echo ""
echo "3. CONFIGURE DELIVERECT:"
echo "   - Log into your Deliverect dashboard"
echo "   - Go to Settings > Webhooks"
echo "   - Add webhook URL: https://your-public-url.ngrok.io/api/menu/webhook/deliverect/menu"
echo "   - Select 'Menu Update' event type"
echo "   - Save the configuration"
echo ""
echo "4. TEST THE INTEGRATION:"
echo "   - Make a change to your menu in Deliverect"
echo "   - Check the logs to see the webhook being called"
echo "   - Verify menu items are stored in the database"
echo ""
echo "=============================================="