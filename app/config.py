"""
Configuration for the RedBarSushiAI FastAPI application.

This module uses Pydantic's BaseSettings for environment variable loading
with validation and type conversion.
"""

import os
import logging
from typing import Dict, Any, Optional, List

# Set up logger first
logger = logging.getLogger(__name__)

# Try import for Pydantic v2 first, fall back to v1 if needed
# Check Pydantic version and import accordingly
try:
    import pydantic
    pydantic_version = tuple(map(int, pydantic.VERSION.split('.')[:2]))
    if pydantic_version >= (2, 0):
        # Pydantic v2 imports
        from pydantic_settings import BaseSettings
        from pydantic import Field, field_validator as validator, AnyHttpUrl
        PYDANTIC_V2 = True
    else:
        # Pydantic v1 imports
        from pydantic import BaseSettings, Field, validator, AnyHttpUrl
        PYDANTIC_V2 = False
except ImportError:
    # Fallback if pydantic is not installed at all
    logger.error("Pydantic is not installed!")
    raise
logger.setLevel(logging.DEBUG)  # Ensure this logger is verbose
# Add handler if still no output from this logger
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.propagate = True

logger.info(f"Using Pydantic v2: {PYDANTIC_V2}")

# Default environment variables path
ENV_FILE = ".env"  # Use main .env file

# Display raw environment variables for debugging
logger.critical("--- app.config.py: Checking raw environment variables ---")
raw_openai_key_from_os_environ = os.environ.get('OPENAI_API_KEY')
logger.critical(f"Raw OPENAI_API_KEY directly from os.environ: '{raw_openai_key_from_os_environ}' (Type: {type(raw_openai_key_from_os_environ).__name__})")
if raw_openai_key_from_os_environ:
    logger.critical(f"Raw OPENAI_API_KEY preview from os.environ: {raw_openai_key_from_os_environ[:7]}...{raw_openai_key_from_os_environ[-4:] if len(raw_openai_key_from_os_environ) > 11 else ''}")
else:
    logger.critical("OPENAI_API_KEY NOT FOUND in os.environ!")

