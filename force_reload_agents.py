#!/usr/bin/env python3
"""
Script to ensure all agent modules are properly loaded during startup.
This forces a reload of all agent modules to ensure they're properly registered.
"""

import os
import logging
import importlib
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_agents_loaded():
    """Force reload all agent modules to ensure they're properly registered."""
    logger.info("Starting force reload of agent modules...")
    
    # List of agent modules to ensure are imported
    agent_modules = [
        "app.agents.base_async",
        "app.agents.frontline_async",
        "app.agents.menu_async",
        "app.agents.cart_async",
        "app.agents.guardrail_async",
        "app.agents.fulfillment_async",
        "app.agents.escalation_async",
        "app.agents.factory_async"
    ]
    
    # Force reload each module
    for module_name in agent_modules:
        try:
            if module_name in sys.modules:
                logger.info(f"Reloading existing module: {module_name}")
                module = importlib.reload(sys.modules[module_name])
            else:
                logger.info(f"Importing new module: {module_name}")
                module = importlib.import_module(module_name)
                
            logger.info(f"Successfully loaded {module_name}")
        except ImportError as e:
            logger.error(f"Failed to import {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error with {module_name}: {e}")
    
    # Specifically ensure the factory is initialized
    try:
        from app.agents.factory_async import async_agent_factory
        logger.info(f"Factory instance: {async_agent_factory}")
        logger.info(f"Factory agent_classes: {list(async_agent_factory.agent_classes.keys())}")
    except Exception as e:
        logger.error(f"Error checking factory: {e}")
    
    logger.info("Agent module reload complete")

if __name__ == "__main__":
    ensure_agents_loaded()