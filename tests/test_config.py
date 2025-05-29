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
    
    # Feature flags
    use_mock_services: bool = Field(
        default=True,
        env="USE_MOCK_SERVICES"
    )
    use_real_database: bool = Field(
        default=False,
        env="USE_REAL_DATABASE"
    )
    use_real_redis: bool = Field(
        default=False,
        env="USE_REAL_REDIS"
    )
    
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
        if self.environment == TestEnvironment.TESTING:
            return "postgresql+asyncpg://redbarsushi:redbarsushi@localhost:5433/redbarsushi_test"
        return os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/redbarsushi")
    
    # Redis configuration
    @property
    def redis_url(self) -> str:
        if self.environment == TestEnvironment.TESTING:
            return "redis://localhost:6381/0"
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
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