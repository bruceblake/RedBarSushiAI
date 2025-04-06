#!/usr/bin/env python
"""
Test script to validate Docker menu file handling in a simulated Docker environment
"""
import os
import sys
import json
import logging

# Set up Docker simulation
os.environ['DOCKER_CONTAINER'] = 'true'

# Create Docker environment marker
try:
    with open('/.dockerenv', 'w') as f:
        pass
except:
    try:
        with open('/tmp/.dockerenv', 'w') as f:
            pass
    except:
        pass

# Set up Docker paths
APP_PATH = '/app'
try:
    os.makedirs(APP_PATH, exist_ok=True)
except:
    APP_PATH = '/tmp/app'
    os.makedirs(APP_PATH, exist_ok=True)

# Copy current menu to Docker path
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    menu_path = os.path.join(current_dir, 'menu_data.json')
    docker_menu_path = os.path.join(APP_PATH, 'menu_data.json')
    
    if os.path.exists(menu_path):
        with open(menu_path, 'r') as src:
            with open(docker_menu_path, 'w') as dst:
                dst.write(src.read())
                print(f"Copied menu to Docker path: {docker_menu_path}")
except Exception as e:
    print(f"Failed to copy menu: {e}")

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_docker_paths():
    """Test if we can properly handle Docker paths"""
    logger.info("Testing Docker path handling")
    
    # Import after setup to ensure Docker environment is detected
    from app.utils.menu_utils import load_menu_data, DOCKER_ROOT, DOCKER_MENU_PATH
    
    # Check for Docker environment
    in_docker = os.path.exists('/.dockerenv') or os.path.exists('/tmp/.dockerenv')
    docker_env = os.environ.get('DOCKER_CONTAINER') == 'true'
    logger.info(f"Docker detection: exists: {in_docker}, env var: {docker_env}")
    
    # Check for menu file in Docker location
    docker_path_exists = os.path.exists(DOCKER_MENU_PATH)
    logger.info(f"Docker menu path {DOCKER_MENU_PATH} exists: {docker_path_exists}")
    
    # Check current directory
    cwd = os.getcwd()
    logger.info(f"Current working directory: {cwd}")
    
    # Test menu file loading
    menu = load_menu_data(force_refresh=True)
    logger.info(f"Loaded menu with {len(menu.get('items', []))} items")
    
    # Return success status
    return len(menu.get('items', [])) > 0

if __name__ == "__main__":
    success = test_docker_paths()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    exit(0 if success else 1)