#!/bin/bash
# Script to start RedBarSushiAI application in various modes

# Default configuration
PORT=${PORT:-8080}
MODE=${MODE:-dev}
VOICE_HANDLER=${VOICE_HANDLER:-realtime}
FORCE_HEADLESS=${FORCE_HEADLESS:-true}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --port) PORT="$2"; shift ;;
        --mode) MODE="$2"; shift ;;
        --headless) FORCE_HEADLESS="$2"; shift ;;
        --voice) VOICE_HANDLER="$2"; shift ;;
        --help) 
            echo "Usage: ./start.sh [options]"
            echo "Options:"
            echo "  --port <port>       Port to run on (default: 8080)"
            echo "  --mode <mode>       Mode to run in (dev, prod, debug) (default: dev)"
            echo "  --headless <bool>   Run in headless mode (default: true)"
            echo "  --voice <handler>   Voice handler to use (realtime) (default: realtime)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Export environment variables
export PORT=$PORT
export VOICE_HANDLER=$VOICE_HANDLER
export FORCE_HEADLESS=$FORCE_HEADLESS
export OPENAI_REALTIME_NO_DISPLAY=1

# Create logs directory if it doesn't exist
mkdir -p logs
mkdir -p logs/voice
mkdir -p logs/stream
mkdir -p logs/database
mkdir -p logs/websocket

echo "Starting RedBarSushiAI in $MODE mode on port $PORT"
echo "Voice handler: $VOICE_HANDLER"
echo "Headless mode: $FORCE_HEADLESS"

# Run the application in the specified mode
case $MODE in
    dev)
        echo "Starting in development mode with auto-reload"
        export FLASK_APP=run.py
        export FLASK_DEBUG=1
        flask run --host=0.0.0.0 --port=$PORT
        ;;
    prod)
        echo "Starting in production mode with Gunicorn"
        gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 --bind "0.0.0.0:$PORT" "run:app"
        ;;
    debug)
        echo "Starting in debug mode with verbose logging"
        export FLASK_APP=run.py
        export FLASK_DEBUG=1
        export LOG_LEVEL=DEBUG
        flask run --host=0.0.0.0 --port=$PORT
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Use one of: dev, prod, debug"
        exit 1
        ;;
esac