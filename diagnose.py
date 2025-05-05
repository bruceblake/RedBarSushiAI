#!/usr/bin/env python3
"""
Diagnostics script for RedBarSushiAI Docker environment.
This script checks for common issues and tries to fix them.
"""

import os
import sys
import subprocess
import json
import importlib
from pathlib import Path

def print_header(text):
    """Print a header with decoration."""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_success(text):
    """Print a success message."""
    print(f"✅ {text}")

def print_warning(text):
    """Print a warning message."""
    print(f"⚠️ {text}")

def print_error(text):
    """Print an error message."""
    print(f"❌ {text}")

def check_environment_variables():
    """Check essential environment variables."""
    print_header("CHECKING ENVIRONMENT VARIABLES")
    
    essential_vars = [
        ("DATABASE_URL", "Database connection string"),
        ("REDIS_URL", "Redis connection string"),
        ("OPENAI_API_KEY", "OpenAI API key"),
        ("FLASK_APP", "Flask application entry point"),
        ("DISPLAY", "X11 display for OpenAI Realtime client")
    ]
    
    all_good = True
    for var, description in essential_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if var == "OPENAI_API_KEY" and len(value) > 8:
                masked_value = f"{value[:4]}...{value[-4:]}"
            elif "password" in var.lower() or "_url" in var.lower():
                masked_value = "********" 
            else:
                masked_value = value
            print_success(f"{var}: {masked_value}")
        else:
            print_error(f"{var} not set - {description} is required")
            all_good = False
    
    return all_good

def check_x11_display():
    """Check if X11 display is working."""
    print_header("CHECKING X11 DISPLAY")
    
    display = os.environ.get("DISPLAY")
    if not display:
        print_error("DISPLAY environment variable not set")
        return False
    
    print(f"DISPLAY set to: {display}")
    
    try:
        result = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"X11 display {display} is working")
            print(f"Display information: {result.stdout.splitlines()[0]}")
            return True
        else:
            print_error(f"X11 display {display} is not working: {result.stderr}")
            return False
    except FileNotFoundError:
        print_error("xdpyinfo not found. X11 utilities may not be installed.")
        return False

def check_database_connection():
    """Check database connection."""
    print_header("CHECKING DATABASE CONNECTION")
    
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
    if not db_url:
        print_error("No database URL found in environment variables")
        return False
    
    try:
        # Extract and display database info without password
        print("Checking database connection...")
        if "postgresql" in db_url:
            # Show parts of the connection string without revealing password
            parts = db_url.split('@')
            if len(parts) > 1:
                auth_parts = parts[0].split(':')
                if len(auth_parts) > 1:
                    username = auth_parts[-2].split('/')[-1]
                    print(f"User: {username}")
                    host_part = parts[1].split('/')[0]
                    print(f"Host: {host_part}")
        
        # Try to import SQLAlchemy
        import sqlalchemy
        print(f"SQLAlchemy version: {sqlalchemy.__version__}")
        
        # Create engine and test connection
        from sqlalchemy import create_engine
        engine = create_engine(db_url)
        connection = engine.connect()
        connection.close()
        print_success("Successfully connected to database")
        return True
    except ImportError:
        print_error("SQLAlchemy not installed. Please install it with: pip install sqlalchemy")
        return False
    except Exception as e:
        print_error(f"Failed to connect to database: {str(e)}")
        return False

def check_redis_connection():
    """Check Redis connection."""
    print_header("CHECKING REDIS CONNECTION")
    
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        print_error("REDIS_URL not set in environment variables")
        return False
    
    print(f"Redis URL: {redis_url}")
    
    try:
        import redis
        print(f"Redis client version: {redis.__version__}")
        
        # Connect to Redis
        r = redis.from_url(redis_url)
        # Test connection with ping
        response = r.ping()
        if response:
            print_success("Successfully connected to Redis")
            return True
        else:
            print_error("Redis ping failed")
            return False
    except ImportError:
        print_error("Redis client not installed. Please install it with: pip install redis")
        return False
    except Exception as e:
        print_error(f"Failed to connect to Redis: {str(e)}")
        return False

