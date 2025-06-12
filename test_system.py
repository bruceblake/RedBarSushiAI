#!/usr/bin/env python3
"""
Test script to verify the RedBarSushiAI system is ready for E2E testing.
Run this after initialization to ensure everything is set up correctly.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import redis.asyncio as redis

async def test_database():
    """Test database connectivity and tables."""
    print("Testing Database Connection...")
    try:
        # Get database URL from environment
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/sushi_restaurant")
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        
        engine = create_async_engine(db_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # Test connection
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            print("✓ Database connection successful")
            
            # Check tables exist
            tables_query = text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            result = await session.execute(tables_query)
            tables = [row[0] for row in result]
            
            required_tables = ['locations', 'menus', 'menu_items', 'orders', 'order_items']
            for table in required_tables:
                if table in tables:
                    print(f"✓ Table '{table}' exists")
                else:
                    print(f"✗ Table '{table}' missing")
                    return False
            
            # Check if we have a location
            result = await session.execute(text("SELECT COUNT(*) FROM locations"))
            location_count = result.scalar()
            print(f"✓ Found {location_count} location(s)")
            
            # Check if we have menu items
            result = await session.execute(text("SELECT COUNT(*) FROM menu_items"))
            menu_item_count = result.scalar()
            print(f"✓ Found {menu_item_count} menu item(s)")
            
            if menu_item_count == 0:
                print("⚠️  No menu items found. Run 'python seed_menu_db.py' to add sample data.")
            
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

async def test_redis():
    """Test Redis connectivity."""
    print("\nTesting Redis Connection...")
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        await r.ping()
        print("✓ Redis connection successful")
        
        # Test set/get
        await r.set("test_key", "test_value", ex=5)
        value = await r.get("test_key")
        assert value == "test_value"
        print("✓ Redis read/write successful")
        
        await r.close()
        return True
        
    except Exception as e:
        print(f"✗ Redis test failed: {e}")
        return False

def test_environment():
    """Test environment variables."""
    print("\nChecking Environment Variables...")
    
    required_vars = [
        ("OPENAI_API_KEY", "OpenAI API key for AI agents"),
        ("TWILIO_ACCOUNT_SID", "Twilio account SID"),
        ("TWILIO_AUTH_TOKEN", "Twilio auth token"),
        ("TWILIO_PHONE_NUMBER", "Twilio phone number"),
    ]
    
    optional_vars = [
        ("TWILIO_CONVERSATION_SERVICE_SID", "ConversationRelay service SID"),
        ("DELIVERECT_API_KEY", "Deliverect API key (for POS integration)"),
    ]
    
    all_good = True
    
    for var, description in required_vars:
        if os.getenv(var):
            print(f"✓ {var} is set ({description})")
        else:
            print(f"✗ {var} is missing! ({description})")
            all_good = False
    
    for var, description in optional_vars:
        if os.getenv(var):
            print(f"✓ {var} is set ({description})")
        else:
            print(f"⚠️  {var} is not set ({description})")
    
    return all_good

async def test_api():
    """Test API connectivity."""
    print("\nTesting API Server...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("✓ API server is running")
                return True
            else:
                print(f"✗ API server returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ API server test failed: {e}")
        print("  Make sure the server is running: uvicorn app.main:app --reload")
        return False

async def main():
    """Run all tests."""
    print("RedBarSushiAI System Test")
    print("========================\n")
    
    # Load .env file if it exists
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ Loaded .env file")
    else:
        print("⚠️  No .env file found")
    
    results = []
    
    # Test environment
    results.append(("Environment", test_environment()))
    
    # Test database
    results.append(("Database", await test_database()))
    
    # Test Redis
    results.append(("Redis", await test_redis()))
    
    # Test API
    results.append(("API", await test_api()))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ All tests passed! The system is ready for E2E testing.")
        print("\nNext steps:")
        print("1. Configure your Twilio phone number webhook")
        print("2. Make a test call to your Twilio number")
        print("3. Check logs: docker-compose logs -f app")
    else:
        print("\n❌ Some tests failed. Please fix the issues above before proceeding.")
        print("\nCommon fixes:")
        print("- Make sure PostgreSQL and Redis are running")
        print("- Run 'python init_db.py' to create database tables")
        print("- Check your .env file has all required variables")
        print("- Start the API server: uvicorn app.main:app --reload")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)