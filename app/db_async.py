"""
Database configuration for the FastAPI application.

This module provides an async SQLAlchemy setup using SQLAlchemy 2.0 async features
with asyncpg as the PostgreSQL driver.
"""

import logging
from typing import AsyncGenerator, Optional, Dict, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect, event, text

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Convert the synchronous SQLAlchemy DATABASE_URL to async version
# Example: postgresql://user:pass@localhost/dbname -> postgresql+asyncpg://user:pass@localhost/dbname
database_url = settings.DATABASE_URL
if database_url.startswith('postgresql://'):
    DATABASE_URL = database_url.replace('postgresql://', 'postgresql+asyncpg://')
elif database_url.startswith('sqlite://'):
    DATABASE_URL = database_url.replace('sqlite://', 'sqlite+aiosqlite://')
else:
    DATABASE_URL = database_url
    logger.warning(f"Unrecognized database URL format: {database_url}")

# Create async engine
engine_args = {
    "echo": False,  # Set to True for SQL query logging
    "pool_pre_ping": True,  # Verify connections before using them
    "pool_recycle": 1800,  # 30 minutes to match Render's proxy timeout
}

# Add PostgreSQL-specific options
if DATABASE_URL.startswith('postgresql+asyncpg://'):
    # SQLAlchemy 2.0 style of setting connection args with asyncpg
    engine_args["connect_args"] = {
        "timeout": 15,  # Connection timeout in seconds
        "command_timeout": 60,  # Statement timeout in seconds
        # Connection options passed to asyncpg
        "statement_cache_size": 0,  # Disable statement caching
        "max_cached_statement_lifetime": 0,  # Disable statement caching
    }

engine = create_async_engine(DATABASE_URL, **engine_args)

# Create session factory for dependency injection
async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False
)

# Base class for all models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

# Dependency to provide async database sessions
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency that yields database sessions for FastAPI endpoint handlers.
    
    Yields:
        AsyncSession: Async SQLAlchemy session for database operations
    """
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()

# Async helper to verify database connection
async def verify_connection() -> bool:
    """Verify database connection is working properly."""
    try:
        session = async_session_factory()
        try:
            # Try a simple query to check connection
            await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection verification failed: {e}")
            return False
        finally:
            await session.close()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        return False

# Function to initialize the database
async def init_database() -> None:
    """Initialize the database schema."""
    try:
        # For development/testing, create tables - in production, use migrations
        if settings.ENVIRONMENT.lower() == "development":
            # Create all tables
            async with engine.begin() as conn:
                # Create tables if they don't exist
                # In production, migrations should be used instead
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

# Helper function for graceful database connection handling
async def ensure_fresh_session() -> AsyncSession:
    """
    Ensure a fresh, working database session.
    
    Returns:
        AsyncSession: A fresh database session
    
    Raises:
        Exception: If unable to create a working session
    """
    try:
        session = async_session_factory()
        # Test the connection
        await session.execute(text("SELECT 1"))
        return session
    except Exception as e:
        logger.error(f"Error with database session: {e}")
        # Try one more time with a new session
        try:
            session = async_session_factory()
            await session.execute(text("SELECT 1"))
            return session
        except Exception as retry_error:
            logger.error(f"Failed to create fresh session on retry: {retry_error}")
            raise