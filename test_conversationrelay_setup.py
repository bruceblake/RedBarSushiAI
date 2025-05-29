#!/usr/bin/env python3
"""
Test script to verify ConversationRelay setup with FSM agents.
Run this to ensure all components are properly configured.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_configuration():
    """Test that configuration is loaded correctly."""
    logger.info("=== Testing Configuration ===")
    try:
        from app.config import settings
        
        logger.info(f"✓ VOICE_HANDLER: {settings.VOICE_HANDLER}")
        logger.info(f"✓ BASE_URL: {settings.BASE_URL}")
        logger.info(f"✓ OPENAI_API_KEY: {'Set' if settings.OPENAI_API_KEY else 'Not set'}")
        logger.info(f"✓ TWILIO_ACCOUNT_SID: {'Set' if settings.TWILIO_ACCOUNT_SID else 'Not set'}")
        
        if settings.VOICE_HANDLER == "conversation_relay":
            logger.info("✓ Voice handler is correctly set to conversation_relay")
            
            # Check ConversationRelay specific settings
            service_sid = getattr(settings, 'TWILIO_CONVERSATION_SERVICE_SID', None)
            connector_name = getattr(settings, 'TWILIO_CONNECTOR_NAME', None)
            
            if service_sid and connector_name:
                logger.info(f"✓ Using Service/Connector mode - SID: {service_sid[:10]}...")
            else:
                logger.info("✓ Using URL mode (recommended)")
        else:
            logger.warning(f"⚠ Voice handler is set to: {settings.VOICE_HANDLER}, not conversation_relay")
            
        return True
    except Exception as e:
        logger.error(f"✗ Configuration test failed: {e}")
        return False

async def test_database_connection():
    """Test database connection and models."""
    logger.info("\n=== Testing Database Connection ===")
    try:
        from app.db_async import verify_connection, get_db
        
        is_connected = await verify_connection()
        if is_connected:
            logger.info("✓ Database connection verified")
            
            # Test getting a session
            async for db in get_db():
                logger.info("✓ Database session created successfully")
                break
        else:
            logger.error("✗ Database connection failed")
            return False
            
        return True
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False

async def test_agent_orchestrator():
    """Test agent orchestrator initialization."""
    logger.info("\n=== Testing Agent Orchestrator ===")
    try:
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        from app.db_async import get_db
        
        # Initialize with database
        async for db in get_db():
            await async_agent_orchestrator.initialize(db=db)
            logger.info("✓ Agent orchestrator initialized successfully")
            
            # Test starting a conversation
            test_call_sid = f"TEST_{datetime.now().timestamp()}"
            await async_agent_orchestrator.start_new_conversation(
                test_call_sid,
                {"test": True}
            )
            logger.info(f"✓ Test conversation started: {test_call_sid}")
            
            # Clean up
            if test_call_sid in async_agent_orchestrator.conversations:
                del async_agent_orchestrator.conversations[test_call_sid]
                logger.info("✓ Test conversation cleaned up")
            break
            
        return True
    except Exception as e:
        logger.error(f"✗ Agent orchestrator test failed: {e}")
        return False

async def test_twiml_generation():
    """Test TwiML generation for ConversationRelay."""
    logger.info("\n=== Testing TwiML Generation ===")
    try:
        from app.api.conversation_relay.twiml import generate_conversation_relay_twiml
        from app.config import settings
        
        # Test URL mode
        twiml = generate_conversation_relay_twiml(
            call_sid="TEST123",
            greeting_text="Test greeting",
            host="localhost:8000"
        )
        
        if '<ConversationRelay' in twiml and 'url=' in twiml:
            logger.info("✓ TwiML generation successful (URL mode)")
            logger.info(f"  Generated WebSocket URL: ws://localhost:8000/api/conversation-relay")
        else:
            logger.error("✗ TwiML generation failed")
            return False
            
        return True
    except Exception as e:
        logger.error(f"✗ TwiML generation test failed: {e}")
        return False

async def test_websocket_handler():
    """Test WebSocket handler imports."""
    logger.info("\n=== Testing WebSocket Handler ===")
    try:
        from app.api.conversation_relay.handler import ConversationRelayHandler
        logger.info("✓ ConversationRelayHandler imported successfully")
        
        # Check handler methods exist
        required_methods = ['handle_setup', 'handle_prompt', 'handle_interrupt', 'send_text']
        for method in required_methods:
            if hasattr(ConversationRelayHandler, method):
                logger.info(f"✓ Method {method} exists")
            else:
                logger.error(f"✗ Method {method} missing")
                return False
                
        return True
    except Exception as e:
        logger.error(f"✗ WebSocket handler test failed: {e}")
        return False

async def test_routes():
    """Test that routes are properly registered."""
    logger.info("\n=== Testing Routes ===")
    try:
        from app.main import app
        
        routes_found = {
            'voice_webhook': False,
            'conversation_relay_ws': False
        }
        
        for route in app.routes:
            if hasattr(route, 'path'):
                if route.path in ['/voice/', '/voice/webhook']:
                    routes_found['voice_webhook'] = True
                    logger.info(f"✓ Found voice webhook route: {route.path}")
                elif '/conversation-relay' in route.path:
                    routes_found['conversation_relay_ws'] = True
                    logger.info(f"✓ Found ConversationRelay WebSocket route: {route.path}")
        
        # Check sub-routers
        from app.api import api_router
        for route in api_router.routes:
            if hasattr(route, 'path') and '/conversation-relay' in route.path:
                routes_found['conversation_relay_ws'] = True
                logger.info(f"✓ Found ConversationRelay route in API router: {route.path}")
        
        all_found = all(routes_found.values())
        if not all_found:
            logger.error("✗ Some required routes are missing:")
            for route, found in routes_found.items():
                if not found:
                    logger.error(f"  - {route}")
                    
        return all_found
    except Exception as e:
        logger.error(f"✗ Routes test failed: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("ConversationRelay Setup Test")
    logger.info("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Database Connection", test_database_connection),
        ("Agent Orchestrator", test_agent_orchestrator),
        ("TwiML Generation", test_twiml_generation),
        ("WebSocket Handler", test_websocket_handler),
        ("Routes", test_routes)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name:.<30} {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n✅ All tests passed! ConversationRelay is ready to use.")
        logger.info("\nNext steps:")
        logger.info("1. Start ngrok: ngrok http 8000")
        logger.info("2. Update Twilio webhook with ngrok URL")
        logger.info("3. Make a test call to your Twilio number")
    else:
        logger.error("\n❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)