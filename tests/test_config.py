"""
Test configuration for different environments.
Automatically switches between mock and real services based on environment.
"""

import os
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseSettings, Field


class TestEnvironment(str, Enum):
    """Test environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class TestConfig(BaseSettings):
    """Test configuration that adapts to environment."""
    
    # Environment
    environment: TestEnvironment = Field(
        default=TestEnvironment.TESTING,
        env="FASTAPI_ENV"
    )
    
    # Feature flags - automatically determined by environment
    @property
    def use_mock_services(self) -> bool:
        """Use mocks in development/testing, real services in staging/production."""
        if self.environment in [TestEnvironment.DEVELOPMENT, TestEnvironment.TESTING]:
            return os.getenv("USE_MOCK_SERVICES", "true").lower() == "true"
        # Staging and production use real services
        return False
    
    @property
    def use_real_database(self) -> bool:
        """Use test database locally, real database in staging/production."""
        return self.environment in [TestEnvironment.STAGING, TestEnvironment.PRODUCTION]
    
    @property
    def use_real_redis(self) -> bool:
        """Use test Redis locally, real Redis in staging/production."""
        return self.environment in [TestEnvironment.STAGING, TestEnvironment.PRODUCTION]
    
    # Mock server
    mock_server_url: str = Field(
        default="http://localhost:8001",
        env="MOCK_SERVER_URL"
    )
    
    # Service URLs (switched based on environment)
    @property
    def twilio_base_url(self) -> str:
        if self.use_mock_services:
            return f"{self.mock_server_url}/twilio"
        return "https://api.twilio.com"
    
    @property
    def openai_base_url(self) -> str:
        if self.use_mock_services:
            return f"{self.mock_server_url}/openai"
        return "https://api.openai.com"
    
    @property
    def deliverect_base_url(self) -> str:
        if self.use_mock_services:
            return f"{self.mock_server_url}/deliverect"
        if self.environment == TestEnvironment.STAGING:
            return os.getenv("DELIVERECT_SANDBOX_URL", "https://api.staging.deliverect.com")
        return "https://api.deliverect.com"
    
    # Database configuration
    @property
    def database_url(self) -> str:
        # Always use DATABASE_URL from environment if available (Render sets this)
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
            
        # Fallback for local testing
        if self.environment == TestEnvironment.TESTING:
            return "postgresql+asyncpg://redbarsushi:redbarsushi@localhost:5433/redbarsushi_test"
        return "postgresql+asyncpg://localhost/redbarsushi"
    
    # Redis configuration
    @property
    def redis_url(self) -> str:
        # Always use REDIS_URL from environment if available (Render sets this)
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return redis_url
            
        # Fallback for local testing
        if self.environment == TestEnvironment.TESTING:
            return "redis://localhost:6381/0"
        return "redis://localhost:6379/0"
    
    # Test data
    test_phone_number: str = Field(
        default="+15005550006",  # Twilio test number
        env="TEST_PHONE_NUMBER"
    )
    test_customer_name: str = Field(
        default="Test Customer",
        env="TEST_CUSTOMER_NAME"
    )
    
    # Timeouts
    test_timeout: int = Field(
        default=30,
        env="TEST_TIMEOUT"
    )
    mock_delay_ms: int = Field(
        default=0,
        env="MOCK_DELAY_MS"
    )
    
    # Performance thresholds
    max_response_time_ms: int = Field(
        default=500,
        env="MAX_RESPONSE_TIME_MS"
    )
    max_order_processing_time_s: int = Field(
        default=3,
        env="MAX_ORDER_PROCESSING_TIME_S"
    )
    
    class Config:
        env_file = ".env.test"
        case_sensitive = False


# Singleton instance
test_config = TestConfig()


def get_test_config() -> TestConfig:
    """Get test configuration instance."""
    return test_config


def is_mock_environment() -> bool:
    """Check if running with mock services."""
    return test_config.use_mock_services


def is_staging_environment() -> bool:
    """Check if running in staging environment."""
    return test_config.environment == TestEnvironment.STAGING


def get_service_timeout() -> int:
    """Get appropriate timeout for current environment."""
    if is_mock_environment():
        return 5  # Fast timeout for mocks
    if is_staging_environment():
        return 30  # Longer timeout for real services
    return 10  # Default