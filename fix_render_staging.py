#!/usr/bin/env python
"""
Fix environment issues for RedBarSushiAI on Render's staging environment.
Specifically addresses Redis connection and X11 display issues.
"""

import os
import sys
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("render_fix")

def fix_redis_for_render():
    """Fix Redis connection for Render's staging environment."""
    logger.info("Fixing Redis connection for Render environment")
    
    # Render-specific Redis connection
    redis_host = "red-ceqpb6rf1sgc739ut8e0"
    redis_port = "6379"
    
    # Set environment variables
    os.environ["REDIS_URL"] = f"redis://{redis_host}:{redis_port}/0"
    os.environ["CELERY_BROKER_URL"] = f"redis://{redis_host}:{redis_port}/1"
    os.environ["CELERY_RESULT_BACKEND"] = f"redis://{redis_host}:{redis_port}/1"
    
    logger.info(f"Set REDIS_URL to: {os.environ['REDIS_URL']}")
    logger.info(f"Set CELERY_BROKER_URL to: {os.environ['CELERY_BROKER_URL']}")
    logger.info(f"Set CELERY_RESULT_BACKEND to: {os.environ['CELERY_RESULT_BACKEND']}")
    
    # Create a JSON file with Redis settings
    settings = {
        "REDIS_URL": os.environ["REDIS_URL"],
        "CELERY_BROKER_URL": os.environ["CELERY_BROKER_URL"],
        "CELERY_RESULT_BACKEND": os.environ["CELERY_RESULT_BACKEND"]
    }
    
    with open("/app/redis_settings.json", "w") as f:
        json.dump(settings, f, indent=2)
    
    logger.info("Created Redis settings JSON file at /app/redis_settings.json")
    
    # Create a shell script to load these environment variables
    with open("/app/redis_env.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f'export REDIS_URL="{os.environ["REDIS_URL"]}"\n')
        f.write(f'export CELERY_BROKER_URL="{os.environ["CELERY_BROKER_URL"]}"\n')
        f.write(f'export CELERY_RESULT_BACKEND="{os.environ["CELERY_RESULT_BACKEND"]}"\n')
    
    os.chmod("/app/redis_env.sh", 0o755)
    logger.info("Created Redis environment script at /app/redis_env.sh")
    
    return True

def fix_x11_for_render():
    """Configure X11 environment for Render."""
    logger.info("Setting up X11 display environment for Render")
    
    # For Render, we'll use headless mode since X11 isn't available
    x11_env = {
        "PYNPUT_HEADLESS": "1",
        "NO_X11": "1",
        "HEADLESS": "1",
        "OPENAI_REALTIME_NO_DISPLAY": "1",
        "X11_SETUP_SUCCESS": "false",
        "OPENAI_REALTIME_AVAILABLE": "1",  # Still mark as available for fallback implementation
        "USE_DIRECT_WEBSOCKET": "true"
    }
    
    # Set environment variables
    for key, value in x11_env.items():
        os.environ[key] = value
        logger.info(f"Set {key} to {value}")
    
    # If DISPLAY is set, unset it
    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]
        logger.info("Unset DISPLAY environment variable")
    
    # Create a JSON file with X11 settings
    with open("/app/x11_settings.json", "w") as f:
        json.dump(x11_env, f, indent=2)
    
    logger.info("Created X11 settings JSON file at /app/x11_settings.json")
    
    # Create a shell script to load these environment variables
    with open("/app/x11_env.sh", "w") as f:
        f.write("#!/bin/bash\n")
        for key, value in x11_env.items():
            f.write(f'export {key}="{value}"\n')
        f.write("# Unset DISPLAY to prevent X11 connection attempts\n")
        f.write("unset DISPLAY\n")
    
    os.chmod("/app/x11_env.sh", 0o755)
    logger.info("Created X11 environment script at /app/x11_env.sh")
    
    return True