def check_openai_sdk():
    """Check OpenAI SDK."""
    print_header("CHECKING OPENAI SDK")
    
    try:
        import openai
        print(f"OpenAI SDK version: {openai.__version__}")
        
        # Make sure we have the API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print_error("OPENAI_API_KEY not set in environment variables")
            return False
        
        # Check if OpenAI Realtime client is available
        try:
            import openai_realtime_client
            print_success(f"OpenAI Realtime client version: {openai_realtime_client.__version__}")
            
            # Check for known issues
            if os.environ.get("OPENAI_REALTIME_NO_DISPLAY") == "1":
                print_warning("OpenAI Realtime client is in headless mode (no X11 display)")
            elif not os.environ.get("DISPLAY"):
                print_warning("DISPLAY environment variable not set for OpenAI Realtime client")
            
        except ImportError:
            print_warning("OpenAI Realtime client not installed. Some features may not work.")
            print("Install with: pip install openai-realtime-client==0.1.0")
        
        return True
    except ImportError:
        print_error("OpenAI SDK not installed. Please install it with: pip install openai")
        return False
    except Exception as e:
        print_error(f"Error checking OpenAI SDK: {str(e)}")
        return False

def check_menu_data():
    """Check menu data file."""
    print_header("CHECKING MENU DATA")
    
    # Check multiple locations where menu_data.json might be
    locations = [
        "/app/menu_data.json",
        "./menu_data.json",
        os.path.join(os.getcwd(), "menu_data.json")
    ]
    
    found = False
    for location in locations:
        if os.path.exists(location):
            print_success(f"Found menu data at {location}")
            
            # Validate the JSON structure
            try:
                with open(location, 'r') as f:
                    menu_data = json.load(f)
                
                required_keys = ['categories', 'products', 'modifierGroups', 'modifiers']
                missing_keys = [key for key in required_keys if key not in menu_data]
                
                if missing_keys:
                    print_error(f"Menu data is missing required keys: {', '.join(missing_keys)}")
                else:
                    print_success("Menu data has all required sections")
                    
                    # Check for some basic content
                    print(f"Categories: {len(menu_data.get('categories', {}))} entries")
                    print(f"Products: {len(menu_data.get('products', {}))} entries")
                    print(f"Modifier Groups: {len(menu_data.get('modifierGroups', {}))} entries")
                    print(f"Modifiers: {len(menu_data.get('modifiers', {}))} entries")
                    
                    variants = menu_data.get('menuNameVariants', [])
                    print(f"Menu Name Variants: {len(variants)} entries")
                    
                    if all(len(menu_data.get(k, {})) > 0 for k in required_keys) and len(variants) > 0:
                        print_success("Menu data appears to be valid and contains entries")
                    else:
                        print_warning("Menu data may be incomplete (empty sections detected)")
                
            except json.JSONDecodeError:
                print_error(f"Menu data at {location} is not valid JSON")
            except Exception as e:
                print_error(f"Error validating menu data: {str(e)}")
                
            found = True
            break
    
    if not found:
        print_error("Menu data file not found in any of the expected locations")
        
        # Create a basic menu data file if it doesn't exist
        create_new = True
        if create_new:
            target_path = os.path.join(os.getcwd(), "menu_data.json")
            try:
                # Check if we have a menu_data.json in the current directory to copy
                if os.path.exists("menu_data.json"):
                    # Copy it to the /app directory in Docker
                    subprocess.run(["cp", "menu_data.json", "/app/menu_data.json"], check=True)
                    print_success("Copied existing menu_data.json to /app/menu_data.json")
                    return True
                    
                # Otherwise create a basic template
                basic_menu = {
                    "categories": {
                        "sample_category": {
                            "_id": "sample_category",
                            "name": "Sample Category", 
                            "subProducts": ["sample_item"]
                        }
                    },
                    "products": {
                        "sample_item": {
                            "_id": "sample_item",
                            "name": "Sample Item",
                            "price": 1000,
                            "plu": "SAMPLE-ITEM",
                            "description": "A sample menu item",
                            "subProducts": []
                        }
                    },
                    "modifierGroups": {},
                    "modifiers": {},
                    "menuNameVariants": [
                        {
                            "variant_phrase": "sample item",
                            "canonical_name": "Sample Item",
                            "target_plu": "SAMPLE-ITEM"
                        }
                    ]
                }
                
                with open(target_path, 'w') as f:
                    json.dump(basic_menu, f, indent=2)
                
                # Also create in /app for Docker
                app_path = "/app/menu_data.json"
                with open(app_path, 'w') as f:
                    json.dump(basic_menu, f, indent=2)
                    
                print_success(f"Created basic menu data file at {target_path} and {app_path}")
                return True
            except Exception as e:
                print_error(f"Failed to create menu data file: {str(e)}")
                return False
    
    return found

