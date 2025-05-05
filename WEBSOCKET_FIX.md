# WebSocket Route Registration Fix

## The Issue

The application was experiencing 404 errors when Twilio tried to connect to the WebSocket endpoint:

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

## The Fix

The solution was to remove the invalid `websocket=True` parameter from the route decorators:

```python
@sock.route("/ws/voice/media")
async def media_stream(ws):
    # ...
```

## Verification

After making this change, the WebSocket routes were properly registered with Flask's URL map, and Twilio was able to connect to the WebSocket endpoint.

## Lessons Learned

1. Flask-Sock has a different API than Flask-SocketIO - they are not interchangeable
2. Always check library documentation for the correct API usage
3. When routes aren't appearing in the route list, check the decorator syntax
4. For WebSocket issues, implement test endpoints to verify connectivity

## Resources

- [Flask-Sock Documentation](https://flask-sock.readthedocs.io/en/latest/quickstart.html)
- [Twilio Media Streams Documentation](https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask)