def fix_logger_initialization():
    """Fix the logger initialization issue in app/__init__.py."""
    logger.info("Fixing logger initialization in app/__init__.py")
    
    try:
        # Path to the init file
        init_file = "/app/app/__init__.py"
        
        if not os.path.exists(init_file):
            logger.warning(f"File not found: {init_file}")
            return False
        
        # Read the file
        with open(init_file, "r") as f:
            content = f.read()
        
        # Replace the logger reference with app_logger
        if "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")" in content:
            logger.info("Found logger reference to fix")
            
            # Replace the logger references
            new_content = content.replace(
                "logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")",
                "app_logger = logging.getLogger(__name__)\n    app_logger.info(f\"Configuring voice handler: {VOICE_HANDLER}\")"
            )
            
            # Replace other logger references in the same section
            new_content = new_content.replace(
                "logger.info(\"Voice handler set to ORCHESTRATED",
                "app_logger.info(\"Voice handler set to ORCHESTRATED"
            )
            new_content = new_content.replace(
                "logger.info(\"Voice handler set to STANDARD",
                "app_logger.info(\"Voice handler set to STANDARD"
            )
            
            # Write the updated content
            with open(init_file, "w") as f:
                f.write(new_content)
            
            logger.info("Successfully fixed logger initialization in app/__init__.py")
            return True
        else:
            logger.info("No logger reference to fix in app/__init__.py")
            return True
    except Exception as e:
        logger.error(f"Error fixing logger initialization: {str(e)}")
        return False

def create_env_init_script():
    """Create a script to initialize the environment on Render startup."""
    logger.info("Creating environment initialization script")
    
    script_content = """#!/bin/bash
# Initialize environment for RedBarSushiAI on Render
# This script runs on container startup

# Source Redis environment variables
if [ -f "/app/redis_env.sh" ]; then
    source /app/redis_env.sh
    echo "✅ Redis environment variables loaded"
fi

# Source X11 environment variables
if [ -f "/app/x11_env.sh" ]; then
    source /app/x11_env.sh
    echo "✅ X11 environment variables loaded"
fi

# Set OpenAI Realtime environment
export OPENAI_REALTIME_AVAILABLE=1
export USE_DIRECT_WEBSOCKET=true

# Log setup
echo "Environment initialized for Render staging"
echo "REDIS_URL: $REDIS_URL"
echo "HEADLESS: $HEADLESS"
echo "OPENAI_REALTIME_AVAILABLE: $OPENAI_REALTIME_AVAILABLE"

# Continue with normal startup
exec "$@"
"""
    
    script_path = "/app/render_init.sh"
    with open(script_path, "w") as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    logger.info(f"Created environment initialization script at {script_path}")
    
    # Update render.yaml if found
    render_yaml_path = "/app/render.yaml"
    if os.path.exists(render_yaml_path):
        try:
            with open(render_yaml_path, "r") as f:
                render_yaml = f.read()
            
            # Check if we need to update the startCommand
            if "startCommand:" in render_yaml and "render_init.sh" not in render_yaml:
                # Find the startCommand line
                lines = render_yaml.split("\n")
                for i, line in enumerate(lines):
                    if "startCommand:" in line:
                        # Replace with our wrapper
                        indent = line.split("startCommand:")[0]
                        lines[i] = f"{indent}startCommand: ./render_init.sh {line.split('startCommand:')[1].strip()}"
                        break
                
                # Write the updated yaml
                with open(render_yaml_path, "w") as f:
                    f.write("\n".join(lines))
                
                logger.info("Updated render.yaml to use the initialization script")
        except Exception as e:
            logger.error(f"Error updating render.yaml: {str(e)}")
    
    return True

def main():
    """Main function to fix Render environment."""
    logger.info("Starting Render environment fix")
    
    # Check if running on Render
    is_render = os.environ.get("RENDER") == "true" or os.environ.get("RENDER_SERVICE_ID")
    logger.info(f"Running on Render: {bool(is_render)}")
    
    # Create output directories if they don't exist
    os.makedirs("/app", exist_ok=True)
    
    # Fix Redis connection
    redis_success = fix_redis_for_render()
    
    # Fix X11 configuration
    x11_success = fix_x11_for_render()
    
    # Fix logger initialization
    logger_success = fix_logger_initialization()
    
    # Create environment initialization script
    init_success = create_env_init_script()
    
    # Summary
    logger.info("\n=== Fix Summary ===")
    logger.info(f"Redis connection fix: {'✅ Success' if redis_success else '❌ Failed'}")
    logger.info(f"X11 configuration fix: {'✅ Success' if x11_success else '❌ Failed'}")
    logger.info(f"Logger initialization fix: {'✅ Success' if logger_success else '❌ Failed'}")
    logger.info(f"Environment init script: {'✅ Success' if init_success else '❌ Failed'}")
    
    if redis_success and x11_success and logger_success and init_success:
        logger.info("✅ All fixes completed successfully")
        return True
    else:
        logger.warning("⚠️ Some fixes were not completed successfully")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)