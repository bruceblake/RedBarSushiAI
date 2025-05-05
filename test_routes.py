"""
Test script to verify Flask routes in the refactored code.
This script attempts to initialize the Flask app and print all registered routes.
"""

import os
import sys
import logging
from flask import url_for

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_app_routes():
    """Print all registered routes in the Flask app."""
    try:
        logger.info("Initializing Flask app...")
        from app import create_app
        app = create_app()
        
        # Create a test request context to enable url_for
        with app.test_request_context():
            logger.info("Retrieving registered routes...")
            output = []
            
            # Loop through all routes
            for rule in app.url_map.iter_rules():
                # Get endpoint and methods
                methods = ','.join(sorted(rule.methods))
                endpoint = rule.endpoint
                
                # Try to build a URL (some may fail due to required parameters)
                url = None
                try:
                    url = url_for(endpoint)
                except Exception:
                    url = f"{rule}"
                
                output.append((endpoint, methods, url))
            
            # Sort by endpoint and print
            logger.info("\n\n")
            logger.info("=" * 80)
            logger.info("REGISTERED ROUTES")
            logger.info("=" * 80)
            logger.info(f"{'ENDPOINT':<40} {'METHODS':<20} {'URL':<40}")
            logger.info("-" * 80)
            
            for endpoint, methods, url in sorted(output, key=lambda x: x[0]):
                logger.info(f"{endpoint:<40} {methods:<20} {url:<40}")
        
        logger.info("\n✅ Successfully initialized Flask app and retrieved routes")
        return True
    except Exception as e:
        logger.error(f"❌ Error initializing Flask app or retrieving routes: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_specific_blueprints():
    """Test that specific blueprints are registered."""
    try:
        logger.info("Testing specific blueprint registration...")
        from app import create_app
        app = create_app()
        
        # Get all registered blueprints
        blueprints = []
        for name, blueprint in app.blueprints.items():
            blueprints.append(name)
        
        # Check for our refactored blueprints
        required_blueprints = ["order", "menu", "voice", "voice_orchestrated", "location"]
        missing = []
        
        for bp in required_blueprints:
            if bp not in blueprints:
                missing.append(bp)
        
        if missing:
            logger.error(f"❌ Missing blueprints: {', '.join(missing)}")
            return False
        
        logger.info(f"✅ All required blueprints are registered: {', '.join(required_blueprints)}")
        return True
    except Exception as e:
        logger.error(f"❌ Error testing blueprint registration: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Testing Flask routes...")
    blueprint_result = test_specific_blueprints()
    routes_result = print_app_routes()
    
    success = blueprint_result and routes_result
    logger.info("\n\n")
    logger.info("=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Blueprint Registration: {'✅ PASSED' if blueprint_result else '❌ FAILED'}")
    logger.info(f"Routes Listing: {'✅ PASSED' if routes_result else '❌ FAILED'}")
    logger.info(f"\nOverall: {'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    
    sys.exit(0 if success else 1)