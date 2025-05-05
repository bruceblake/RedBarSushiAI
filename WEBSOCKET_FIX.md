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

1. **Route Registration Conflict**: Multiple instances of the same WebSocket route were being registered, causing route conflicts with the error message: "View function mapping is overwriting an existing endpoint function: media_stream_ws"

2. **Insufficient Worker Configuration**: Gunicorn was configured with insufficient worker parameters. Worker processes were being terminated by SIGTERM signals (appearing in logs as `[2025-05-05 21:42:20 +0000] [1] [INFO] Handling signal: term`).

3. **Unhandled Task Garbage Collection**: WebSocket tasks were being garbage collected because they weren't tracked in a persistent collection.

4. **Insufficient Connection Keep-Alive**: Not enough keep-alive messages were being sent after the greeting.

5. **Insufficient Timing Delays**: The TwiML lacked adequate pauses between connection steps.

6. **WebSocket Message Format Issues**: Some message formats weren't compatible with Twilio Media Streams.

## Implemented Fixes

### 1. Gunicorn Worker Configuration

Updated Procfile with graceful shutdown parameters to prevent abrupt worker termination:

```diff
- web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 --bind 0.0.0.0:$PORT --timeout 120 'run:app'
+ web: FLASK_SKIP_DOTENV=1 WEB_CONCURRENCY=4 gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 --graceful-timeout 60 --max-requests 200 --max-requests-jitter 50 'run:app'
```

Key improvements:
- Increased worker count from 2 to 4
- Added environment variable `WEB_CONCURRENCY=4` to ensure consistent worker count
- Added `--graceful-timeout 60` to allow 60 seconds for connections to complete before worker termination
- Added `--max-requests 200 --max-requests-jitter 50` to gracefully recycle workers and prevent memory issues

### 2. Route Registration Conflict Resolution

Enhanced the WebSocket route registration check to prevent duplicate route registration:

```python
# Old check that only looked at route paths
if "/ws/voice/media" not in existing_routes:
    @sock.route("/ws/voice/media")
    @websocket_handler
    async def media_stream_ws(ws):
        # ...

# New improved check that also looks at function names
existing_funcs = [f.__name__ for f in sock._rules.values()] if hasattr(sock, '_rules') else []

if "/ws/voice/media" not in existing_routes and "media_stream_ws" not in existing_funcs:
    @sock.route("/ws/voice/media")
    @websocket_handler
    async def media_stream_ws(ws):
        # ...
```

This prevents the "View function mapping is overwriting an existing endpoint function" error.

### 3. WebSocket Route Enhancement

Enhanced the WebSocket route handler to establish and maintain connections:

```python
@sock.route("/ws/voice/media")
@websocket_handler
async def media_stream_ws(ws):
    """WebSocket endpoint for Twilio Media Streams API."""
    # Log critical connection information
    logger.critical(f"[MEDIA_STREAM] WebSocket connection established to /ws/voice/media")
    logger.critical(f"[MEDIA_STREAM] Connection ID: {getattr(ws, '_log_id', 'unknown')}")
    
    # Get request info if available
    if hasattr(ws, 'request') and hasattr(ws.request, 'headers'):
        headers = ws.request.headers
        logger.critical(f"[MEDIA_STREAM] Headers: {headers}")
        # Check if this is a Twilio connection
        user_agent = headers.get('User-Agent', '')
        is_twilio = 'twilio' in user_agent.lower()
        logger.critical(f"[MEDIA_STREAM] User-Agent: {user_agent}")
        logger.critical(f"[MEDIA_STREAM] Is Twilio: {is_twilio}")
    
    # Set a session attribute for tracking in logs
    session_id = getattr(ws, '_log_id', str(time.time()))
    
    try:
        # Send a welcome message to establish the connection
        welcome_msg = json.dumps({
            "type": "connected", 
            "message": "WebSocket connection established",
            "timestamp": time.time(),
            "session_id": session_id
        })
        await ws.send(welcome_msg)
        logger.critical(f"[MEDIA_STREAM] Sent welcome message")
        
        # Add a brief delay
        await asyncio.sleep(0.2)
        
        # Send a test heartbeat message
        heartbeat_msg = json.dumps({
            "type": "heartbeat", 
            "message": "Initial heartbeat to maintain connection",
            "timestamp": time.time(),
            "session_id": session_id
        })
        await ws.send(heartbeat_msg)
        logger.critical(f"[MEDIA_STREAM] Sent initial heartbeat")
        
        # Wait a moment before starting the media stream handler
        # This ensures the connection is fully established
        await asyncio.sleep(0.2)
    except Exception as e:
        logger.critical(f"[MEDIA_STREAM] Error sending initial messages: {e}")
        logger.critical(traceback.format_exc())
    
    # Now proceed with regular handling
    await handle_media_stream(ws)
```

