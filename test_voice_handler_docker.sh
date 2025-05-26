#!/bin/bash

echo "============================================================"
echo "VOICE_HANDLER Switch Test (Docker Version)"
echo "============================================================"

# Function to test webhook
test_webhook() {
    local voice_handler=$1
    echo -e "\n[Testing with VOICE_HANDLER=$voice_handler]"
    
    # Show current setting in container
    echo "Current container VOICE_HANDLER:"
    docker exec redbarsushi-app env | grep VOICE_HANDLER || echo "VOICE_HANDLER not set"
    
    # Make webhook request
    echo -e "\nTesting /voice/webhook endpoint..."
    response=$(curl -s -X POST http://localhost:8000/voice/webhook \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -H "User-Agent: TwilioProxy/1.1" \
        -d "CallSid=CA1234567890abcdef1234567890abcdef&AccountSid=AC1234567890abcdef1234567890abcdef&From=%2B15551234567&To=%2B15559876543&CallStatus=ringing")
    
    echo "Response (first 500 chars):"
    echo "$response" | head -c 500
    echo -e "\n"
    
    # Check for expected elements
    if [[ "$voice_handler" == "media_streams" ]] || [[ "$voice_handler" == "realtime" ]]; then
        if echo "$response" | grep -q "<Stream"; then
            echo "✅ Found <Stream> element (Media Streams path)"
        else
            echo "❌ Expected <Stream> element not found!"
        fi
    elif [[ "$voice_handler" == "conversation_relay" ]]; then
        if echo "$response" | grep -q "<ConversationRelay"; then
            echo "✅ Found <ConversationRelay> element (ConversationRelay path)"
        else
            echo "❌ Expected <ConversationRelay> element not found!"
        fi
    fi
}

# Check API health
echo "Checking API health..."
health=$(curl -s http://localhost:8000/healthcheck)
if [ $? -eq 0 ]; then
    echo "✅ API is healthy"
    echo "$health" | python3 -m json.tool | grep -E "status|environment" || echo "$health"
else
    echo "❌ API is not responding"
    exit 1
fi

# Check WebSocket routes
echo -e "\n============================================================"
echo "WebSocket Routes"
echo "============================================================"
curl -s http://localhost:8000/routes | python3 -m json.tool | grep -A 50 "websocket_routes" | grep "path" || echo "No WebSocket routes found"

# Test with current container setting
echo -e "\n============================================================"
echo "Testing Current Configuration"
echo "============================================================"
current_handler=$(docker exec redbarsushi-app env | grep VOICE_HANDLER | cut -d'=' -f2)
test_webhook "$current_handler"

# Instructions for full testing
echo -e "\n============================================================"
echo "Test Summary"
echo "============================================================"
echo "Current VOICE_HANDLER in container: $current_handler"
echo ""
echo "To test both paths:"
echo "1. For Media Streams path:"
echo "   - Edit docker-compose.yml or .env to set VOICE_HANDLER=media_streams"
echo "   - Run: docker-compose restart app"
echo "   - Run this test again"
echo ""
echo "2. For ConversationRelay path:"
echo "   - Edit docker-compose.yml or .env to set VOICE_HANDLER=conversation_relay"
echo "   - Run: docker-compose restart app"
echo "   - Run this test again"
echo ""
echo "Note: The container currently has VOICE_HANDLER=$current_handler"