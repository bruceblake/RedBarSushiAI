# Voice Routes Refactoring

This directory contains the refactored voice integration for RedBarSushiAI. The refactoring breaks down the large `voice_orchestrated_realtime.py` file into a more modular and maintainable structure.

## Directory Structure

```
app/routes/voice/
├── __init__.py                  # Package initialization and WebSocket routes
├── blueprints.py                # Blueprint definitions
├── main.py                      # Main integration point
├── routes.py                    # HTTP route definitions
├── handlers/                    # Event handlers
│   ├── __init__.py              # Handler exports
│   ├── audio.py                 # Audio event handler
│   ├── silence.py               # Silence event handler
│   ├── tools.py                 # Tool call handler
│   └── transcript.py            # Transcript handler
├── realtime/                    # Realtime API integration
│   ├── __init__.py              # Module exports
│   ├── audio_generator.py       # Audio generator for streaming
│   └── stream_handler.py        # WebSocket handler
├── twilio/                      # Twilio integration
│   ├── __init__.py              # Module exports
│   └── twiml.py                 # TwiML generation
└── utils/                       # Voice-specific utilities
    ├── __init__.py              # Utility exports
    ├── tools_registry.py        # Tool registration
    └── vad.py                   # Voice activity detection configuration
```

## Integration with Existing Code

For backward compatibility, the `app/routes/voice_refactored.py` file exports the same blueprint as the original `voice_orchestrated_realtime.py` file with the name `realtime_voice_bp`. This allows existing code to continue referencing the same blueprint.

## Main Improvements

1. **Modularity**: Functionality is broken down into logical components
2. **Maintainability**: Each file has a single responsibility
3. **File Size**: No file exceeds 500 lines as required
4. **Error Handling**: Enhanced error handling and diagnostics
5. **Code Organization**: Clearer separation of concerns

## Usage

To use the refactored voice system, update your app initialization to include:

```python
from app.routes.voice_refactored import init_voice_system, realtime_voice_bp

# Initialize the voice system
init_voice_system(app)
```

## WebSocket Endpoints

The system provides the following WebSocket endpoints:

- `/ws/voice/media`: Main endpoint for Twilio Media Streams
- `/ws/voice/debug`: Debug endpoint for WebSocket connectivity testing

## HTTP Endpoints

The system provides the following HTTP endpoints:

- `/voice/realtime/`: Main endpoint for handling Twilio webhook requests
- `/voice/debug/health`: Health check endpoint for the voice system