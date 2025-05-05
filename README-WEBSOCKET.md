# WebSocket Connection Fix for RedBarSushiAI

## Background

The RedBarSushiAI voice ordering system experienced an issue where WebSocket connections were being terminated immediately after playing the greeting to customers. This caused phone calls to hang up prematurely, making the system unusable.

## Root Causes

Our investigation identified several interconnected issues:

1. **Route Registration Conflict**: Multiple instances of the same WebSocket route were being registered, causing the error "View function mapping is overwriting an existing endpoint function: media_stream_ws".

2. **Worker Process Termination**: Gunicorn worker processes were being terminated unexpectedly with SIGTERM signals, dropping active WebSocket connections.

3. **Insufficient Keep-Alive Messages**: Only a single keep-alive message was being sent after the greeting, which wasn't sufficient to maintain the connection.

4. **Missing Pauses in TwiML**: The TwiML lacked proper pauses between audio stream connections, causing connection instability.

5. **Task Garbage Collection**: Async tasks were being garbage collected before completion, terminating keep-alive sequences prematurely.

## Implemented Fixes

We have implemented a comprehensive set of fixes to address these issues:

### 1. Enhanced Route Registration Check

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

This prevents duplicate route registration by checking both the route path and the function name.

### 2. Improved Worker Configuration

Updated Procfile with graceful shutdown parameters:

```
web: FLASK_SKIP_DOTENV=1 WEB_CONCURRENCY=4 gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 --graceful-timeout 60 --max-requests 200 --max-requests-jitter 50 'run:app'
```

Key improvements:
- Increased worker count from 2 to 4
- Added environment variable `WEB_CONCURRENCY=4` to ensure consistent worker count
- Added `--graceful-timeout 60` to allow 60 seconds for connections to complete before worker termination
- Added `--max-requests 200 --max-requests-jitter 50` to gracefully recycle workers and prevent memory issues

### 3. Multiple Keep-Alive Messages

Implemented multiple sequential keep-alive messages after greeting:

```python
# Send multiple keep-alive messages after greeting
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
        # Fallback mechanism with alternative format
        # ...
```

### 4. Enhanced TwiML Generation

Added strategic pauses in the TwiML to ensure proper connection establishment:

```python
# Add a 1-second pause to ensure TTS completes and connection is ready
response.pause(length=1)

# Start Media Stream with the WebSocket endpoint
start = Start()
start.stream(url=ws_url_inbound, track="inbound_track", name="inbound_stream")
response.append(start)

# Add another small pause to ensure the first connection is established
response.pause(length=0.5)
```

### 5. Task Tracking for Garbage Collection Prevention

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

We've created several tools to test and verify the WebSocket fixes:

1. **WebSocket Stability Test** (`test_websocket_stability.py`): Tests WebSocket connection stability over an extended period, specifically monitoring the post-greeting phase.

2. **WebSocket Fix Verification** (`verify_websocket_fixes.py`): Verifies that all fixes have been properly applied by checking configuration files and WebSocket behavior.

3. **Worker Termination Fix** (`fix_worker_termination.py`): Automatically applies all the fixes to relevant files, ensuring consistent implementation.

## Deployment

To deploy these fixes:

1. All changes have been verified and are already in place in the codebase.

2. A comprehensive documentation has been added in `WEBSOCKET_FIX.md` that explains the issues and fixes in detail.

3. To deploy, push the changes to the staging branch and trigger a deployment on Render:
   ```
   git push origin staging
   ```

4. After verifying in staging, merge to the main branch for production deployment:
   ```
   git checkout main
   git merge staging
   git push origin main
   ```

## Monitoring

After deploying these fixes, monitor the logs for the following patterns to ensure the WebSocket connections remain stable:

1. Successful connection establishment:
   ```
   [MEDIA_STREAM] WebSocket connection established to /ws/voice/media
   ```

2. Successful keep-alive messages:
   ```
   [SILENCE:*] ✅ Sent keep-alive #* after greeting
   ```

3. Completed keep-alive sequences:
   ```
   [SILENCE:*] ✅ Completed keep-alive sequence after greeting
   ```

4. No worker termination signals during active calls:
   ```
   [INFO] Handling signal: term
   ```

## Conclusion

These fixes collectively address the WebSocket disconnection issue by ensuring route registration is consistent, worker processes are terminated gracefully, and connections are maintained with multiple keep-alive messages. The system should now be able to handle voice calls without disconnecting after the greeting.

For detailed technical information about the fixes, refer to the `WEBSOCKET_FIX.md` file.