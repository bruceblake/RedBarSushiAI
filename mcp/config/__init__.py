"""
Configuration module for the MCP service.
Loads configuration from environment variables and provides defaults.
"""
import os
from typing import Dict, Any


class Config:
    """Configuration class for MCP service."""

    def __init__(self):
        # Environment
        self.ENV = os.getenv("MCP_ENV", "development")
        self.DEBUG = self.ENV == "development"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql://mcp:password@localhost:5432/mcp_testing"
        )

        # Redis
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Render API
        self.RENDER_API_KEY = os.getenv("RENDER_API_KEY", "")
        self.RENDER_SERVICE_ID = os.getenv("RENDER_SERVICE_ID", "")

        # GitHub
        self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
        self.GITHUB_REPO = os.getenv("GITHUB_REPO", "proxyie/RedBarSushiAI")
        self.GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "staging")
        self.GITHUB_TEST_BRANCH = os.getenv("GITHUB_TEST_BRANCH", "staging")

        # Slack
        self.SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
        self.SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#redbarsushi-alerts")

        # Test configuration
        self.TEST_BASE_URL = os.getenv(
            "TEST_BASE_URL", "https://redbarsushi-staging.onrender.com"
        )
        self.TEST_TWILIO_ACCOUNT_SID = os.getenv(
            "TEST_TWILIO_ACCOUNT_SID", "ACb8391ed8d92871d85180ca9adea481b6"
        )
        self.TEST_TWILIO_AUTH_TOKEN = os.getenv("TEST_TWILIO_AUTH_TOKEN", "")
        self.TEST_TWILIO_PHONE = os.getenv("TEST_TWILIO_PHONE", "+18333247207")
        self.TEST_OPENAI_API_KEY = os.getenv("TEST_OPENAI_API_KEY", "")
        self.TEST_CUSTOMER_PHONE = os.getenv("TEST_CUSTOMER_PHONE", "+15551234567")

        # Testing database
        self.TEST_DATABASE_URL = os.getenv(
            "TEST_DATABASE_URL", "sqlite:///:memory:"
        )
        self.TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")

    def as_dict(self) -> Dict[str, Any]:
        """Return configuration as a dictionary."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_") and key.isupper()
        }


# Create a singleton instance
config = Config()