#!/usr/bin/env python3
"""
Script to verify environment variables for RedBarSushiAI.

This script checks critical environment variables, specifically focusing
on the OPENAI_API_KEY to ensure it's properly configured.
"""

import os
import sys
import logging
from typing import Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("env_check")

def check_env_files() -> Dict[str, Optional[str]]:
    """Check if env files exist and their contents for OPENAI_API_KEY."""
    env_files = {
        ".env": None,
        ".env.development": None,
        ".env.production": None,
        ".env.local": None,
    }
    
    for filename in env_files:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(filepath):
            logger.info(f"✅ {filename} exists")
            with open(filepath, 'r') as f:
                content = f.read()
                if "OPENAI_API_KEY" in content:
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip().startswith("OPENAI_API_KEY="):
                            key_value = line.strip().split("=", 1)[1].strip()
                            # Remove quotes if present
                            if key_value.startswith('"') and key_value.endswith('"'):
                                key_value = key_value[1:-1]
                            elif key_value.startswith("'") and key_value.endswith("'"):
                                key_value = key_value[1:-1]
                            
                            # Mask most of the key for security
                            if key_value:
                                if len(key_value) > 10:
                                    masked_key = f"{key_value[:4]}...{key_value[-4:]}"
                                else:
                                    masked_key = "[TOO SHORT]"
                                env_files[filename] = masked_key
                                logger.info(f"   📝 Found OPENAI_API_KEY in {filename}: {masked_key}")
                                
                                # Check for test/dummy keys
                                if "mytestapikey" in key_value.lower() or "test" in key_value.lower():
                                    logger.error(f"❌ The OPENAI_API_KEY in {filename} appears to be a TEST/DUMMY key!")
                            else:
                                logger.warning(f"⚠️ OPENAI_API_KEY is empty in {filename}")
                                env_files[filename] = "[EMPTY]"
                            break
                    else:
                        logger.warning(f"⚠️ OPENAI_API_KEY line found in {filename} but couldn't extract value")
                else:
                    logger.warning(f"⚠️ No OPENAI_API_KEY found in {filename}")
        else:
            logger.warning(f"⚠️ {filename} does not exist")
    
    return env_files

def check_docker_compose_files() -> None:
    """Check Docker Compose files for env_file references and environment sections."""
    docker_compose_files = [
        "docker-compose.yml",
        "docker-compose.override.yml",
        "docker/compose/docker-compose.yml",
        "docker/compose/docker-compose.override.yml",
    ]
    
    for filename in docker_compose_files:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(filepath):
            logger.info(f"✅ {filename} exists")
            with open(filepath, 'r') as f:
                content = f.read()
                
                # Check for env_file references
                if "env_file:" in content:
                    logger.info(f"   📝 Found env_file directive in {filename}")
                    # Try to extract the path
                    lines = content.split('\n')
                    env_files = []
                    in_env_file_section = False
                    for line in lines:
                        if "env_file:" in line:
                            in_env_file_section = True
                        elif in_env_file_section and line.strip().startswith("-"):
                            env_file = line.strip().replace("-", "").strip()
                            env_files.append(env_file)
                        elif in_env_file_section and not line.strip().startswith("-") and line.strip():
                            in_env_file_section = False
                    
                    if env_files:
                        for env_file in env_files:
                            logger.info(f"   🔍 env_file reference: {env_file}")
                
                # Check for environment sections with OPENAI_API_KEY
                if "environment:" in content and "OPENAI_API_KEY" in content:
                    logger.warning(f"⚠️ Found direct OPENAI_API_KEY definition in {filename} environment section!")
                    logger.warning(f"   This might override .env file values!")
        else:
            logger.warning(f"⚠️ {filename} does not exist")

def check_system_env() -> Optional[str]:
    """Check system environment variables for OPENAI_API_KEY."""
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key:
        # Mask most of the key for security
        if len(openai_api_key) > 10:
            masked_key = f"{openai_api_key[:4]}...{openai_api_key[-4:]}"
        else:
            masked_key = "[TOO SHORT]"
        logger.info(f"✅ OPENAI_API_KEY found in OS environment: {masked_key}")
        
        # Check for test/dummy keys
        if "mytestapikey" in openai_api_key.lower() or "test" in openai_api_key.lower():
            logger.error(f"❌ The OPENAI_API_KEY in OS environment appears to be a TEST/DUMMY key!")
        
        return masked_key
    else:
        logger.warning("⚠️ OPENAI_API_KEY not found in OS environment")
        return None

def main() -> None:
    """Main function to check environment variables."""
    logger.info("=== RedBarSushiAI Environment Variables Check ===")
    
    # Check OS environment
    logger.info("\n1. Checking system environment variables:")
    system_key = check_system_env()
    
    # Check .env files
    logger.info("\n2. Checking .env files:")
    env_files = check_env_files()
    
    # Check Docker Compose files
    logger.info("\n3. Checking Docker Compose files:")
    check_docker_compose_files()
    
    # Summary and recommendations
    logger.info("\n=== Summary ===")
    if system_key:
        logger.info(f"🔑 OS environment OPENAI_API_KEY: {system_key}")
    else:
        logger.warning("❓ No OPENAI_API_KEY found in OS environment")
    
    for filename, key in env_files.items():
        if key:
            logger.info(f"🔑 {filename} OPENAI_API_KEY: {key}")
        else:
            if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)):
                logger.warning(f"❓ No OPENAI_API_KEY found in {filename}")
    
    logger.info("\n=== Recommendations ===")
    
    # Check for main issue - no valid API key
    if not system_key and not any(env_files.values()):
        logger.error("❌ No OPENAI_API_KEY found in any location!")
        logger.info("📋 You need to add your OpenAI API key to .env.development or export it as an environment variable")
    elif any("mytestapikey" in str(key).lower() or "test" in str(key).lower() for key in [system_key] + list(env_files.values()) if key):
        logger.error("❌ Found TEST/DUMMY OpenAI API key!")
        logger.info("📋 You need to replace the test API key with a valid OpenAI API key")
    
    logger.info("\nTo fix the issue:")
    logger.info("1. Open your .env.development file")
    logger.info("2. Ensure it has a line with OPENAI_API_KEY=your_actual_openai_key")
    logger.info("3. Make sure there are no quotes around the key value")
    logger.info("4. Restart your Docker container with ./force_rebuild.sh && ./restart_docker.sh")
    logger.info("5. If issues persist, export the key directly: export OPENAI_API_KEY=your_actual_openai_key")

if __name__ == "__main__":
    main()