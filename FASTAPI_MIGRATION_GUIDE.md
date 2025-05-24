# FastAPI Migration Guide

This document outlines the migration from Flask to FastAPI for the RedBarSushiAI project.

## Migration Status: ✅ COMPLETE

The codebase has been successfully migrated to use FastAPI for all WebSocket and API endpoints.

## Key Changes Made

### 1. Removed Flask Voice Routes
- Deleted `app/routes/voice/` directory (entire Flask voice implementation)
- Deleted `app/routes/voice.py` (Flask voice entry point)

### 2. Updated to FastAPI Implementation
- **WebSocket Handler**: `app/api/voice_async.py` - Main WebSocket handler for Twilio media streams
- **TwiML Generation**: `app/api/voice/twiml.py` - Generates TwiML for Twilio webhooks
- **Realtime Audio**: `app/utils/realtime_audio_async.py` - OpenAI Realtime API client
- **Agent System**: All agents use async patterns (`*_async.py` files)

### 3. WebSocket Routes
- **Twilio Webhook**: `POST /voice/` and `POST /voice/webhook`
- **WebSocket Endpoint**: `wss://[host]/realtime/ws/media/{call_sid}`
- **Health Check**: `GET /health`
- **Routes Debug**: `GET /routes-debug`

### 4. Deployment Configuration Updates

#### Updated Files:
- **Procfile**: Now uses `uvicorn main:app` instead of `gunicorn run:app`
- **Dockerfile**: Already configured with `CMD ["uvicorn", "main:app", ...]`
- **render-fastapi.yaml**: New configuration file for Render deployment with FastAPI

#### To Deploy:
1. For staging: Use Docker build (already configured)
2. For production: Update render.yaml to use FastAPI configuration:
   ```yaml
   startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT --workers 4 --log-level info
   ```

## Architecture Overview

### WebSocket Flow:
1. Twilio calls webhook at `/voice/`
2. TwiML generated with WebSocket URL: `/realtime/ws/media/{call_sid}`
3. Twilio connects to WebSocket endpoint
4. FastAPI WebSocket handler manages connection
5. Audio forwarded to OpenAI Realtime API
6. Responses streamed back through WebSocket to Twilio

### Key Components:
- **FastAPI App**: `app/main.py` and root `main.py`
- **API Router**: `app/api/__init__.py` - Includes all API routes
- **Voice Module**: `app/api/voice/` - Structured voice implementation
- **Async Utilities**: All utilities use async/await patterns

## Testing the Implementation

### Local Testing:
```bash
# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health

# Test routes listing
curl http://localhost:8000/routes-debug
```

### WebSocket Testing:
Use the WebSocket test page at `/ws-test-page` or access directly at `/static/websocket-test.html`

## Benefits of FastAPI

1. **Native WebSocket Support**: Better WebSocket handling than Flask-SocketIO
2. **Async/Await**: True asynchronous processing for better performance
3. **Type Hints**: Better code documentation and IDE support
4. **Automatic API Documentation**: Available at `/docs` and `/redoc`
5. **Better Performance**: Faster request handling and lower latency

## Rollback Plan

If issues arise, the Flask implementation can be restored by:
1. Reverting the Procfile to use `gunicorn run:app`
2. Restoring Flask voice routes from git history
3. Using the original render.yaml configuration

However, the FastAPI implementation has been thoroughly tested and is production-ready.

## Next Steps

1. Monitor WebSocket connections in production
2. Optimize worker count based on load
3. Consider adding more async background tasks
4. Implement additional FastAPI features (middleware, dependencies, etc.)

## Support

For questions or issues with the FastAPI implementation:
- Check logs: `docker logs -f redbarsushi-app`
- Debug routes: Visit `/routes-debug`
- Test WebSocket: Use `/ws-test-page`
- Review this guide and CLAUDE.md for architecture details