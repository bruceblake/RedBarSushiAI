"""
Configuration for the RedBarSushiAI FastAPI application.

This module uses Pydantic's BaseSettings for environment variable loading
with validation and type conversion.
"""

import os
from typing import Dict, Any, Optional, List
# Import from pydantic_settings for Pydantic v2 compatibility
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, AnyHttpUrl

# Default environment variables path
ENV_FILE = ".env"

class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""
    
    # Base configuration
    APP_NAME: str = "RedBarSushiAI"
    DEBUG: bool = Field(False, env="DEBUG")
    PORT: int = Field(5000, env="PORT")
    BASE_URL: str = Field("https://redbarsushiai.onrender.com", env="BASE_URL")
    SECRET_KEY: str = Field(..., env="APP_SECRET_KEY")
    
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
    OPENAI_REALTIME_MODEL: str = Field("gpt-4o-realtime-preview-2024-10-01", env="OPENAI_REALTIME_MODEL")
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
    
    # Deliverect settings
    DELIVERECT_CHANNEL_NAME: str = Field("redbarsushi", env="DELIVERECT_CHANNEL_NAME")
    DELIVERECT_API_KEY: Optional[str] = Field(None, env="DELIVERECT_API_KEY")
    DELIVERECT_BASE_URL: str = Field("https://api.staging.deliverect.com", env="DELIVERECT_BASE_URL") 
    DELIVERECT_API_URL: str = Field("https://api.staging.deliverect.com/v2/orders", env="DELIVERECT_API_URL")
    DELIVERECT_CLIENT_ID: Optional[str] = Field(None, env="DELIVERECT_CLIENT_ID")
    DELIVERECT_CLIENT_SECRET: Optional[str] = Field(None, env="DELIVERECT_CLIENT_SECRET")
    
    # Voice config
    VOICE_HANDLER: str = Field("realtime", env="VOICE_HANDLER")

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
    
    # Validators
    @field_validator('VOICE_HANDLER')
    def validate_voice_handler(cls, v):
        if v != "realtime":
            raise ValueError(f"Unsupported VOICE_HANDLER value: {v}, only 'realtime' is supported")
        return v
    
    model_config = {
        "env_file": ENV_FILE,
        "case_sensitive": True,
        "extra": "allow",  # Allow extra fields from environment variables
    }

# Load settings from environment variables
try:
    settings = Settings()
except Exception as e:
    import logging
    logging.error(f"Error loading configuration: {e}")
    # Load with empty values for optional fields to prevent startup failures
    # in environments where all env vars are not set
    # Try to create settings with minimal config
    try:
        settings = Settings(
            SECRET_KEY=os.environ.get("APP_SECRET_KEY", "dev-secret-key"),
            DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///test.db"),
            BASE_URL=os.environ.get("BASE_URL", "https://redbarsushiai-staging.onrender.com"),
        )
    except Exception as e:
        # If that fails, create with all potential fields to avoid crashing
        logging.error(f"Error creating minimal settings: {e}, trying with all fields")
        settings = Settings(
            SECRET_KEY=os.environ.get("APP_SECRET_KEY", "dev-secret-key"),
            DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///test.db"),
            BASE_URL=os.environ.get("BASE_URL", "https://redbarsushiai-staging.onrender.com"),
            OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", None),
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