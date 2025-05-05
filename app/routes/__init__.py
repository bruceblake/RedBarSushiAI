"""
Route registration for RedBarSushiAI.
This module registers all Flask blueprints for the application.
"""

from flask import Flask

def register_blueprints(app: Flask):
    """
    Register all blueprints with the Flask application.
    
    Args:
        app: The Flask application
    """
    # Import blueprints
    from app.routes.voice import voice_bp
    from app.routes.menu import menu_bp
    from app.routes.order import order_bp
    from app.routes.location import location_bp
    from app.routes.order_ai import order_ai_bp
    
    # Import the orchestrated voice blueprint
    from app.routes.voice_orchestrated import orchestrated_voice_bp
    
    # Register blueprints
    app.register_blueprint(voice_bp, url_prefix='/webhook/voice')
    app.register_blueprint(menu_bp, url_prefix='/webhook/menu')
    app.register_blueprint(order_bp, url_prefix='/webhook/order')
    app.register_blueprint(location_bp, url_prefix='/webhook/location')
    app.register_blueprint(order_ai_bp, url_prefix='/webhook/order_ai')
    
    # Register the orchestrated voice blueprint with its own prefix
    app.register_blueprint(orchestrated_voice_bp, url_prefix='/voice_orchestrated')