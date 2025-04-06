# wsgi.py - Entry point for WSGI servers with error handling
import os
import sys
import logging

# Configure basic logging
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("wsgi")

try:
    # Try to import the Flask app
    logger.info("Initializing application...")
    from run import app as application
    logger.info("Application initialized successfully")
    
    # Add basic health check
    @application.route('/wsgi-healthcheck')
    def wsgi_healthcheck():
        return {"status": "ok", "message": "WSGI application is running"}
        
except ImportError as e:
    logger.error(f"Import error when loading application: {e}")
    # Create a simple Flask app as fallback
    from flask import Flask, jsonify
    application = Flask(__name__)
    
    @application.route('/')
    def fallback_index():
        return jsonify({
            "status": "error", 
            "message": "Application failed to load properly",
            "error": str(e)
        }), 500
        
    @application.route('/healthcheck')
    def fallback_healthcheck():
        return jsonify({
            "status": "error", 
            "message": "System in fallback mode - application failed to initialize"
        }), 500
        
except Exception as e:
    logger.error(f"Unexpected error when loading application: {e}")
    # Create a simple Flask app as fallback
    from flask import Flask, jsonify
    application = Flask(__name__)
    
    @application.route('/')
    def fallback_index():
        return jsonify({
            "status": "error", 
            "message": "Application failed to load properly",
            "error": str(e)
        }), 500
        
    @application.route('/healthcheck')
    def fallback_healthcheck():
        return jsonify({
            "status": "error", 
            "message": "System in fallback mode - application failed to initialize"
        }), 500

# Gunicorn looks for an 'application' object by default
if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