### 4. Improved TwiML Generation

Enhanced the TwiML generation with pauses and clear stream naming:

```python
# Add a 1-second pause to ensure TTS completes and connection is ready
response.pause(length=1)

# Start Media Stream with the WebSocket endpoint using a separate endpoint for inbound
ws_url_inbound = f"wss://{hostname}/ws/voice/media"
logger.info(f"[TWIML:{call_sid}] Adding Media Stream start with URL: {ws_url_inbound}, track: inbound_track")
start = Start()
start.stream(url=ws_url_inbound, track="inbound_track", name="inbound_stream")
response.append(start)

# Add another small pause to ensure the first connection is established
response.pause(length=0.5)

# Connect bidirectional audio stream with parameters to improve stability
ws_url_both = f"wss://{hostname}/ws/voice/media"
logger.info(f"[TWIML:{call_sid}] Adding Media Stream connect with URL: {ws_url_both}, track: both_tracks")
connect = Connect()
connect.stream(url=ws_url_both, track="both_tracks", name="both_tracks_stream")
response.append(connect)
```

### 5. Multiple Keep-Alive Messages After Greeting

Implemented multiple sequential keep-alive messages after greeting:

```python
# Send multiple keep-alive messages after greeting to maintain connection
logger.critical(f"[SILENCE:{session_id}] Sending multiple keep-alive messages after greeting")
for i in range(5):  # Send 5 keep-alive messages with short intervals
    keep_alive = {
        "type": "connection_keep_alive", 
        "message": f"Keeping connection alive after greeting ({i+1}/5)",
        "timestamp": silence_timestamp + i*0.2,
        "session_id": session_id
    }
    try:
        await asyncio.sleep(0.2)  # Small delay between messages
        await ws.send(json.dumps(keep_alive))
        metrics["events_sent"] += 1
        logger.critical(f"[SILENCE:{session_id}] ✅ Sent keep-alive #{i+1} after greeting")
    except Exception as ka_error:
        logger.critical(f"[SILENCE:{session_id}] ❌ Error sending keep-alive #{i+1}: {ka_error}")
        # Try an alternative format
        try:
            alt_keep_alive = {
                "event": "ping", 
                "message": f"Keep-alive ping #{i+1}",
                "timestamp": time.time()
            }
            await ws.send(json.dumps(alt_keep_alive))
            logger.critical(f"[SILENCE:{session_id}] ✅ Sent alternative keep-alive #{i+1}")
        except Exception as alt_error:
            logger.critical(f"[SILENCE:{session_id}] ❌ Alternative also failed: {alt_error}")

# Log completion of keep-alive sequence
logger.critical(f"[SILENCE:{session_id}] ✅ Completed keep-alive sequence after greeting")
```

### 6. Enhanced Silence Handling

Improved silence handling with multiple keep-alive messages:

```python
# During periods of silence in conversation
try:
    # Send multiple keep-alive messages to ensure connection stays open
    for i in range(3):
        keep_alive = {
            "type": "silence_keep_alive", 
            "message": f"Keeping connection alive during silence in {current_state} state ({i+1}/3)",
            "timestamp": silence_timestamp + (i * 0.2),
            "session_id": session_id,
            "state": str(current_state)
        }
        await ws.send(json.dumps(keep_alive))
        metrics["events_sent"] += 1
        logger.critical(f"[SILENCE:{session_id}] Sent silence keep-alive #{i+1} in {current_state} state")
        await asyncio.sleep(0.2)  # Small delay between keep-alives
except Exception as ka_error:
    logger.critical(f"[SILENCE:{session_id}] Error sending silence keep-alive: {ka_error}")
    # Fallback mechanism with alternative format
    # ...
```

### 7. Enhanced Follow-up Mechanism

Improved follow-up prompt strategy with extensive keep-alive messaging:

