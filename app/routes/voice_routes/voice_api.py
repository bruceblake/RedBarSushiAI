"""
Voice API module. This module contains REST API endpoints for voice-related functionality.
"""

import logging
import json
from flask import request, jsonify, session, Response, current_app
from twilio.twiml.voice_response import VoiceResponse

# Import blueprint
from . import voice_bp

# Import helpers
from .voice_core import get_session_id

# Import agent utilities
from app.utils.agent_utils import analyze_user_input, get_order_modifications, OrderParsingAgent

# Set up logger
logger = logging.getLogger(__name__)

@voice_bp.route("/api/analyze", methods=["POST"])
def analyze():
    """
    API endpoint to analyze user input for intent.
    
    This endpoint:
    1. Takes user input as JSON
    2. Analyzes it for ordering intent
    3. Returns structured data about detected items and intents
    
    Used by web clients to process user input without a voice call.
    """
    data = request.json
    user_input = data.get("input", "")
    
    if not user_input:
        return jsonify({"error": "No input provided"}), 400
    
    # Log the analysis request
    logger.info(f"Analyzing input: {user_input}")
    
    # Process the input with our agent
    try:
        result = analyze_user_input(user_input)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error analyzing input: {str(e)}")
        return jsonify({"error": str(e)}), 500

@voice_bp.route("/api/modify", methods=["POST"])
def modify():
    """
    API endpoint to modify existing orders.
    
    This endpoint:
    1. Takes order data and modification instructions
    2. Processes the modifications
    3. Returns the updated order
    
    Used by web clients to modify orders based on user input.
    """
    data = request.json
    order_items = data.get("order_items", [])
    modification = data.get("modification", "")
    
    if not order_items or not modification:
        return jsonify({"error": "Missing required parameters"}), 400
    
    # Log the modification request
    logger.info(f"Modifying order with: {modification}")
    
    # Process the modification with our agent
    try:
        result = get_order_modifications(order_items, modification)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error modifying order: {str(e)}")
        return jsonify({"error": str(e)}), 500

