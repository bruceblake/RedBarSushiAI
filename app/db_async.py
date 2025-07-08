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

# Handle both Pydantic v1 and v2
try:
    from app.config import settings
except ImportError as e:
    # If there's an issue with the config import, try to use environment variables directly
    import os
    logger = logging.getLogger(__name__)
    logger.error(f"Error importing settings from app.config: {e}")
    logger.warning("Falling back to direct environment variable usage")
    
    # Get DATABASE_URL directly from the environment
    database_url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    
    # Define a minimal settings object with just what we need
    class MinimalSettings:
        DATABASE_URL = database_url
        ENVIRONMENT = os.environ.get("FASTAPI_ENV", "development")
    
    settings = MinimalSettings()

# Set up logging
logger = logging.getLogger(__name__)

# Convert the synchronous SQLAlchemy DATABASE_URL to async version if needed
# Example: postgresql://user:pass@localhost/dbname -> postgresql+asyncpg://user:pass@localhost/dbname
database_url = settings.DATABASE_URL
if database_url.startswith('postgresql://'):
    DATABASE_URL = database_url.replace('postgresql://', 'postgresql+asyncpg://')
elif database_url.startswith('postgresql+asyncpg://'):
    # Already in async format
    DATABASE_URL = database_url
elif database_url.startswith('sqlite://'):
    DATABASE_URL = database_url.replace('sqlite://', 'sqlite+aiosqlite://')
elif database_url.startswith('sqlite+aiosqlite://'):
    # Already in async format
    DATABASE_URL = database_url
else:
    DATABASE_URL = database_url
    logger.warning(f"Unrecognized database URL format: {database_url}")

# Create async engine with optimized connection pool settings
engine_args = {
    "echo": False,  # Set to True for SQL query logging
    "pool_pre_ping": True,  # Verify connections before using them
    "pool_recycle": 1800,  # 30 minutes to match Render's proxy timeout
    # Connection pool optimization settings
    "pool_size": getattr(settings, 'DB_POOL_SIZE', 10),  # Base pool size
    "max_overflow": getattr(settings, 'DB_MAX_OVERFLOW', 20),  # Additional connections under load
    "pool_timeout": getattr(settings, 'DB_POOL_TIMEOUT', 30),  # Timeout waiting for connection
    "echo_pool": getattr(settings, 'DB_ECHO_POOL', False),  # Set to True for pool debugging
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
        
        # Always run schema migrations for production compatibility
        await migrate_schema()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def migrate_schema() -> None:
    """Migrate database schema to fix column mismatches between SQL and models."""
    try:
        logger.info("Running schema migrations...")
        
        async with engine.begin() as conn:
            # Migration 1: Add missing columns to menu_items
            missing_columns_sql = """
            -- Add missing columns if they don't exist
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS order_index INTEGER DEFAULT 0;
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';
            """
            
            # Migration 2: Add missing columns to modifier tables
            modifier_columns_sql = """
            -- Add missing columns to menu_modifiers
            ALTER TABLE menu_modifiers ADD COLUMN IF NOT EXISTS deliverect_modifier_id VARCHAR(255);
            ALTER TABLE menu_modifiers ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
            ALTER TABLE menu_modifiers ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';
            
            -- Add missing columns to menu_modifier_groups  
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS deliverect_group_id VARCHAR(255);
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS plu VARCHAR(255);
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS multiMax INTEGER DEFAULT 0;
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS is_variant_group BOOLEAN DEFAULT false;
            ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';
            
            -- Add missing columns to menu_categories
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS deliverect_category_id VARCHAR(255);
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS parent_id INTEGER;
            """
            
            # Migration 3: Fix column sizes with simple ALTER statements
            column_size_fixes_sql = """
            -- Fix column sizes to match SQLAlchemy models
            ALTER TABLE menu_items ALTER COLUMN deliverect_item_id TYPE VARCHAR(255);
            ALTER TABLE menu_modifier_groups ALTER COLUMN deliverect_group_id TYPE VARCHAR(255);
            ALTER TABLE menu_modifiers ALTER COLUMN deliverect_modifier_id TYPE VARCHAR(255);
            ALTER TABLE menu_categories ALTER COLUMN deliverect_category_id TYPE VARCHAR(255);
            """
            
            # Execute migrations in order
            # Step 1: Add missing columns to menu_items
            for sql_statement in missing_columns_sql.split(';'):
                if sql_statement.strip():
                    await conn.execute(text(sql_statement.strip()))
            
            # Step 2: Add missing columns to modifier tables and categories
            for sql_statement in modifier_columns_sql.split(';'):
                if sql_statement.strip():
                    await conn.execute(text(sql_statement.strip()))
            
            # Step 3: Fix column sizes (ignore errors if columns don't exist yet)
            for sql_statement in column_size_fixes_sql.split(';'):
                if sql_statement.strip():
                    try:
                        await conn.execute(text(sql_statement.strip()))
                    except Exception as e:
                        # Log but don't fail - column might not exist yet
                        logger.warning(f"Column size fix failed (may not exist): {e}")
            
            await conn.commit()
            logger.info("✅ Schema migrations completed successfully")
            
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        # Don't raise - app should still start even if migrations fail
        logger.warning("Continuing startup despite migration failure")

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

# Alias for backward compatibility
init_db = init_database