def check_app_utils_agent_utils():
    """Check the agent_utils module for the OPENAI_API_KEY import."""
    print_header("CHECKING app.utils.agent_utils MODULE")
    
    try:
        # Try to import the module
        from app.utils.agent_utils import OPENAI_API_KEY
        print_success("Successfully imported OPENAI_API_KEY from app.utils.agent_utils")
        return True
    except ImportError as e:
        if str(e) == "cannot import name 'OPENAI_API_KEY' from 'app.utils.agent_utils'":
            # Fix the issue by adding OPENAI_API_KEY to the __init__.py file
            try:
                init_path = None
                # Find the __init__.py file
                possible_paths = [
                    "/app/app/utils/agent_utils/__init__.py",
                    os.path.join(os.getcwd(), "app/utils/agent_utils/__init__.py")
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        init_path = path
                        break
                
                if init_path:
                    print(f"Found __init__.py file at {init_path}")
                    
                    # Read the current content
                    with open(init_path, 'r') as f:
                        content = f.read()
                    
                    # Check if the file already contains the import
                    if "OPENAI_API_KEY" in content:
                        print_warning("OPENAI_API_KEY is defined in the file but couldn't be imported")
                    else:
                        # Add the OPENAI_API_KEY import at the beginning
                        new_content = '"""\nAgent utility functions for handling OpenAI Agents integration.\nThis module provides the core functionality for our AI agents.\n"""\n\n# Import required modules\nimport os\n\n# Export OpenAI API key from environment\nOPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")\n\n' + content
                        
                        # Write the updated content
                        with open(init_path, 'w') as f:
                            f.write(new_content)
                        
                        print_success("Added OPENAI_API_KEY to app.utils.agent_utils.__init__")
                        
                        # Update __all__ to include OPENAI_API_KEY
                        if "__all__" in content and "OPENAI_API_KEY" not in content:
                            # Find the __all__ list
                            start = content.find("__all__")
                            if start != -1:
                                # Find the opening bracket
                                open_bracket = content.find("[", start)
                                if open_bracket != -1:
                                    # Insert OPENAI_API_KEY as the first item
                                    new_content = content[:open_bracket+1] + "\n    # Environment variables\n    'OPENAI_API_KEY',\n    " + content[open_bracket+1:]
                                    
                                    # Write the updated content
                                    with open(init_path, 'w') as f:
                                        f.write(new_content)
                                    
                                    print_success("Added OPENAI_API_KEY to __all__ list")
                    
                    # Try importing again
                    try:
                        # Clear the module from cache
                        if "app.utils.agent_utils" in sys.modules:
                            del sys.modules["app.utils.agent_utils"]
                        
                        # Try importing again
                        from app.utils.agent_utils import OPENAI_API_KEY
                        print_success("Successfully imported OPENAI_API_KEY from app.utils.agent_utils after fix")
                        return True
                    except ImportError as e:
                        print_error(f"Still cannot import OPENAI_API_KEY: {str(e)}")
                        return False
                else:
                    print_error("Could not find app/utils/agent_utils/__init__.py file")
                    return False
            except Exception as e:
                print_error(f"Failed to fix agent_utils.__init__: {str(e)}")
                return False
        else:
            print_error(f"Failed to import app.utils.agent_utils: {str(e)}")
            return False
    except Exception as e:
        print_error(f"Error checking app.utils.agent_utils: {str(e)}")
        return False

def fix_x_server():
    """Try to fix X server issues."""
    print_header("FIXING X SERVER")
    
    if check_x11_display():
        print_success("X server is already working")
        return True
    
    print("Attempting to fix X server issues...")
    
    try:
        # Check if Xvfb is installed
        result = subprocess.run(["which", "Xvfb"], capture_output=True, text=True)
        if result.returncode != 0:
            print("Installing Xvfb...")
            subprocess.run(["apt-get", "update"], check=True)
            subprocess.run(["apt-get", "install", "-y", "xvfb", "x11-utils", "dbus-x11"], check=True)
        
        # Find a free display number
        for display_num in [1, 2, 3, 4, 5, 99, 0]:
            print(f"Trying display :{display_num}...")
            
            # Check if display is already in use
            if os.path.exists(f"/tmp/.X{display_num}-lock"):
                print(f"Display :{display_num} is already in use")
                continue
            
            # Start Xvfb
            process = subprocess.Popen(
                ["Xvfb", f":{display_num}", "-screen", "0", "1280x720x24", "-ac", "+extension", "GLX", "+render", "-noreset"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for Xvfb to start
            import time
            time.sleep(2)
            
            # Check if Xvfb is running
            if process.poll() is None:
                # Set the DISPLAY environment variable
                os.environ["DISPLAY"] = f":{display_num}"
                
                # Test if the display works
                result = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
                if result.returncode == 0:
                    print_success(f"Successfully started Xvfb on display :{display_num}")
                    
                    # Set other environment variables
                    os.environ["PYNPUT_HEADLESS"] = "0"
                    os.environ["NO_X11"] = "0"
                    os.environ["HEADLESS"] = "0"
                    os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "0"
                    os.environ["X11_SETUP_SUCCESS"] = "true"
                    os.environ["OPENAI_REALTIME_AVAILABLE"] = "1"
                    
                    # Create a file to persist environment variables
                    with open(os.path.expanduser("~/.xdisplay"), "w") as f:
                        f.write(f"export DISPLAY=:{display_num}\n")
                        f.write("export PYNPUT_HEADLESS=0\n")
                        f.write("export NO_X11=0\n")
                        f.write("export HEADLESS=0\n")
                        f.write("export OPENAI_REALTIME_NO_DISPLAY=0\n")
                        f.write("export X11_SETUP_SUCCESS=true\n")
                        f.write("export OPENAI_REALTIME_AVAILABLE=1\n")
                    
                    # Make it executable
                    subprocess.run(["chmod", "+x", os.path.expanduser("~/.xdisplay")])
                    
                    return True
            
            # If we get here, Xvfb failed to start or the display doesn't work
            if process.poll() is None:
                # Xvfb is running but the display doesn't work
                process.terminate()
        
        # If we get here, all display attempts failed
        print_error("Could not start Xvfb on any display")
        
        # Set headless mode
        os.environ["PYNPUT_HEADLESS"] = "1"
        os.environ["NO_X11"] = "1"
        os.environ["HEADLESS"] = "1"
        os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
        
        print_warning("Falling back to headless mode for OpenAI Realtime client")
        return False
    except Exception as e:
        print_error(f"Failed to fix X server: {str(e)}")
        return False

def main():
    """Run all checks and report results."""
    print_header("REDBARSUSHIAI ENVIRONMENT DIAGNOSTICS")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    
    # Run checks
    env_check = check_environment_variables()
    x11_check = check_x11_display()
    db_check = check_database_connection()
    redis_check = check_redis_connection()
    openai_check = check_openai_sdk()
    menu_check = check_menu_data()
    agent_utils_check = check_app_utils_agent_utils()
    
    # Try to fix X server if it's not working
    if not x11_check:
        x11_fixed = fix_x_server()
        if x11_fixed:
            print_success("Fixed X server issues")
            x11_check = True
    
    # Report summary
    print_header("DIAGNOSTICS SUMMARY")
    checks = [
        ("Environment Variables", env_check),
        ("X11 Display", x11_check),
        ("Database Connection", db_check),
        ("Redis Connection", redis_check),
        ("OpenAI SDK", openai_check),
        ("Menu Data", menu_check),
        ("Agent Utils Module", agent_utils_check)
    ]
    
    for name, result in checks:
        if result:
            print_success(f"{name}: OK")
        else:
            print_error(f"{name}: FAILED")
    
    overall = all(result for _, result in checks)
    if overall:
        print_success("All checks passed. The environment is ready.")
    else:
        print_error("Some checks failed. Please fix the issues before running the application.")

if __name__ == "__main__":
    main()