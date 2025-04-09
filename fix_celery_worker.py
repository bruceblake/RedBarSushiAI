#!/usr/bin/env python
"""
Utility script to diagnose and fix Celery worker issues on Render.com

This script:
1. Tests connections to Redis
2. Checks if Celery worker is running
3. Validates task registration
4. Provides manual commands to restart Celery services
5. Creates a local test Celery worker for debugging

Usage:
  python fix_celery_worker.py --action check
  python fix_celery_worker.py --action test
  python fix_celery_worker.py --action local
"""

import argparse
import os
import sys
import subprocess
import json
import time
import traceback

def check_redis_connection(url=None):
    """Check if Redis is available and functioning."""
    if not url:
        url = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL'))
    
    if not url:
        print("❌ No Redis URL found in environment variables")
        return False
    
    try:
        import redis
        # Extract credentials and host info without printing the full URL
        redacted_url = url
        if '@' in url:
            # Redact password if present
            auth, rest = url.split('@', 1)
            protocol_user = auth.rsplit(':', 1)[0]
            redacted_url = f"{protocol_user}:****@{rest}"
        
        print(f"📡 Testing connection to Redis at {redacted_url}")
        
        # Parse the Redis URL
        if '://' not in url and ':' in url:
            # Handle simplified Render format (host:port/db)
            if '/' in url:
                host_port, db = url.rsplit('/', 1)
                host, port = host_port.split(':')
                # Make sure DB is a number
                try:
                    db_num = int(db)
                except ValueError:
                    db_num = 0
                # Construct proper Redis URL
                url = f"redis://{host}:{port}/{db_num}"
            else:
                # Just prefix with redis://
                url = f"redis://{url}"
        
        # Ensure the URL has the proper redis:// prefix
        if not url.startswith('redis://'):
            url = f"redis://{url}"
        
        # Connect to Redis
        r = redis.from_url(url, socket_timeout=5.0)
        ping_result = r.ping()
        
        if ping_result:
            print("✅ Successfully connected to Redis!")
            # Test setting and getting a value
            test_key = "celery_test_key"
            test_value = f"test_{int(time.time())}"
            r.setex(test_key, 60, test_value)  # expires in 60 seconds
            read_value = r.get(test_key)
            
            if read_value and read_value.decode('utf-8') == test_value:
                print("✅ Successfully set and retrieved a test value from Redis")
                return True
            else:
                print("❌ Failed to set or retrieve test value from Redis")
                return False
        else:
            print("❌ Failed to ping Redis server")
            return False
    except ImportError:
        print("❌ Redis package not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "redis"])
            print("✅ Redis package installed. Please run the script again.")
        except Exception as e:
            print(f"❌ Failed to install Redis package: {e}")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        traceback.print_exc()
        return False

def check_celery_installed():
    """Check if Celery is installed."""
    try:
        import celery
        print(f"✅ Celery is installed (version {celery.__version__})")
        return True
    except ImportError:
        print("❌ Celery is not installed.")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "celery"])
            print("✅ Celery installed. Please run the script again.")
        except Exception as e:
            print(f"❌ Failed to install Celery: {e}")
        return False

def check_celery_tasks():
    """Check if Celery tasks are properly registered."""
    try:
        sys.path.insert(0, os.getcwd())
        
        # First check if celery_app.py exists
        if not os.path.exists("celery_app.py"):
            print("❌ celery_app.py not found in current directory")
            return False
        
        # Then check if tasks.py exists
        if not os.path.exists("tasks.py"):
            print("❌ tasks.py not found in current directory")
            return False
            
        # Try to import the Celery app
        print("Importing the Celery application...")
        try:
            from celery_app import celery
            print("✅ Successfully imported Celery application")
            
            # List registered tasks
            print("\n📋 Registered tasks:")
            for task_name in sorted(celery.tasks.keys()):
                if not task_name.startswith('celery.'):
                    print(f"  - {task_name}")
            
            # Check for the specific task having issues
            if 'tasks.send_order_status_update_task' in celery.tasks:
                print("✅ send_order_status_update_task is properly registered")
            else:
                print("❌ send_order_status_update_task is NOT registered!")
                
            return True
        except Exception as e:
            print(f"❌ Error importing Celery application: {e}")
            traceback.print_exc()
            return False
    except Exception as e:
        print(f"❌ Error checking Celery tasks: {e}")
        traceback.print_exc()
        return False

