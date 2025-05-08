#!/usr/bin/env python3
"""
Verify Docker environment for RedBarSushiAI
"""

import redis
import psycopg2
import json
import sys
import time
import subprocess
import os

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 50)
    print(f" {title}")
    print("=" * 50)

def check_containers():
    """Check if Docker containers are running"""
    print_section("Checking Docker Containers")
    
    try:
        # Run docker ps command to check running containers
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} ({{.Status}})"],
            capture_output=True,
            text=True,
            check=True
        )
        
        containers = result.stdout.strip().split('\n')
        for container in containers:
            if container:
                print(f"✓ {container}")
        
        # Check if required containers are running
        required = ["redbarsushi_postgres", "redbarsushi_redis"]
        running = [c.split()[0] for c in containers if c]
        
        missing = [r for r in required if r not in running]
        if missing:
            print(f"\n⚠️ Missing required containers: {', '.join(missing)}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Error checking containers: {e}")
        return False

def test_redis():
    """Test Redis connectivity"""
    print_section("Testing Redis Connection")
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        if r.ping():
            print("✓ Successfully connected to Redis")
            
            # Test setting and getting a value
            test_key = "redbar:test:key"
            test_value = f"Test value at {time.time()}"
            r.set(test_key, test_value)
            retrieved = r.get(test_key)
            
            if retrieved.decode('utf-8') == test_value:
                print(f"✓ Successfully set and retrieved test value")
                # Clean up
                r.delete(test_key)
                return True
            else:
                print(f"❌ Value mismatch: expected '{test_value}', got '{retrieved.decode('utf-8')}'")
                return False
        else:
            print("❌ Redis ping failed")
            return False
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_postgres():
    """Test PostgreSQL connectivity"""
    print_section("Testing PostgreSQL Connection")
    
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='redbarsushi_staging_db',
            user='redbarsushi_staging_db_user',
            password='testing_password'
        )
        
        print("✓ Successfully connected to PostgreSQL")
        
        # Check if we can execute queries
        cursor = conn.cursor()
        
        # Get PostgreSQL version
        cursor.execute('SELECT version();')
        version = cursor.fetchone()
        print(f"✓ PostgreSQL version: {version[0]}")
        
        # Check database tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        if tables:
            print(f"✓ Found {len(tables)} tables in database:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("⚠️ No tables found in database")
            
            # Initialize the database schema if needed
            print("\nWould you like to initialize the database schema? (y/n)")
            choice = input().lower()
            if choice == 'y':
                try:
                    # Run the initialization scripts
                    sql_path = os.path.join(os.getcwd(), "mcp/db/init")
                    schema_file = os.path.join(sql_path, "01_schema.sql")
                    seed_file = os.path.join(sql_path, "02_seed_data.sql")
                    
                    if os.path.exists(schema_file) and os.path.exists(seed_file):
                        # Initialize schema
                        with open(schema_file, 'r') as f:
                            sql = f.read()
                            cursor.execute(sql)
                            conn.commit()
                        print("✓ Initialized database schema")
                        
                        # Load seed data
                        with open(seed_file, 'r') as f:
                            sql = f.read()
                            cursor.execute(sql)
                            conn.commit()
                        print("✓ Loaded seed data")
                        
                        # Verify tables were created
                        cursor.execute("""
                            SELECT table_name 
                            FROM information_schema.tables 
                            WHERE table_schema = 'public'
                            ORDER BY table_name;
                        """)
                        
                        tables = cursor.fetchall()
                        print(f"✓ Now have {len(tables)} tables in database")
                    else:
                        print(f"❌ SQL initialization files not found in {sql_path}")
                except Exception as e:
                    print(f"❌ Failed to initialize database: {e}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def main():
    """Run all tests"""
    containers_ok = check_containers()
    redis_ok = test_redis()
    postgres_ok = test_postgres()
    
    print_section("Summary")
    print(f"Containers: {'✓' if containers_ok else '❌'}")
    print(f"Redis:      {'✓' if redis_ok else '❌'}")
    print(f"PostgreSQL: {'✓' if postgres_ok else '❌'}")
    
    if containers_ok and redis_ok and postgres_ok:
        print("\n✅ Docker environment is ready for MCP testing!")
        return 0
    else:
        print("\n⚠️ Some components failed verification. See details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())