import asyncio
from sqlalchemy import text
from app.db_async import engine

async def check_tables():
    async with engine.begin() as conn:
        # Get all tables
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        
        print("Tables in database:")
        for row in result:
            print(f"  - {row[0]}")
        
        # Check foreign key constraints
        result = await conn.execute(text("""
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_schema = 'public'
            AND (tc.table_name LIKE '%menu%' OR tc.table_name LIKE '%item%' OR tc.table_name LIKE '%modifier%')
            ORDER BY tc.table_name, kcu.column_name
        """))
        
        print("\nForeign key constraints:")
        for row in result:
            print(f"  - {row[0]}.{row[1]} -> {row[2]}.{row[3]} ({row[4]})")

if __name__ == "__main__":
    asyncio.run(check_tables())