def check_redis_configuration():
    """Check Redis configuration in files."""
    print("\n🔍 Checking Redis configuration in files...")
    
    # Check app/config.py
    if os.path.exists("app/config.py"):
        try:
            with open("app/config.py", "r") as f:
                config_content = f.read()
                if "REDIS_URL" in config_content:
                    print("✅ REDIS_URL found in app/config.py")
                    import re
                    match = re.search(r'REDIS_URL\s*=\s*[\'"]([^\'"]+)[\'"]', config_content)
                    if match:
                        print(f"   Value: {match.group(1)}")
                else:
                    print("❌ REDIS_URL not found in app/config.py")
        except Exception as e:
            print(f"❌ Error reading app/config.py: {e}")
    
    # Check celery_app.py
    if os.path.exists("celery_app.py"):
        try:
            with open("celery_app.py", "r") as f:
                celery_content = f.read()
                if "broker_url" in celery_content and "result_backend" in celery_content:
                    print("✅ broker_url and result_backend found in celery_app.py")
                else:
                    print("❌ Missing broker_url or result_backend in celery_app.py")
        except Exception as e:
            print(f"❌ Error reading celery_app.py: {e}")
    
    # Check .env file
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                env_content = f.read()
                if "REDIS_URL" in env_content:
                    print("✅ REDIS_URL found in .env")
                else:
                    print("❌ REDIS_URL not found in .env")
                
                if "CELERY_BROKER_URL" in env_content:
                    print("✅ CELERY_BROKER_URL found in .env")
                else:
                    print("❌ CELERY_BROKER_URL not found in .env")
                
                if "CELERY_RESULT_BACKEND" in env_content:
                    print("✅ CELERY_RESULT_BACKEND found in .env")
                else:
                    print("❌ CELERY_RESULT_BACKEND not found in .env")
        except Exception as e:
            print(f"❌ Error reading .env: {e}")

def generate_render_commands():
    """Generate commands to restart Celery worker on Render."""
    print("\n🛠️ Render CLI commands to fix the Celery worker:")
    print("\n1. First, log in to Render (if not already logged in):")
    print("   render login")
    
    print("\n2. List all your services to find the Celery worker service ID:")
    print("   render services list")
    
    print("\n3. Restart the Celery worker service:")
    print("   render services restart srv-YOUR_CELERY_SERVICE_ID")
    
    print("\n4. Check the logs to verify it's working:")
    print("   render logs srv-YOUR_CELERY_SERVICE_ID")
    
    print("\n5. If you need to update environment variables:")
    print("   a. Go to the Render dashboard")
    print("   b. Navigate to your Celery worker service")
    print("   c. Click on 'Environment' tab")
    print("   d. Set or update these variables:")
    print("      REDIS_URL=redis://your-redis-host:port/0")
    print("      CELERY_BROKER_URL=redis://your-redis-host:port/0")
    print("      CELERY_RESULT_BACKEND=redis://your-redis-host:port/0")
    print("      PROCESS=celery")
    
    print("\nNote: Replace 'YOUR_CELERY_SERVICE_ID' with the actual service ID from step 2.")

