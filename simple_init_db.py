#!/usr/bin/env python3
"""
Simple database initialization script for RedBarSushiAI.
Creates all tables needed for the application.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine

# Import models to ensure they're registered
from app.db_async import Base
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order_async import Order, OrderItem, OrderItemModifier, ContactRequest

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize the database with all required tables."""
    
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/redbarsushi"
    )
    
    # Ensure it's using asyncpg
    if "postgresql://" in database_url and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    logger.info(f"Connecting to database: {database_url}")
    
    # Create engine
    engine = create_async_engine(
        database_url,
        echo=True,  # Show SQL statements
    )
    
    try:
        # Create all tables
        logger.info("Creating database tables...")
        async with engine.begin() as conn:
            # Drop all tables first if they exist (for clean state)
            if "--drop" in sys.argv:
                logger.warning("Dropping existing tables...")
                await conn.run_sync(Base.metadata.drop_all)
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database tables created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False
    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    logger.info("Starting database initialization...")
    
    try:
        success = await init_database()
        
        if success:
            logger.info("\n✅ Database initialized successfully!")
            return 0
        else:
            logger.error("\n❌ Database initialization failed!")
            return 1
            
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    # Run with --drop flag to drop existing tables first
    if "--help" in sys.argv:
        print("Usage: python simple_init_db.py [--drop]")
        print("  --drop: Drop existing tables before creating new ones")
        sys.exit(0)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)