# Voice System Architecture

This directory contains the voice integration for RedBarSushiAI. The architecture is modular with clear separation of concerns, ensuring maintainability and performance.

## Directory Structure

```
app/routes/voice/
├── __init__.py                  # Package initialization and component registry
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
    ├── tools_registry.py        # Tool registration and execution
    └── vad.py                   # Voice activity detection configuration
```

## Integration with Main App

The `app/routes/voice.py` file serves as the entry point for integration with the Flask application. It exports the `realtime_voice_bp` blueprint and the `init_voice_system` function.

## Key Features

1. **Component Registry**: Global registry for sharing components between modules
2. **WebSocket Handling**: Real-time audio processing with Twilio Media Streams
3. **Agent Orchestration**: Multi-agent architecture with specialized roles
4. **Tool Registry**: Centralized registration and execution of OpenAI tools
5. **TwiML Generation**: Dynamic TwiML generation for Twilio responses
6. **VAD Configuration**: Configurable voice activity detection settings

## Usage

To use the voice system in a Flask application:

```python
from app.routes.voice import init_voice_system, realtime_voice_bp

# Initialize the voice system
init_voice_system(app)

# Register the blueprint
app.register_blueprint(realtime_voice_bp)
```

## WebSocket Endpoints

The system provides the following WebSocket endpoints:

- `/ws/voice/media`: Main endpoint for Twilio Media Streams
- `/ws/voice/debug`: Debug endpoint for WebSocket connectivity testing

## HTTP Endpoints

The system provides the following HTTP endpoints:

- `/voice/realtime/`: Main endpoint for handling Twilio webhook requests
- `/voice/debug/health`: Health check endpoint for the voice system