# run.py
import os
import sys
import time
import logging
from flask import Flask, jsonify

# Configure basic logging
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run")

# System information
logger.info(f"Starting app in {os.getcwd()}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Python path: {sys.executable}")
logger.info(f"Environment: {os.environ.get('DOCKER', 'local')}")

# Set up a dummy app in case the main app fails to load
def create_fallback_app(error_message):
    fallback = Flask(__name__)
    
    @fallback.route('/')
    def index():
        return jsonify({
            "status": "error",
            "message": "Application failed to initialize properly",
            "error": error_message
        }), 500
        
    @fallback.route('/healthcheck')
    def healthcheck():
        return jsonify({
            "status": "error",
            "message": "Application in fallback mode",
            "error": error_message
        }), 500
        
    @fallback.route('/voice', methods=['GET', 'POST'])
    def voice_fallback():
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say("We're sorry, our system is currently experiencing technical difficulties. Please try again later.")
        response.hangup()
        return str(response)
        
    return fallback

# Create the Flask application with retry logic
max_retries = 3
retry_count = 0
retry_delay = 2
last_error = None

while retry_count < max_retries:
    try:
        from app import create_app
        app = create_app()
        logger.info(f"Application created successfully on attempt {retry_count + 1}")
        break
    except Exception as e:
        last_error = str(e)
        retry_count += 1
        logger.error(f"ERROR creating application (attempt {retry_count}/{max_retries}): {e}")
        if retry_count < max_retries:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            logger.error("Maximum retries reached, creating fallback app")
            app = create_fallback_app(str(e))

# Add a simple route to test basic functionality
@app.route('/hello')
def hello():
    return {"message": "Hello from RedBarSushiAI\!"}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
