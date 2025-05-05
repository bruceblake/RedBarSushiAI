# WebSocket Connection Fixes for RedBarSushiAI

## Issue History

### Initial Issue: Route Registration

The application initially experienced 404 errors when Twilio tried to connect to the WebSocket endpoint:

```
Error: WebSocket connection to 'wss://redbarsushiai-staging.onrender.com/ws/voice/media' failed: HTTP Authentication failed; no valid credentials available
```

The root cause was that the WebSocket routes were not being properly registered with Flask's URL map because of incorrect route decorators:

```python
@sock.route("/ws/voice/media", websocket=True)
async def media_stream(ws):
    # ...
```

The `websocket=True` parameter is not a valid parameter for Flask-Sock's route decorator. This parameter was causing the route to be improperly registered.

### Initial Fix

The initial solution was to remove the invalid `websocket=True` parameter from the route decorators:

```python
@sock.route("/ws/voice/media")
async def media_stream(ws):
    # ...
```

After making this change, the WebSocket routes were properly registered with Flask's URL map, and Twilio was able to connect to the WebSocket endpoint.

## Current Issue: Premature WebSocket Disconnection

After fixing the route registration, the system connected but experienced WebSocket disconnection immediately after the greeting:

```
[SILENCE:CA...] Error sending keep-alive: received 1005 (no status received [internal]); then sent 1005 (no status received [internal])
```

The logs showed successful TwiML generation and initial WebSocket connections, but the connections would close immediately after the greeting, causing calls to hang up.

## Root Causes

Multiple issues were identified:

1. **Insufficient Worker Configuration**: Gunicorn was configured with only 2 worker processes (`-w 2`), which couldn't handle multiple concurrent WebSocket connections.

2. **Unhandled Task Garbage Collection**: WebSocket tasks were being garbage collected because they weren't tracked in a persistent collection.

3. **Insufficient Connection Keep-Alive**: Not enough keep-alive messages were being sent after the greeting.

4. **Insufficient Timing Delays**: The TwiML lacked adequate pauses between connection steps.

5. **WebSocket Message Format Issues**: Some message formats weren't compatible with Twilio Media Streams.

## Implemented Fixes

### 1. Gunicorn Worker Configuration

Updated Procfile to increase workers and connection timeout:

```diff
- web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 --bind 0.0.0.0:$PORT --timeout 120 'run:app'
+ web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 'run:app'
```

### 2. WebSocket Route Enhancement

Enhanced the WebSocket route handler to establish and maintain connections:

```python
@sock.route("/ws/voice/media")
@websocket_handler
async def media_stream_ws(ws):
    """WebSocket endpoint for Twilio Media Streams API."""
    # Log critical connection information
    logger.critical(f"[MEDIA_STREAM] WebSocket connection established")
    
    try:
        # Send welcome and heartbeat messages immediately
        welcome_msg = json.dumps({
            "type": "connected", 
            "message": "WebSocket connection established",
            "timestamp": time.time(),
            "session_id": getattr(ws, '_log_id', 'unknown')
        })
        await ws.send(welcome_msg)
        # ...additional heartbeat messages...
    except Exception as e:
        logger.critical(f"[MEDIA_STREAM] Error sending initial messages: {e}")
    
    # Now proceed with regular handling
    await handle_media_stream(ws)
```

### 3. Improved TwiML Generation

Enhanced the TwiML generation with pauses and clear stream naming:

```python
# Add pauses to ensure TTS completes and connection is ready
response.pause(length=1)

# Start Media Stream with separate naming
start = Start()
start.stream(url=ws_url_inbound, track="inbound_track", name="inbound_stream")
response.append(start)

# Add another pause for connection stabilization
response.pause(length=0.5)

# Connect bidirectional audio stream
connect = Connect()
connect.stream(url=ws_url_both, track="both_tracks", name="both_tracks_stream")
response.append(connect)
```

### 4. Multiple Keep-Alive Messages After Greeting

Implemented multiple keep-alive messages after greeting:

```python
# Send 5 keep-alive messages with short intervals
for i in range(5):
    keep_alive = {
        "type": "connection_keep_alive", 
        "message": f"Keeping connection alive after greeting ({i+1}/5)",
        "timestamp": silence_timestamp + i*0.2,
        "session_id": session_id
    }
    try:
        await asyncio.sleep(0.2)
        await ws.send(json.dumps(keep_alive))
        # ...
    except Exception as ka_error:
        # Fallback mechanism
        # ...
```

### 5. Improved Follow-up Mechanism

Enhanced the follow-up prompt with additional keep-alive messages:

```python
# Send keep-alive messages before, during, and after the follow-up prompt
# to maintain connection throughout the critical post-greeting period
```

### 6. Task Tracking for Garbage Collection Prevention

Added persistent task tracking:

```python
# Add task to a global set to prevent it from being garbage collected
if not hasattr(asyncio, '_keepalive_tasks'):
    asyncio._keepalive_tasks = set()
asyncio._keepalive_tasks.add(keepalive_task)

# Set up a callback to remove the task when it's done
def cleanup_task(task):
    asyncio._keepalive_tasks.discard(task)
    
keepalive_task.add_done_callback(cleanup_task)
```

## Lessons Learned

1. WebSocket connections need frequent keep-alive messages to stay active
2. Pauses in TwiML are essential for proper connection establishment
3. Garbage collection can unexpectedly terminate asyncio tasks
4. Gunicorn worker configuration is critical for WebSocket applications
5. Detailed logging is essential for troubleshooting WebSocket issues
6. Multiple messages in quick succession help maintain WebSocket connections

## Resources

- [Flask-Sock Documentation](https://flask-sock.readthedocs.io/en/latest/quickstart.html)
- [Twilio Media Streams Documentation](https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask)
- [Gunicorn Worker Configuration](https://docs.gunicorn.org/en/latest/design.html#how-many-workers)
- [GeventWebSocket Documentation](https://gitlab.com/noppo/gevent-websocket)