def test_task_execution():
    """Test direct execution of the task that's having issues."""
    print("\n🧪 Testing direct task execution (without Celery)...")
    try:
        # First, make sure we can import the task
        sys.path.insert(0, os.getcwd())
        
        try:
            # Import the task directly
            from tasks import send_order_status_update_task
            print("✅ Successfully imported send_order_status_update_task")
            
            # Get a test order ID from the database
            try:
                print("Connecting to database to find a test order...")
                from app import create_app, db
                from app.models import Order
                
                app = create_app()
                with app.app_context():
                    # Try to find a recent order
                    test_order = db.session.query(Order).order_by(Order.id.desc()).first()
                    
                    if test_order:
                        print(f"✅ Found test order: {test_order.id[:8]}...")
                        
                        # Try to execute the task directly
                        print(f"Executing task directly (without .delay())...")
                        result = send_order_status_update_task(
                            test_order.id,
                            f"Test message from diagnostic script at {time.strftime('%H:%M:%S')}",
                            location_id=test_order.location_id
                        )
                        print(f"✅ Direct task execution successful! Result: {result}")
                        
                        # Now try to use delay (async)
                        print(f"Testing asynchronous task execution with .delay()...")
                        try:
                            # First verify redis connection
                            if not check_redis_connection():
                                print("❌ Cannot test async execution because Redis connection failed")
                                return False
                                
                            # Try async execution
                            async_result = send_order_status_update_task.delay(
                                test_order.id,
                                f"Async test message from diagnostic script at {time.strftime('%H:%M:%S')}",
                                location_id=test_order.location_id
                            )
                            print(f"✅ Task submitted asynchronously with ID: {async_result.id}")
                            print("Note: Check that you received the test SMS message")
                            return True
                        except Exception as e:
                            print(f"❌ Error during async task execution: {e}")
                            traceback.print_exc()
                            return False
                    else:
                        print("❌ No orders found in database to test with")
                        print("  Creating test order for task execution...")
                        test_order_id = f"test-{int(time.time())}"
                        test_message = f"Test order created at {time.strftime('%H:%M:%S')}"
                        
                        # Try direct execution with test data
                        print(f"Executing task directly with test data...")
                        result = send_order_status_update_task(
                            test_order_id,
                            f"Test message from diagnostic script at {time.strftime('%H:%M:%S')}",
                            location_id=None
                        )
                        print(f"✅ Direct task execution successful! Result: {result}")
                        return True
                        
            except Exception as db_error:
                print(f"❌ Database error: {db_error}")
                print("Trying direct task execution with test data instead...")
                
                # Try direct execution with test data
                test_order_id = f"test-{int(time.time())}"
                result = send_order_status_update_task(
                    test_order_id,
                    f"Test message from diagnostic script at {time.strftime('%H:%M:%S')}",
                    location_id=None
                )
                print(f"✅ Direct task execution successful! Result: {result}")
                return True
                
        except ImportError as e:
            print(f"❌ Could not import task: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing task execution: {e}")
        traceback.print_exc()
        return False

def run_local_worker():
    """Start a local Celery worker for testing."""
    print("\n🚀 Starting a local Celery worker for testing...")
    try:
        # Verify Redis connection first
        if not check_redis_connection():
            print("❌ Cannot start worker because Redis connection failed")
            return False
            
        # Check if Celery is installed
        if not check_celery_installed():
            print("❌ Cannot start worker because Celery is not installed")
            return False
            
        # Check if celery_app.py exists
        if not os.path.exists("celery_app.py"):
            print("❌ celery_app.py not found in current directory")
            return False
            
        # Start a Celery worker process
        print("\n🚀 Starting Celery worker (press Ctrl+C to stop)...")
        worker_cmd = [sys.executable, "-m", "celery", "-A", "celery_app", "worker", "--loglevel=INFO"]
        
        try:
            subprocess.call(worker_cmd)
        except KeyboardInterrupt:
            print("\n✅ Celery worker stopped")
        except Exception as e:
            print(f"❌ Error running Celery worker: {e}")
            
        return True
    except Exception as e:
        print(f"❌ Error starting local worker: {e}")
        traceback.print_exc()
        return False

def test_task_with_direct_call():
    """Test the problematic task with a direct call."""
    print("\n🔍 Testing task with direct function call (bypassing Celery)...")
    
    try:
        from celery_app import celery
        print("✅ Successfully imported Celery application")
        
        from tasks import send_order_status_update_task
        print("✅ Successfully imported task function")
        
        # Create test data
        test_order_id = f"test-{int(time.time())}"
        test_message = f"Test message from direct call at {time.strftime('%H:%M:%S')}"
        
        print(f"Executing task function directly...")
        
        # Call the function directly (bypassing .delay())
        result = send_order_status_update_task._orig_run(
            test_order_id,
            test_message,
            location_id=None
        )
        
        print(f"✅ Direct function call successful!")
        print(f"Result: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in direct function call: {e}")
        traceback.print_exc()
        return False