@voice_bp.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Simple health check endpoint to verify the service is running.
    
    This endpoint:
    1. Checks basic application health
    2. Returns status information
    
    Used by monitoring systems to verify service availability.
    """
    # Check if we have access to the OpenAI API
    openai_available = True
    try:
        import openai
        openai.api_key  # Will raise AttributeError if key is not set
    except (ImportError, AttributeError):
        openai_available = False
    
    # Build health check response
    health_data = {
        "status": "up",
        "version": current_app.config.get("APP_VERSION", "unknown"),
        "openai_available": openai_available,
        "twilio_configured": "TWILIO_ACCOUNT_SID" in current_app.config,
    }
    
    # Return the health check data
    return jsonify(health_data)

@voice_bp.route("/api/ws/capabilities", methods=["GET"])
def websocket_capabilities():
    """
    API endpoint to describe WebSocket capabilities.
    
    This endpoint:
    1. Returns information about available WebSocket endpoints
    2. Describes their purposes and expected data formats
    
    Used by web clients to understand available WebSocket services.
    """
    # Build capabilities information
    capabilities = {
        "endpoints": [
            {
                "path": "/api/ws/speech-to-text",
                "description": "Real-time speech-to-text conversion",
                "formats": ["audio/webm", "audio/wav"],
                "protocols": ["binary"],
                "options": {
                    "interim_results": "boolean - whether to return interim results"
                }
            },
            {
                "path": "/api/ws/conversation",
                "description": "Multi-turn conversation with the AI assistant",
                "formats": ["application/json"],
                "protocols": ["text"],
                "message_format": {
                    "message": "string - user's message",
                    "session_id": "string - optional session identifier"
                }
            },
            {
                "path": "/api/ws/text-to-speech",
                "description": "Real-time text-to-speech conversion",
                "formats": ["application/json"],
                "protocols": ["text/binary"],
                "message_format": {
                    "text": "string - text to convert to speech",
                    "voice": "string - optional voice identifier"
                }
            }
        ],
        "supported_browsers": [
            "Chrome 25+", "Firefox 22+", "Safari 11+", "Edge 12+"
        ]
    }
    
    # Return the capabilities information
    return jsonify(capabilities)

@voice_bp.route("/demo", methods=["GET"])
def realtime_demo():
    """
    Simple demo page for real-time speech features.
    
    This route:
    1. Renders a basic HTML page with WebSocket demos
    2. Shows real-time speech-to-text and conversation
    
    Used for testing and demonstration of WebSocket capabilities.
    """
    demo_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Red Bar Sushi AI - Real-time Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            button { padding: 10px 15px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; }
            button:disabled { background: #ccc; }
            .transcript { min-height: 100px; border: 1px solid #eee; padding: 10px; margin-top: 10px; }
            .response { color: #e74c3c; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Red Bar Sushi AI - Real-time Demo</h1>
            
            <div class="card">
                <h2>Speech-to-Text</h2>
                <p>Click the button and speak to see real-time transcription.</p>
                <button id="sttButton">Start Listening</button>
                <div class="transcript" id="sttTranscript"></div>
            </div>
            
            <div class="card">
                <h2>Conversation</h2>
                <p>Type a message to chat with the AI assistant.</p>
                <input type="text" id="messageInput" placeholder="Type your message..." style="width: 70%; padding: 8px;">
                <button id="sendButton">Send</button>
                <div class="transcript" id="conversationTranscript"></div>
            </div>
        </div>
        
        <script>
            // Speech-to-Text
            const sttButton = document.getElementById('sttButton');
            const sttTranscript = document.getElementById('sttTranscript');
            let sttSocket;
            let mediaRecorder;
            let isRecording = false;
            
            sttButton.addEventListener('click', () => {
                if (isRecording) {
                    stopRecording();
                } else {
                    startRecording();
                }
            });
            
            async function startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    
                    // Set up WebSocket
                    sttSocket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws/speech-to-text`);
                    
                    sttSocket.onopen = () => {
                        console.log('STT WebSocket connected');
                        sttButton.textContent = 'Stop Listening';
                        isRecording = true;
                        sttTranscript.textContent = 'Listening...';
                    };
                    
                    sttSocket.onmessage = (event) => {
                        const result = JSON.parse(event.data);
                        if (result.text) {
                            sttTranscript.textContent = result.text;
                        }
                    };
                    
                    sttSocket.onclose = () => {
                        console.log('STT WebSocket closed');
                    };
                    
                    // Send audio data
                    mediaRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0 && sttSocket.readyState === WebSocket.OPEN) {
                            sttSocket.send(event.data);
                        }
                    };
                    
                    mediaRecorder.start(250);
                } catch (error) {
                    console.error('Error starting recording:', error);
                    sttTranscript.textContent = 'Error: ' + error.message;
                }
            }
            
            function stopRecording() {
                if (mediaRecorder && isRecording) {
                    mediaRecorder.stop();
                    mediaRecorder.stream.getTracks().forEach(track => track.stop());
                    sttButton.textContent = 'Start Listening';
                    isRecording = false;
                }
                
                if (sttSocket) {
                    sttSocket.close();
                }
            }
            
            // Conversation
            const sendButton = document.getElementById('sendButton');
            const messageInput = document.getElementById('messageInput');
            const conversationTranscript = document.getElementById('conversationTranscript');
            let conversationSocket;
            
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
            
            function setupConversationSocket() {
                if (conversationSocket && conversationSocket.readyState === WebSocket.OPEN) {
                    return;
                }
                
                conversationSocket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws/conversation`);
                
                conversationSocket.onopen = () => {
                    console.log('Conversation WebSocket connected');
                    sendButton.disabled = false;
                };
                
                conversationSocket.onmessage = (event) => {
                    const response = JSON.parse(event.data);
                    if (response.message) {
                        conversationTranscript.innerHTML += `<div class="response">AI: ${response.message}</div>`;
                    }
                };
                
                conversationSocket.onclose = () => {
                    console.log('Conversation WebSocket closed');
                    sendButton.disabled = true;
                    setTimeout(setupConversationSocket, 3000);
                };
            }
            
            function sendMessage() {
                const message = messageInput.value.trim();
                if (message && conversationSocket && conversationSocket.readyState === WebSocket.OPEN) {
                    conversationTranscript.innerHTML += `<div>You: ${message}</div>`;
                    conversationSocket.send(JSON.stringify({ message }));
                    messageInput.value = '';
                }
            }
            
            // Initialize
            setupConversationSocket();
        </script>
    </body>
    </html>
    """
    
    return Response(demo_html, mimetype="text/html")