class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""
    
    # Base configuration
    APP_NAME: str = "RedBarSushiAI"
    DEBUG: bool = Field(False, env="DEBUG")
    PORT: int = Field(5000, env="PORT")
    BASE_URL: str = Field("https://redbarsushiai.onrender.com", env="BASE_URL")
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    
    # Environment
    ENVIRONMENT: str = Field("development", env="FLASK_ENV")  # Keep FLASK_ENV for compatibility
    RENDER: bool = Field(False, env="RENDER")
    DOCKER: bool = Field(False, env="DOCKER")
    FORCE_HEADLESS: bool = Field(False, env="FORCE_HEADLESS")
    
    # Log settings
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    
    # Database settings
    DATABASE_URL: str = Field("sqlite:///app.db", env="DATABASE_URL")  # Default to SQLite for local dev
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # Redis settings
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    CELERY_BROKER_URL: Optional[str] = Field(None, env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(None, env="CELERY_RESULT_BACKEND")
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    OPENAI_REALTIME_MODEL: str = Field("gpt-4o-realtime-preview-2024-12-17", env="OPENAI_REALTIME_MODEL")
    OPENAI_REALTIME_VOICE: str = Field("shimmer", env="OPENAI_REALTIME_VOICE")
    OPENAI_REALTIME_INSTRUCTIONS: str = Field(
        """
        You are an AI assistant for a sushi restaurant named Red Bar Sushi. Your role is to help customers with their 
        orders and menu questions in a friendly, efficient manner. Speak with a helpful, welcoming tone appropriate 
        for a high-end sushi restaurant.
        """,
        env="OPENAI_REALTIME_INSTRUCTIONS"
    )
    
    # Twilio settings
    TWILIO_ACCOUNT_SID: Optional[str] = Field(None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(None, env="TWILIO_PHONE_NUMBER")
    
    # Stripe settings (if used)
    STRIPE_API_KEY: Optional[str] = Field(None, env="STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    
    # Restaurant Configuration
    RESTAURANT_NAME: str = Field("Restaurant", env="RESTAURANT_NAME")
    RESTAURANT_TYPE: str = Field("restaurant", env="RESTAURANT_TYPE") 
    RESTAURANT_GREETING_NAME: str = Field("assistant", env="RESTAURANT_GREETING_NAME")
    RESTAURANT_PHONE_GREETING: Optional[str] = Field(None, env="RESTAURANT_PHONE_GREETING")
    
    # Deliverect settings
    DELIVERECT_CHANNEL_NAME: str = Field("redbarsushi", env="DELIVERECT_CHANNEL_NAME")
    DELIVERECT_API_KEY: Optional[str] = Field(None, env="DELIVERECT_API_KEY")
    DELIVERECT_BASE_URL: str = Field("https://api.staging.deliverect.com", env="DELIVERECT_BASE_URL") 
    DELIVERECT_API_URL: str = Field("https://api.staging.deliverect.com/v2/orders", env="DELIVERECT_API_URL")
    DELIVERECT_CLIENT_ID: Optional[str] = Field(None, env="DELIVERECT_CLIENT_ID")
    DELIVERECT_CLIENT_SECRET: Optional[str] = Field(None, env="DELIVERECT_CLIENT_SECRET")
    
    # Voice config (ConversationRelay only - Media Streams support removed)
    VOICE_HANDLER: str = Field("conversation_relay", env="VOICE_HANDLER")
    
    # AI agent configuration
    USE_AI_AGENTS: bool = Field(True, env="USE_AI_AGENTS")
    
    # Twilio ConversationRelay settings
    TWILIO_CONVERSATION_SERVICE_SID: Optional[str] = Field(None, env="TWILIO_CONVERSATION_SERVICE_SID")
    TWILIO_CONNECTOR_NAME: Optional[str] = Field(None, env="TWILIO_CONNECTOR_NAME")

    # Agent IDs
    OPENAI_FRONTLINE_AGENT_ID: Optional[str] = Field(None, env="OPENAI_FRONTLINE_AGENT_ID")
    OPENAI_MENU_AGENT_ID: Optional[str] = Field(None, env="OPENAI_MENU_AGENT_ID")
    OPENAI_CART_AGENT_ID: Optional[str] = Field(None, env="OPENAI_CART_AGENT_ID")
    OPENAI_FULFILLMENT_AGENT_ID: Optional[str] = Field(None, env="OPENAI_FULFILLMENT_AGENT_ID")
    OPENAI_GUARDRAIL_AGENT_ID: Optional[str] = Field(None, env="OPENAI_GUARDRAIL_AGENT_ID")
    OPENAI_ESCALATION_AGENT_ID: Optional[str] = Field(None, env="OPENAI_ESCALATION_AGENT_ID")
    
    # Database config
    INITIALIZE_MENU_DATABASE: bool = Field(True, env="INITIALIZE_MENU_DATABASE")

    # Optional MCP settings
    MCP_PORT: Optional[int] = Field(None, env="MCP_PORT")
    MCP_URL: Optional[str] = Field(None, env="MCP_URL")
    
    # No validation needed for VOICE_HANDLER since only ConversationRelay is supported
    
    if PYDANTIC_V2:
        # Pydantic v2 config
        model_config = {
            "env_file": ENV_FILE,
            "case_sensitive": True,
            "extra": "allow"  # Allow extra fields from environment variables
        }
    else:
        # Pydantic v1 config
        class Config:
            """Pydantic config"""
            env_file = ENV_FILE
            case_sensitive = True
            extra = "allow"  # Allow extra fields from environment variables

# Load settings from environment variables
try:
    # Try to get the installed pydantic version
    import pydantic
    logger.critical(f"Pydantic version: {pydantic.__version__}")
    
    logger.critical("--- app.config.py: Attempting to load Pydantic Settings ---")
    logger.critical(f"Using env_file: {ENV_FILE}")
    
    # Try to load settings from environment variables
    settings = Settings()
    
    logger.critical("--- Pydantic Settings object created ---")
    logger.critical(f"Loaded settings.OPENAI_API_KEY: '{settings.OPENAI_API_KEY}'")
    if settings.OPENAI_API_KEY:
        logger.critical(f"Loaded settings.OPENAI_API_KEY preview: {settings.OPENAI_API_KEY[:7]}...{settings.OPENAI_API_KEY[-4:] if len(settings.OPENAI_API_KEY) > 11 else ''}")
        if "mytestapikey" in settings.OPENAI_API_KEY.lower():
            logger.critical("CRITICAL: OPENAI_API_KEY loaded appears to be a TEST/DUMMY key: " + settings.OPENAI_API_KEY)
            
    logger.info("Settings loaded successfully")
    logger.info(f"Running in environment: {settings.ENVIRONMENT}")
    logger.info(f"BASE_URL from settings: {settings.BASE_URL}")
except Exception as e:
    logger.critical(f"CRITICAL ERROR during Pydantic Settings instantiation in app.config.py: {e}", exc_info=True)
    # Load with empty values for optional fields to prevent startup failures
    # in environments where all env vars are not set
    # Try to create settings with minimal config
    try:
        logger.critical("Attempting to create settings with minimal config")
        settings = Settings(
            SECRET_KEY=os.environ.get("APP_SECRET_KEY", "dev-secret-key"),
            DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///test.db"),
            BASE_URL=os.environ.get("BASE_URL", "https://redbarsushiai-staging.onrender.com"),
            RESTAURANT_NAME=os.environ.get("RESTAURANT_NAME", "Restaurant"),
            RESTAURANT_TYPE=os.environ.get("RESTAURANT_TYPE", "restaurant"),
            RESTAURANT_GREETING_NAME=os.environ.get("RESTAURANT_GREETING_NAME", "assistant"),
        )
        logger.info("Created settings with minimal config")
        
        # Log the OPENAI_API_KEY again
        logger.critical(f"Minimal config settings.OPENAI_API_KEY: '{settings.OPENAI_API_KEY}'")
        if settings.OPENAI_API_KEY:
            logger.critical(f"Minimal config settings.OPENAI_API_KEY preview: {settings.OPENAI_API_KEY[:7]}...{settings.OPENAI_API_KEY[-4:] if len(settings.OPENAI_API_KEY) > 11 else ''}")
            
    except Exception as e:
        # If that fails, create with all potential fields to avoid crashing
        logger.critical(f"Error creating minimal settings: {e}, trying with all fields")
        
        # Log the raw value again
        raw_key = os.environ.get("OPENAI_API_KEY", "NO_KEY_FOUND")
        logger.critical(f"Raw OPENAI_API_KEY before full settings creation: '{raw_key}'")
        
        settings = Settings(
            SECRET_KEY=os.environ.get("APP_SECRET_KEY", "dev-secret-key"),
            DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///test.db"),
            BASE_URL=os.environ.get("BASE_URL", "https://redbarsushiai-staging.onrender.com"),
            OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", "sk-mytestapikey"),  # EXPLICITLY SET FALLBACK FOR DEBUGGING
            RESTAURANT_NAME=os.environ.get("RESTAURANT_NAME", "Restaurant"),
            RESTAURANT_TYPE=os.environ.get("RESTAURANT_TYPE", "restaurant"),
            RESTAURANT_GREETING_NAME=os.environ.get("RESTAURANT_GREETING_NAME", "assistant"),
            TWILIO_ACCOUNT_SID=os.environ.get("TWILIO_ACCOUNT_SID", None),
            TWILIO_AUTH_TOKEN=os.environ.get("TWILIO_AUTH_TOKEN", None),
            TWILIO_PHONE_NUMBER=os.environ.get("TWILIO_PHONE_NUMBER", None),
            DELIVERECT_API_KEY=os.environ.get("DELIVERECT_API_KEY", None),
            DELIVERECT_API_URL=os.environ.get("DELIVERECT_API_URL", "https://api.staging.deliverect.com/v2/orders"),
            DELIVERECT_CLIENT_ID=os.environ.get("DELIVERECT_CLIENT_ID", None),
            DELIVERECT_CLIENT_SECRET=os.environ.get("DELIVERECT_CLIENT_SECRET", None),
            STRIPE_API_KEY=os.environ.get("STRIPE_API_KEY", None),
            REDIS_URL=os.environ.get("REDIS_URL", None),
            CELERY_BROKER_URL=os.environ.get("CELERY_BROKER_URL", None),
            CELERY_RESULT_BACKEND=os.environ.get("CELERY_RESULT_BACKEND", None),
        )
        logger.critical("Created settings with all fields")
        
        # Log the final result for OPENAI_API_KEY
        logger.critical(f"Final settings.OPENAI_API_KEY: '{settings.OPENAI_API_KEY}'")
        if settings.OPENAI_API_KEY:
            logger.critical(f"Final settings.OPENAI_API_KEY preview: {settings.OPENAI_API_KEY[:7]}...{settings.OPENAI_API_KEY[-4:] if len(settings.OPENAI_API_KEY) > 11 else ''}")
            if "mytestapikey" in settings.OPENAI_API_KEY.lower():
                logger.critical("CRITICAL: Final OPENAI_API_KEY is a TEST/DUMMY key: " + settings.OPENAI_API_KEY)