```python
async def send_followup_prompt(ws, session_id, frontline, timestamp, metrics, delay=3.0):
    """Send a follow-up prompt after the greeting to maintain engagement."""
    try:
        # First send a keep-alive message
        initial_keep_alive = {
            "type": "followup_keep_alive",
            "message": "Pre-followup keep-alive",
            "timestamp": time.time(),
            "session_id": session_id
        }
        try:
            await ws.send(json.dumps(initial_keep_alive))
            logger.critical(f"[SILENCE:{session_id}] ✅ Sent pre-followup keep-alive message")
        except Exception as pre_error:
            logger.critical(f"[SILENCE:{session_id}] ❌ Error sending pre-followup keep-alive: {pre_error}")
        
        # Wait for the specified delay (reduced from 5.0 to 3.0 seconds)
        await asyncio.sleep(delay)
        
        # Send immediate keep-alive before sending the actual prompt
        pre_prompt_ka = {
            "type": "pre_prompt_keep_alive",
            "timestamp": time.time(),
            "session_id": session_id
        }
        try:
            await ws.send(json.dumps(pre_prompt_ka))
            logger.critical(f"[SILENCE:{session_id}] ✅ Sent pre-prompt keep-alive")
        except Exception as e:
            logger.critical(f"[SILENCE:{session_id}] ❌ Error sending pre-prompt keep-alive: {e}")
        
        # Send the follow-up prompt
        followup_message = {
            "event": "agent_response",
            "text": followup,
            "timestamp": time.time(),
            "is_followup": True,
            "after_greeting": True
        }
        await ws.send(json.dumps(followup_message))
        metrics["events_sent"] += 1
        
        # Schedule additional keep-alive messages after the prompt
        for i in range(3):
            try:
                await asyncio.sleep(0.5)
                post_prompt_ka = {
                    "type": "post_prompt_keep_alive",
                    "index": i + 1,
                    "timestamp": time.time(),
                    "session_id": session_id
                }
                await ws.send(json.dumps(post_prompt_ka))
                logger.critical(f"[SILENCE:{session_id}] ✅ Sent post-prompt keep-alive #{i+1}")
            except Exception as e:
                logger.critical(f"[SILENCE:{session_id}] ❌ Error sending post-prompt keep-alive #{i+1}: {e}")
    except Exception as e:
        logger.error(f"[SILENCE:{session_id}] Error sending follow-up prompt: {e}")
```

### 8. Task Tracking for Garbage Collection Prevention

Added persistent task tracking:

```python
# Add task to a global set to prevent it from being garbage collected
if not hasattr(asyncio, '_keepalive_tasks'):
    asyncio._keepalive_tasks = set()
asyncio._keepalive_tasks.add(task)

# Set up a callback to remove the task when it's done
def cleanup_task(task):
    asyncio._keepalive_tasks.discard(task)
    
task.add_done_callback(cleanup_task)
```

## Testing Tools

Two new testing tools have been created to verify the WebSocket fixes:

1. **WebSocket Stability Fix Script** (`fix_worker_termination.py`):
   - Updates Procfile with graceful shutdown parameters
   - Enhances WebSocket route registration check
   - Improves keep-alive messaging strategy
   - Adds critical logging for diagnosing connection issues

2. **WebSocket Stability Test** (`test_websocket_stability.py`):
   - Tests WebSocket connection stability over an extended period
   - Specifically monitors the post-greeting phase where disconnections occur
   - Provides detailed metrics and reporting on connection stability
   - Can be used to validate fixes in the staging environment

## Lessons Learned

1. **Worker Process Management**: Gunicorn worker processes need graceful shutdown parameters to prevent WebSocket connections from being terminated abruptly.

2. **Route Registration**: WebSocket routes should be checked for both path conflicts and function name conflicts to prevent duplicate registrations.

3. **Multiple Keep-Alive Messages**: A single keep-alive message is insufficient; multiple sequential messages with short delays are required at critical points in the conversation.

4. **Strategic Pauses in TwiML**: Pauses between stream connections in TwiML are essential for proper connection establishment.

5. **Garbage Collection**: Asyncio tasks can be unexpectedly terminated by garbage collection if not tracked.

6. **Enhanced Logging**: Critical-level logging with detailed connection information is essential for troubleshooting WebSocket issues.

7. **Multiple Messages in Quick Succession**: Sending multiple messages in quick succession helps maintain WebSocket connections during periods of silence.

## Resources

- [Flask-Sock Documentation](https://flask-sock.readthedocs.io/en/latest/quickstart.html)
- [Twilio Media Streams Documentation](https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask)
- [Gunicorn Worker Configuration](https://docs.gunicorn.org/en/latest/design.html#how-many-workers)
- [GeventWebSocket Documentation](https://gitlab.com/noppo/gevent-websocket)
- [Gunicorn Settings Documentation](https://docs.gunicorn.org/en/latest/settings.html#graceful-timeout)