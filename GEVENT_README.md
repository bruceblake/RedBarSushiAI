# Flask-Sock with Gevent

This document explains the implementation of WebSockets in RedBarSushiAI using Flask-Sock with Gevent.

## The Correct Approach

After reviewing the Flask-Sock documentation, we've determined that Flask-Sock is designed to work natively with certain WSGI servers, particularly Gevent:

> Unlike other WebSocket packages for Gevent, this extension does not require the gevent-websocket package to be installed.

The key insight is that Flask-Sock has its own integration with Gevent and doesn't need (or expect) an ASGI server like Uvicorn.

## Implementation

We've made the following changes to align with the Flask-Sock recommended approach:

1. **Gevent Worker**: Using the Gevent worker class for Gunicorn as recommended by Flask-Sock:
   ```bash
   gunicorn -k gevent -w 4 --worker-connections 1000 "wsgi:app"
   ```

2. **Monkey Patching**: Added Gevent monkey patching in wsgi.py to make async-style code work with Gevent:
   ```python
   import gevent.monkey
   gevent.monkey.patch_all()
   ```

3. **Direct WSGI App**: Exporting the raw Flask app object instead of wrapping it with WsgiToAsgi:
   ```python
   # Export the Flask app directly for Gunicorn with gevent worker
   __all__ = ['app', 'application']
   ```

4. **Synchronous WebSocket Handlers**: Converted WebSocket handlers from asyncio style to gevent style:
   ```python
   # Instead of async/await code:
   @sock.route("/ws/media/<call_sid>")
   def handle_media_realtime(ws, call_sid):
       # Use synchronous ws.send() and ws.receive()
       # Use gevent.spawn() instead of asyncio.create_task()
       # Use gevent.sleep() instead of asyncio.sleep()
   ```

5. **External WebSocket Connections**: Using `websocket-client` library for connecting to external WebSocket APIs (like OpenAI):
   ```python
   import websocket  # gevent-compatible websocket-client
   
   ws = websocket.create_connection(url, header=headers)
   ws.send(json.dumps(message))
   response = ws.recv()
   ```

## Understanding Gevent Concurrency

Gevent provides concurrency through lightweight "greenlets" instead of asyncio coroutines:

1. **Greenlets**: Cooperative micro-threads that yield control rather than being preemptively scheduled.
2. **Monkey Patching**: Makes standard library I/O functions cooperative with Gevent.
3. **Event Loop**: Implicit event loop that switches between greenlets when they yield control.

Key differences from asyncio:

| asyncio | gevent |
|---------|--------|
| `async def func()` | `def func()` |
| `await asyncio.sleep(1)` | `gevent.sleep(1)` |
| `task = asyncio.create_task(func())` | `g = gevent.spawn(func)` |
| `await task` | `g.join()` |
| `asyncio.gather(task1, task2)` | `gevent.joinall([g1, g2])` |
| `asyncio.Queue()` | `gevent.queue.Queue()` |
| `asyncio.Event()` | `gevent.event.Event()` |

## Connection to OpenAI

For connecting to OpenAI's Realtime API, we now use a synchronous approach with gevent:

1. **SyncRealtimeAudioProcessor**: Added a synchronous version of the audio processor using gevent primitives.
2. **Websocket-client**: Replaced the asyncio-based `websockets` library with the gevent-compatible `websocket-client`.
3. **Greenlet-based Concurrency**: Using greenlets to handle bidirectional communication:
   - One greenlet for receiving messages from OpenAI
   - One greenlet for sending audio chunks
   - Main greenlet for processing events and yielding results
   - Inter-greenlet communication via queues and events

## Benefits of This Approach

1. **Matches Flask-Sock's Design**: This is how Flask-Sock was designed to be used.
2. **Simpler Architecture**: No need for ASGI/WSGI bridging with adapters.
3. **Better Performance**: Gevent is optimized for handling many concurrent connections.
4. **Stability**: Fewer moving parts means fewer potential points of failure.
5. **Compatibility**: Works with the broader Flask ecosystem that expects WSGI.

## Debugging WebSocket Issues

If WebSocket connections still fail, check:

1. **Monkey Patching**: Ensure `gevent.monkey.patch_all()` is called early in the application startup.
2. **WebSocket Route Registration**: Make sure `@sock.route("/ws/media/<call_sid>")` is registered correctly.
3. **Connection Handling**: Verify that the WebSocket handler is properly handling incoming connections.
4. **Dependencies**: Ensure `gevent` and `websocket-client` are installed.
5. **Logs**: Check the application logs for WebSocket-related errors.

## Comparison to Previous Approach

Our previous approach tried to use ASGI (Uvicorn) with WsgiToAsgi to bridge WSGI and ASGI. This created several issues:

1. **Incompatible Architectures**: WSGI and ASGI have fundamentally different approaches to handling connections.
2. **Scope Routing Issues**: WsgiToAsgi rejected WebSocket scopes with `ValueError: WSGI wrapper received a non-HTTP scope`.
3. **Middleware Confusion**: Flask-Sock's integration with Flask wasn't properly considered.
4. **RuntimeWarning: coroutine never awaited**: Asyncio coroutines weren't being correctly awaited in the WSGI environment.

The current Gevent-based approach aligns with Flask-Sock's intended usage and provides a more stable solution by:

1. Using the correct concurrency model for Flask-Sock (Gevent)
2. Eliminating the WSGI/ASGI compatibility layer
3. Properly handling WebSocket connections with gevent primitives
4. Using libraries that are compatible with the gevent concurrency model