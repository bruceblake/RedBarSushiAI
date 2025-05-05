"""
Test script to verify imports and basic functionality of refactored code.
"""

import os
import sys
import logging
import importlib

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_import(module_path):
    """Test importing a module and report any errors."""
    try:
        logger.info(f"Testing import: {module_path}")
        module = importlib.import_module(module_path)
        logger.info(f"✅ Successfully imported {module_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error importing {module_path}: {str(e)}")
        return False

def test_app_context():
    """Test creating a Flask app context."""
    try:
        logger.info("Testing Flask app context creation")
        from app import create_app
        app = create_app()
        with app.app_context():
            logger.info("✅ Successfully created Flask app context")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating Flask app context: {str(e)}")
        return False

def test_routes():
    """Test importing routes."""
    all_passed = True
    routes = [
        "app.routes.order",
        "app.routes.menu",
        "app.routes.voice",
        "app.routes.voice_orchestrated",
        "app.routes.location"
    ]
    
    for route in routes:
        if not test_import(route):
            all_passed = False
    
    return all_passed

def test_utils():
    """Test importing utility modules."""
    all_passed = True
    utils = [
        "app.utils.agent_utils",
        "app.utils.menu_utils",
        "app.utils.menu_validator",
        "app.utils.helpers",
        "app.utils.conversation_store",
        "app.utils.menu_cache"
    ]
    
    for util in utils:
        if not test_import(util):
            all_passed = False
    
    return all_passed

def test_models():
    """Test importing models."""
    all_passed = True
    models = [
        "app.models",
        "app.models.order",
        "app.models.menu",
        "app.models.location"
    ]
    
    for model in models:
        if not test_import(model):
            all_passed = False
    
    # Specifically test ContactRequest import
    try:
        logger.info("Testing specific import: app.models.ContactRequest")
        from app.models import ContactRequest
        logger.info("✅ Successfully imported ContactRequest")
    except Exception as e:
        logger.error(f"❌ Error importing ContactRequest: {str(e)}")
        all_passed = False
    
    return all_passed

def test_refactored_modules():
    """Test importing specifically refactored modules."""
    all_passed = True
    
    # Test order modules
    order_modules = [
        "app.routes.order.__init__",
        "app.routes.order.utils",
        "app.routes.order.take_order",
        "app.routes.order.confirmation",
        "app.routes.order.modification",
        "app.routes.order.fallbacks",
        "app.routes.order.checkout",
        "app.routes.order.status",
        "app.routes.order.contact"
    ]
    
    logger.info("Testing order modules...")
    for module in order_modules:
        if not test_import(module):
            all_passed = False
    
    # Test agent_utils modules
    agent_modules = [
        "app.utils.agent_utils.__init__",
        "app.utils.agent_utils.logging",
        "app.utils.agent_utils.menu",
        "app.utils.agent_utils.order",
        "app.utils.agent_utils.parsing",
        "app.utils.agent_utils.modification",
        "app.utils.agent_utils.tools"
    ]
    
    logger.info("Testing agent_utils modules...")
    for module in agent_modules:
        if not test_import(module):
            all_passed = False
    
    return all_passed

def run_all_tests():
    """Run all tests."""
    logger.info("Starting import tests")
    
    tests = {
        "App Context": test_app_context,
        "Routes": test_routes,
        "Utils": test_utils,
        "Models": test_models,
        "Refactored Modules": test_refactored_modules
    }
    
    results = {}
    all_passed = True
    
    for name, test_func in tests.items():
        logger.info(f"\n{'=' * 50}\nRunning {name} tests\n{'=' * 50}")
        result = test_func()
        results[name] = result
        if not result:
            all_passed = False
    
    # Print summary
    logger.info("\n\n")
    logger.info("=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    for name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{name}: {status}")
    
    overall = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    logger.info(f"\nOverall: {overall}")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)