def fix_celery_issues():
    """Attempt to fix common Celery issues automatically."""
    print("\n🔧 Attempting to fix common Celery issues...")
    
    fixed_anything = False
    
    # Check if Redis URLs need to be fixed
    redis_url = os.environ.get('REDIS_URL')
    if redis_url and not redis_url.startswith('redis://'):
        fixed_anything = True
        print("📝 Fixing Redis URL format in .env file...")
        try:
            # Parse Redis URL
            if ':' in redis_url and '/' in redis_url:
                host_port, db = redis_url.rsplit('/', 1)
                host, port = host_port.split(':')
                try:
                    db_num = int(db)
                except ValueError:
                    db_num = 0
                fixed_url = f"redis://{host}:{port}/{db_num}"
            else:
                fixed_url = f"redis://{redis_url}"
                
            # Update the .env file
            if os.path.exists(".env"):
                with open(".env", "r") as f:
                    env_content = f.read()
                
                # Replace the Redis URL
                if "REDIS_URL=" in env_content:
                    new_content = env_content.replace(f"REDIS_URL={redis_url}", f"REDIS_URL={fixed_url}")
                    
                    # Also update CELERY_BROKER_URL and CELERY_RESULT_BACKEND
                    if "CELERY_BROKER_URL=" in new_content:
                        new_content = new_content.replace(f"CELERY_BROKER_URL={redis_url}", 
                                                         f"CELERY_BROKER_URL={fixed_url}")
                    else:
                        new_content += f"\nCELERY_BROKER_URL={fixed_url}"
                        
                    if "CELERY_RESULT_BACKEND=" in new_content:
                        new_content = new_content.replace(f"CELERY_RESULT_BACKEND={redis_url}", 
                                                         f"CELERY_RESULT_BACKEND={fixed_url}")
                    else:
                        new_content += f"\nCELERY_RESULT_BACKEND={fixed_url}"
                    
                    with open(".env", "w") as f:
                        f.write(new_content)
                    
                    print(f"✅ Updated Redis URLs in .env to: {fixed_url}")
                    
                    # Also update environment variables
                    os.environ["REDIS_URL"] = fixed_url
                    os.environ["CELERY_BROKER_URL"] = fixed_url 
                    os.environ["CELERY_RESULT_BACKEND"] = fixed_url
                    print("✅ Updated environment variables with corrected Redis URL")
        except Exception as e:
            print(f"❌ Error fixing Redis URL: {e}")
    
    # Create a fix_celery.sh script for easy deployment to Render
    try:
        with open("fix_celery.sh", "w") as f:
            f.write("""#!/bin/bash
# Script to fix Celery configuration on Render

# Ensure Redis URL is properly formatted
if [ -n "$REDIS_URL" ] && [[ "$REDIS_URL" != redis://* ]]; then
    echo "Fixing Redis URL format..."
    # Extract parts from the URL
    if [[ "$REDIS_URL" == *":"* ]] && [[ "$REDIS_URL" == *"/"* ]]; then
        # Format appears to be hostname:port/db
        HOST_PORT="${REDIS_URL%/*}"
        DB="${REDIS_URL#*/}"
        HOST="${HOST_PORT%:*}"
        PORT="${HOST_PORT#*:}"
        
        # Make sure DB is a number
        if ! [[ "$DB" =~ ^[0-9]+$ ]]; then
            DB=0
        fi
        
        # Construct proper Redis URL
        export REDIS_URL="redis://${HOST}:${PORT}/${DB}"
        export CELERY_BROKER_URL="$REDIS_URL"
        export CELERY_RESULT_BACKEND="$REDIS_URL"
        echo "Fixed Redis URL: ${REDIS_URL}"
    else
        # Just prefix with redis://
        export REDIS_URL="redis://${REDIS_URL}"
        export CELERY_BROKER_URL="$REDIS_URL"
        export CELERY_RESULT_BACKEND="$REDIS_URL"
        echo "Added redis:// prefix to Redis URL: ${REDIS_URL}"
    fi
fi

# Set process type to celery
export PROCESS="celery"

# Start Celery worker with memory optimizations
echo "Starting Celery worker with memory optimizations..."
exec celery -A celery_app worker --loglevel=INFO --concurrency=2 --max-memory-per-child=50000
""")
        os.chmod("fix_celery.sh", 0o755)  # Make executable
        print("✅ Created fix_celery.sh script for deployment to Render")
        fixed_anything = True
    except Exception as e:
        print(f"❌ Error creating fix script: {e}")
    
    # Create a Procfile for Render
    try:
        with open("Procfile", "w") as f:
            f.write("""web: gunicorn --worker-class=gevent --workers=1 --threads=4 'run:app'
worker: celery -A celery_app worker --loglevel=INFO --max-memory-per-child=50000
beat: celery -A celery_app beat --loglevel=INFO
""")
        print("✅ Created Procfile for Render deployment")
        fixed_anything = True
    except Exception as e:
        print(f"❌ Error creating Procfile: {e}")
    
    # If we didn't fix anything specific, provide general advice
    if not fixed_anything:
        print("ℹ️ No automatic fixes were applied. Please try the manual solutions.")
    
    return fixed_anything

