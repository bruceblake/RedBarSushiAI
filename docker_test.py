#!/usr/bin/env python
"""
Test script to validate Docker menu file handling
"""
import os
import json
import logging

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_docker_paths():
    """Test if we can properly handle Docker paths"""
    logger.info("Testing Docker path handling")
    
    # Check for Docker environment
    in_docker = os.path.exists('/.dockerenv')
    docker_env = os.environ.get('DOCKER_CONTAINER') == 'true'
    logger.info(f"Docker detection: /.dockerenv exists: {in_docker}, DOCKER_CONTAINER env var: {docker_env}")
    
    # Check for menu file in Docker location
    docker_menu_path = '/app/menu_data.json'
    docker_path_exists = os.path.exists(docker_menu_path)
    logger.info(f"Docker menu path {docker_menu_path} exists: {docker_path_exists}")
    
    # Check current directory
    cwd = os.getcwd()
    logger.info(f"Current working directory: {cwd}")
    
    # Test menu file loading
    from app.utils.menu_utils import load_menu_data
    menu = load_menu_data(force_refresh=True)
    logger.info(f"Loaded menu with {len(menu.get('items', []))} items")
    
    # Log paths that were checked
    from app.utils.menu_utils import POSSIBLE_MENU_PATHS, MENU_FILE_PATH
    logger.info(f"Menu file path used: {MENU_FILE_PATH}")
    logger.info("Paths checked (in order of priority):")
    for i, path in enumerate(POSSIBLE_MENU_PATHS):
        if path:
            exists = os.path.exists(path)
            logger.info(f"  {i+1}. {path} - {'EXISTS' if exists else 'NOT FOUND'}")
    
    # Return success status
    return len(menu.get('items', [])) > 0

if __name__ == "__main__":
    success = test_docker_paths()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    exit(0 if success else 1)