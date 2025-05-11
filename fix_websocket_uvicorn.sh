#!/bin/bash
set -e

# This script fixes WebSocket-related issues with Uvicorn on Render
# The key issues:
# 1. Multiple workers causing WebSocket connections to be routed to different workers
# 2. Uvicorn configuration for proper WebSocket support

# Function to log messages with timestamps
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $@"
}

log "Starting WebSocket/Uvicorn fixes for Render deployment..."

# Check if we're running in Render's environment
if [ -n "$RENDER_SERVICE_ID" ]; then
  log "Detected Render environment"
  export RENDER=true
else
  log "Not running in Render, using local environment settings"
fi

# Modify Dockerfile to use a single Uvicorn worker
log "Updating Dockerfile CMD to use a single worker..."
sed -i 's/CMD \["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--log-level", "info"\]/CMD \["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "debug"\]/g' Dockerfile

# Update fastapi_render_entrypoint.sh to use a single worker
log "Updating fastapi_render_entrypoint.sh to use a single worker and proper config..."
sed -i 's/exec uvicorn app.main:app --host 0.0.0.0 --port $PORT/exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --log-level debug/g' fastapi_render_entrypoint.sh
sed -i 's/exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers $WORKER_COUNT --log-level info/exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --log-level debug/g' fastapi_render_entrypoint.sh

# Create a WebSocket test file in main.py if it doesn't exist
log "Adding WebSocket test endpoint to main.py..."
if ! grep -q "app.websocket(\"/ws-test/{client_id}\")" main.py; then
    # Insert WebSocket imports
    sed -i 's/from fastapi import FastAPI, Depends, Request/from fastapi import FastAPI, Depends, Request, WebSocket, WebSocketDisconnect/g' main.py
    
    # Insert the test WebSocket endpoint before the first @app.get
    cat > insert.txt << 'EOF'
# WebSocket test endpoint for diagnostics
@app.websocket("/ws-test/{client_id}")
async def websocket_test_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket test endpoint for diagnostics."""
    print(f"⚠️ WEBSOCKET TEST: Connection attempt from {client_id}")
    logging.critical(f"⚠️ WEBSOCKET TEST: Connection attempt from {client_id}")
    
    try:
        await websocket.accept()
        print(f"✅ WEBSOCKET TEST: Connection accepted for {client_id}")
        logging.critical(f"✅ WEBSOCKET TEST: Connection accepted for {client_id}")
        
        # Send an initial message
        await websocket.send_text(f"Hello, {client_id}! Connection established.")
        
        # Echo messages back to the client
        while True:
            data = await websocket.receive_text()
            logging.info(f"WEBSOCKET TEST: Received message from {client_id}: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logging.warning(f"WEBSOCKET TEST: Client {client_id} disconnected")
    except Exception as e:
        logging.error(f"WEBSOCKET TEST: Error with {client_id}: {str(e)}")
        print(f"❌ WEBSOCKET TEST: Error with {client_id}: {str(e)}")
    finally:
        logging.info(f"WEBSOCKET TEST: Connection closed for {client_id}")

EOF
    
    # Find the line number of the first @app.get decorator
    line_num=$(grep -n "@app.get" main.py | head -1 | cut -d':' -f1)
    
    # Insert the text before the first @app.get line
    sed -i "${line_num}r insert.txt" main.py
    
    # Remove temporary file
    rm insert.txt
fi

# Update render.yaml to use proper entry command for WebSockets
if [ -f "render.yaml" ]; then
    log "Updating render.yaml to use proper WebSocket configuration..."
    
    # For staging environment, update the build command to run our WebSocket fix script
    if grep -q "name: redbarsushi-staging" render.yaml; then
        sed -i '/name: redbarsushi-staging/,/buildCommand:/ s/buildCommand: .*/buildCommand: \.\\/fix_render_deploy.sh \&\& \.\\/fix_websocket_uvicorn.sh/g' render.yaml
    fi
fi

# Create a HTML test page for WebSocket connections
log "Creating WebSocket test HTML page..."
mkdir -p static
cat > static/websocket-test.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket Connection Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        #status { font-weight: bold; margin-bottom: 10px; }
        #log { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: auto; background-color: #f9f9f9; }
        .connected { color: green; }
        .disconnected { color: red; }
        .error { color: darkred; }
        .message { color: blue; }
        input[type="text"] { width: 70%; padding: 5px; margin-right: 10px; }
        button { padding: 5px 10px; }
        #urlInput { width: 70%; margin-right: 10px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <h1>WebSocket Connection Test</h1>
    
    <div>
        <label for="urlInput">WebSocket URL:</label><br>
        <input type="text" id="urlInput" placeholder="wss://yourserver.com/ws-test/browser" value="wss://redbarsushiai-staging.onrender.com/ws-test/browser">
        <button id="connect">Connect</button>
        <button id="disconnect" disabled>Disconnect</button>
    </div>
    
    <div id="status" class="disconnected">Disconnected</div>
    
    <div id="messageForm" style="display: none;">
        <input type="text" id="messageInput" placeholder="Type a message...">
        <button id="send">Send</button>
    </div>
    
    <h3>Connection Log:</h3>
    <div id="log"></div>
    
    <script>
        let socket = null;
        const statusEl = document.getElementById('status');
        const logEl = document.getElementById('log');
        const connectBtn = document.getElementById('connect');
        const disconnectBtn = document.getElementById('disconnect');
        const messageForm = document.getElementById('messageForm');
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('send');
        const urlInput = document.getElementById('urlInput');
        
        function log(message, className) {
            const line = document.createElement('div');
            line.className = className || '';
            line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            logEl.appendChild(line);
            logEl.scrollTop = logEl.scrollHeight;
        }
        
        function connect() {
            if (socket) {
                log('Already connected! Disconnect first.', 'error');
                return;
            }
            
            const url = urlInput.value;
            if (!url) {
                log('Please enter a WebSocket URL', 'error');
                return;
            }
            
            try {
                log(`Attempting to connect to ${url}...`);
                socket = new WebSocket(url);
                
                socket.onopen = () => {
                    log('Connection established!', 'connected');
                    statusEl.textContent = 'Connected';
                    statusEl.className = 'connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    messageForm.style.display = 'block';
                };
                
                socket.onmessage = (event) => {
                    log(`Received: ${event.data}`, 'message');
                };
                
                socket.onclose = (event) => {
                    log(`Connection closed. Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`);
                    statusEl.textContent = 'Disconnected';
                    statusEl.className = 'disconnected';
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    messageForm.style.display = 'none';
                    socket = null;
                };
                
                socket.onerror = (error) => {
                    log('WebSocket error', 'error');
                    console.error('WebSocket error:', error);
                };
            } catch (error) {
                log(`Failed to create WebSocket: ${error.message}`, 'error');
            }
        }
        
        function disconnect() {
            if (socket) {
                log('Closing connection...');
                socket.close();
            }
        }
        
        function sendMessage() {
            if (!socket) {
                log('Not connected!', 'error');
                return;
            }
            
            const message = messageInput.value;
            if (!message) {
                return;
            }
            
            try {
                socket.send(message);
                log(`Sent: ${message}`);
                messageInput.value = '';
            } catch (error) {
                log(`Failed to send message: ${error.message}`, 'error');
            }
        }
        
        connectBtn.addEventListener('click', connect);
        disconnectBtn.addEventListener('click', disconnect);
        sendBtn.addEventListener('click', sendMessage);
        
        messageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Log connection details - This helps diagnose issues
        log(`Browser: ${navigator.userAgent}`);
        log(`Page URL: ${window.location.href}`);
    </script>
</body>
</html>
EOF

# Add route for the test page
if ! grep -q "app.get(\"/ws-test-page\")" main.py; then
    log "Adding test page route to main.py..."
    cat > insert.txt << 'EOF'
@app.get("/ws-test-page")
async def websocket_test_page():
    """Redirect to WebSocket test page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/websocket-test.html")