def print_render_deployment_instructions():
    """Print instructions for fixing Celery on Render."""
    print("\n📋 Instructions for fixing Celery on Render:")
    print("\n1. 🚀 Create a new Web Service in Render")
    print("   - Connect to your GitHub repository")
    print("   - Set the following:")
    print("     * Name: RedBarSushi-Celery")
    print("     * Environment: Python")
    print("     * Build Command: pip install -r requirements.txt")
    print("     * Start Command: ./fix_celery.sh")
    
    print("\n2. ⚙️ Set environment variables:")
    print("   - REDIS_URL: (Use the same as your web service)")
    print("   - DATABASE_URL: (Use the same as your web service)")
    print("   - PROCESS: celery")
    print("   - PYTHONUNBUFFERED: 1")
    print("   - All other environment variables from your web service")
    
    print("\n3. 📋 Under Advanced settings:")
    print("   - Set Health Check Path to: /")
    print("   - Set Auto-Deploy to: Yes")
    
    print("\n4. 🧪 After deployment, check logs to verify the worker is running properly")
    
    print("\n5. 🔄 Test your SMS functionality again")
    
    print("\nAlternative approach using Render Dashboard:")
    print("1. Log in to your Render dashboard")
    print("2. Create a new Web Service using the same repository")
    print("3. Configure it as described above")
    print("4. Use either fix_celery.sh or set Start Command to: celery -A celery_app worker --loglevel=INFO")

def main():
    parser = argparse.ArgumentParser(description="Fix Celery Worker issues for RedBarSushiAI")
    parser.add_argument('--action', choices=['check', 'test', 'local', 'fix', 'deploy'], 
                      default='check', help='Action to perform')
    parser.add_argument('--redis-url', help='Redis URL to use for testing')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔍 RedBarSushiAI Celery Worker Diagnostics and Fix Tool")
    print("=" * 60)
    
    # Set Python path to include current directory
    sys.path.insert(0, os.getcwd())
    
    if args.action == 'check':
        # Run all diagnostics
        print("\n📋 Running diagnostics...\n")
        redis_ok = check_redis_connection(args.redis_url)
        celery_ok = check_celery_installed()
        tasks_ok = check_celery_tasks()
        check_redis_configuration()
        
        # Print summary
        print("\n📊 Diagnostic Summary:")
        print(f"Redis Connection: {'✅ OK' if redis_ok else '❌ Failed'}")
        print(f"Celery Installation: {'✅ OK' if celery_ok else '❌ Failed'}")
        print(f"Task Registration: {'✅ OK' if tasks_ok else '❌ Issues found'}")
        
        # Generate commands for Render
        generate_render_commands()
        
        # Suggest fixes
        print("\n🔧 Suggested fixes:")
        if not redis_ok:
            print("1. Check Redis connection and credentials")
            print("   - Verify REDIS_URL environment variable is correctly formatted")
            print("   - Make sure Redis server is running")
            print("   - Check network connectivity to Redis server")
        
        if not celery_ok:
            print("2. Install Celery:")
            print("   pip install celery redis")
            
        if not tasks_ok:
            print("3. Check task registration:")
            print("   - Verify tasks.py exists and contains send_order_status_update_task")
            print("   - Make sure celery_app.py properly imports tasks")
            print("   - Restart the Celery worker")
            
        print("\n4. Try running the task directly:")
        print("   python fix_celery_worker.py --action test")
        
        print("\n5. Start a local Celery worker:")
        print("   python fix_celery_worker.py --action local")
        
        print("\n6. Apply automatic fixes:")
        print("   python fix_celery_worker.py --action fix")
            
    elif args.action == 'test':
        # Test task execution
        test_task_execution()
        test_task_with_direct_call()
        
    elif args.action == 'local':
        # Run a local Celery worker
        run_local_worker()
        
    elif args.action == 'fix':
        # Try to fix common issues
        fix_celery_issues()
        
    elif args.action == 'deploy':
        # Print deploy instructions
        print_render_deployment_instructions()
        
    print("\n✅ Done!")

if __name__ == "__main__":
    main()