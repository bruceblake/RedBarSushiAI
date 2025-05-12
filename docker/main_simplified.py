"""Simplified main entry point to help diagnose startup issues."""

import os
import logging
import sys

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

logger = logging.getLogger("startup_debug")
logger.setLevel(logging.DEBUG)

# Set environment variables
os.environ["BASE_URL"] = os.environ.get("BASE_URL", "https://redbarsushiai.onrender.com")
os.environ["PYNPUT_HEADLESS"] = "1"
os.environ["HEADLESS"] = "1"
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

logger.debug("Starting simplified diagnostic app")

# Try to import key modules
try:
    from fastapi import FastAPI
    logger.debug("Successfully imported FastAPI")
except ImportError as e:
    logger.error(f"Failed to import FastAPI: {e}")
    sys.exit(1)

# Create FastAPI application
app = FastAPI(title="RedBarSushiAI Diagnostic", version="1.0.0")

# Test pydantic import
try:
    import pydantic
    logger.debug(f"Pydantic version: {pydantic.__version__}")
    
    # For v2, try importing BaseSettings from pydantic_settings
    if pydantic.__version__.startswith("2."):
        try:
            from pydantic_settings import BaseSettings
            logger.debug("Successfully imported BaseSettings from pydantic_settings")
        except ImportError as e:
            logger.error(f"Failed to import BaseSettings from pydantic_settings: {e}")
except ImportError as e:
    logger.error(f"Failed to import pydantic: {e}")

@app.get("/")
async def root():
    return {"message": "Diagnostic app running"}

@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}

# Simple WebSocket test
@app.websocket("/ws-test/{client_id}")
async def websocket_test(websocket, client_id: str):
    logger.debug(f"WebSocket connection attempted: {client_id}")
    await websocket.accept()
    await websocket.send_text(f"Hello, {client_id}!")
    await websocket.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main_simplified:app", host="0.0.0.0", port=port)