EOF
    
    # Find the line number of the first @app.get decorator
    line_num=$(grep -n "@app.get" main.py | head -1 | cut -d':' -f1)
    
    # Insert the text before the first @app.get line
    sed -i "${line_num}r insert.txt" main.py
    
    # Remove temporary file
    rm insert.txt
fi

# Ensure static files are served
if ! grep -q "app.mount(\"/static\"" main.py; then
    log "Adding static files mounting to main.py..."
    cat > insert.txt << 'EOF'
# Mount static files directory
from fastapi.staticfiles import StaticFiles
import os

# Create static directory if it doesn't exist
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    logging.info(f"Created static directory: {static_dir}")

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")
logging.info(f"Mounted static files directory: {static_dir}")

EOF
    
    # Find the line number after the FastAPI app creation
    line_num=$(grep -n "app = FastAPI" main.py | head -1 | cut -d':' -f1)
    line_num=$((line_num + 1))
    
    # Insert the text after the app = FastAPI line
    sed -i "${line_num}r insert.txt" main.py
    
    # Remove temporary file
    rm insert.txt
fi

# Modify the twiml.py file to use the test endpoint
if [ -f "app/api/voice/twiml.py" ]; then
    log "Modifying twiml.py to use the test endpoint..."
    sed -i 's/websocket_url = f"{ws_scheme}:\/\/{host}\/realtime\/ws\/media\/{call_sid}"/websocket_url = f"{ws_scheme}:\/\/{host}\/ws-test\/{call_sid}"/g' app/api/voice/twiml.py
    
    # Add critical logging
    sed -i '/websocket_url = f"{ws_scheme}:\/\/{host}\/ws-test\/{call_sid}"/a \
        logging.critical(f"❗❗❗ USING SIMPLIFIED TEST WEBSOCKET URL: {websocket_url} ❗❗❗")' app/api/voice/twiml.py
fi

log "All WebSocket fixes applied. These changes should help with WebSocket connection issues on Render."
log "1. Uvicorn now uses a single worker, which should prevent connection routing issues"
log "2. A simple WebSocket test endpoint has been added directly to main.py"
log "3. TwiML generation now uses the simplified test endpoint instead of the complex path"
log "4. A browser-based test page has been created to help diagnose WebSocket issues"

# Make this script executable
chmod +x fix_websocket_uvicorn.sh

log "Fix script completed. Deploy these changes to Render to apply the fixes."