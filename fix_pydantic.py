#!/usr/bin/env python3
"""
Script to fix Pydantic version issues by downgrading to v1.10.13 if v2 is detected.
"""
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_pydantic_version():
    try:
        import pydantic
        return pydantic.__version__
    except ImportError:
        logger.warning("Pydantic not found")
        return None

def install_pydantic_v1():
    logger.info("Installing Pydantic v1.10.13...")
    cmd = [sys.executable, "-m", "pip", "install", "pydantic==1.10.13", "--force-reinstall"]
    try:
        subprocess.check_call(cmd)
        logger.info("Successfully installed Pydantic v1.10.13")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Pydantic v1.10.13: {e}")
        return False

def fix_pydantic():
    version = check_pydantic_version()
    if version:
        logger.info(f"Detected Pydantic version: {version}")
        if version.startswith("2."):
            logger.info("Detected Pydantic v2, installing v1.10.13 for compatibility")
            return install_pydantic_v1()
        elif version.startswith("1."):
            logger.info("Pydantic v1 already installed, no action needed")
            return True
    else:
        logger.info("Pydantic not found, installing v1.10.13")
        return install_pydantic_v1()

if __name__ == "__main__":
    logger.info("Running Pydantic version fix")
    if fix_pydantic():
        logger.info("✅ Pydantic setup is now correct")
        sys.exit(0)
    else:
        logger.error("❌ Failed to fix Pydantic setup")
        sys.exit(1)
