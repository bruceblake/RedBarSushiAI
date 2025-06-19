#!/usr/bin/env python3
"""
Database initialization script for RedBarSushiAI.
Creates all tables and initial data needed for the application.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Import models to ensure they're registered
from app.models.base_async import BaseAsync
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem
from app.models.location_async import Location

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize the database with all required tables."""
    
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/redbarsushi"
    )
    
    # Ensure it's using psycopg2
    if "postgresql://" in database_url and "+psycopg2" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    
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
                await conn.run_sync(BaseAsync.metadata.drop_all)
            
            # Create all tables
            await conn.run_sync(BaseAsync.metadata.create_all)
            
        logger.info("Database tables created successfully!")
        
        # Create default location if it doesn't exist
        async with engine.connect() as conn:
            # Check if default location exists
            result = await conn.execute(
                text("SELECT id FROM locations WHERE name = :name"),
                {"name": "Red Bar Sushi - Main"}
            )
            location_exists = result.fetchone()
            
            if not location_exists:
                logger.info("Creating default location...")
                await conn.execute(
                    text("""
                        INSERT INTO locations (
                            name, address, phone, email,
                            business_hours, delivery_radius,
                            delivery_fee, minimum_order,
                            tax_rate, is_active
                        ) VALUES (
                            :name, :address, :phone, :email,
                            :hours, :radius, :fee, :minimum,
                            :tax, :active
                        )
                    """),
                    {
                        "name": "Red Bar Sushi - Main",
                        "address": "123 Sushi Lane, San Francisco, CA 94110",
                        "phone": "+14155551234",
                        "email": "info@redbarsushi.com",
                        "hours": {
                            "monday": {"open": "11:00", "close": "22:00"},
                            "tuesday": {"open": "11:00", "close": "22:00"},
                            "wednesday": {"open": "11:00", "close": "22:00"},
                            "thursday": {"open": "11:00", "close": "22:00"},
                            "friday": {"open": "11:00", "close": "23:00"},
                            "saturday": {"open": "11:00", "close": "23:00"},
                            "sunday": {"open": "12:00", "close": "21:00"}
                        },
                        "radius": 5.0,
                        "fee": 495,  # $4.95 in cents
                        "minimum": 2000,  # $20.00 in cents
                        "tax": 0.0875,  # 8.75%
                        "active": True
                    }
                )
                await conn.commit()
                logger.info("Default location created!")
        
        # Verify tables were created
        async with engine.connect() as conn:
            # Check tables exist
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result]
            
            logger.info("Created tables:")
            for table in tables:
                logger.info(f"  - {table}")
            
            expected_tables = [
                "locations",
                "menu_categories", 
                "menu_items",
                "menu_modifiers",
                "menu_modifier_groups",
                "menu_item_modifier_groups",
                "menu_modifier_group_modifiers",
                "menu_name_variants",
                "orders",
                "order_items"
            ]
            
            missing_tables = set(expected_tables) - set(tables)
            if missing_tables:
                logger.error(f"Missing tables: {missing_tables}")
                return False
                
        logger.info("Database initialization complete!")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False
    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    logger.info("Starting database initialization...")
    
    # Check if database is accessible
    try:
        success = await init_database()
        
        if success:
            logger.info("\n✅ Database initialized successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Run 'python seed_menu_db.py' to load sample menu data")
            logger.info("2. Start the application with 'uvicorn app.main:app --reload'")
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
        print("Usage: python init_db.py [--drop]")
        print("  --drop: Drop existing tables before creating new ones")
        sys.exit(0)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)