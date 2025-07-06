"""
E2E Test Configuration and Fixtures

Provides pytest fixtures and configuration for comprehensive E2E testing.
"""

import pytest
import pytest_asyncio
import asyncio
import logging
import os
import json
import httpx
import redis.asyncio as redis
from typing import AsyncGenerator, Dict, Any, Optional
# Optional semantic similarity (fallback if not available)
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SEMANTIC_AVAILABLE = False

from tests.e2e.deliverect_test_helper import deliverect_test_helper

# Configure logging for E2E tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_test_environment():
    """
    Setup the complete E2E test environment before running tests.
    
    This fixture:
    1. Validates environment variables
    2. Sets up Deliverect test menu
    3. Ensures system is ready for testing
    """
    logger.info("🚀 Setting up E2E test environment...")
    
    # Validate required environment variables
    required_env_vars = [
        "OPENAI_API_KEY",
        "REDIS_URL", 
        "DATABASE_URL"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Some E2E tests may not work properly")
    
    # Setup Deliverect test menu
    try:
        menu_setup = await deliverect_test_helper.setup_test_menu()
        if menu_setup:
            logger.info("✅ Deliverect test menu setup completed")
        else:
            logger.warning("⚠️  Deliverect test menu setup failed - using mocked verification")
    except Exception as e:
        logger.warning(f"⚠️  Deliverect setup error: {e} - proceeding with mocked verification")
    
    # Ensure Seasonal Soup is snoozed for out-of-stock tests
    try:
        await deliverect_test_helper.snooze_item("TEST-SEASONAL-SOUP", snooze=True)
        logger.info("✅ Seasonal Soup snoozed for out-of-stock testing")
    except Exception as e:
        logger.warning(f"⚠️  Could not snooze test item: {e}")
    
    logger.info("🎯 E2E test environment ready!")
    
    yield  # Run tests
    
    # Cleanup after tests
    logger.info("🧹 Cleaning up E2E test environment...")
    try:
        await deliverect_test_helper.cleanup_test_orders()
        logger.info("✅ E2E test cleanup completed")
    except Exception as e:
        logger.warning(f"⚠️  Cleanup warning: {e}")

@pytest.fixture
async def test_call_context():
    """
    Provide a fresh test call context for each test.
    
    Returns:
        Dictionary with test call information
    """
    import uuid
    import time
    
    return {
        "call_sid": f"e2e_test_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        "session_id": f"session_{uuid.uuid4().hex[:8]}",
        "test_start_time": time.time()
    }

@pytest.fixture
def deliverect_helper():
    """
    Provide access to Deliverect test helper.
    
    Returns:
        DeliverectTestHelper instance
    """
    return deliverect_test_helper


@pytest_asyncio.fixture(scope="session")
def semantic_model():
    """Load semantic similarity model once for entire test suite"""
    if SEMANTIC_AVAILABLE:
        return SentenceTransformer('all-MiniLM-L6-v2')
    return None


@pytest_asyncio.fixture
async def async_client():
    """Create isolated async HTTP client for each test targeting Docker container"""
    # Use container network if we're running inside Docker, localhost otherwise
    base_url = os.getenv("E2E_BASE_URL", "http://localhost:8080")
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def redis_client():
    """Create Redis connection for test database targeting Docker container"""
    # Use container network if we're running inside Docker, localhost otherwise
    redis_url = os.getenv("E2E_REDIS_URL", "redis://redbarsushi-redis:6379/1")
    client = redis.from_url(redis_url)
    yield client
    # Clean up test database after each test
    try:
        await client.flushdb()
        await client.close()
    except Exception as e:
        logger.warning(f"Error cleaning up Redis: {e}")


async def send_turn(client: httpx.AsyncClient, call_sid: str, user_input: str) -> Dict[str, Any]:
    """
    Helper function to simulate a user's conversational turn
    
    Args:
        client: HTTP client
        call_sid: Session identifier
        user_input: User's message
        
    Returns:
        Response data from the API
    """
    payload = {
        "speech_result": user_input,
        "call_sid": call_sid
    }
    
    response = await client.post("/order/take_order", json=payload)
    response.raise_for_status()
    return response.json()


async def get_cart_state(redis_client: redis.Redis, call_sid: str) -> Dict[str, Any]:
    """
    Helper to retrieve and decode cart state from Redis
    
    Args:
        redis_client: Redis connection
        call_sid: Session identifier
        
    Returns:
        Cart state dictionary
    """
    cart_data = await redis_client.get(f"cart:{call_sid}")
    if cart_data:
        return json.loads(cart_data)
    return {}


async def get_fsm_state(redis_client: redis.Redis, call_sid: str) -> Optional[str]:
    """
    Helper to retrieve FSM state from Redis
    
    Args:
        redis_client: Redis connection
        call_sid: Session identifier
        
    Returns:
        Current FSM state string
    """
    state_data = await redis_client.get(f"fsm_state:{call_sid}")
    if state_data:
        state_info = json.loads(state_data)
        return state_info.get("current_state")
    return None


async def get_session_data(redis_client: redis.Redis, call_sid: str) -> Dict[str, Any]:
    """
    Helper to retrieve session data from Redis
    
    Args:
        redis_client: Redis connection
        call_sid: Session identifier
        
    Returns:
        Session data dictionary
    """
    session_data = await redis_client.get(f"session:{call_sid}")
    if session_data:
        return json.loads(session_data)
    return {}


def assert_semantic_similarity(text1: str, text2: str, model=None, threshold: float = 0.7) -> bool:
    """
    Assert semantic similarity between two texts
    
    Args:
        text1: First text
        text2: Second text
        model: Sentence transformer model (optional)
        threshold: Similarity threshold (0-1)
        
    Returns:
        True if similarity exceeds threshold
    """
    if not SEMANTIC_AVAILABLE or model is None:
        # Simple keyword overlap fallback
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        return (overlap / max(total, 1)) >= (threshold * 0.5)  # More lenient threshold
    
    embeddings = model.encode([text1, text2])
    similarity = model.similarity(embeddings[0], embeddings[1])
    return similarity.item() >= threshold


def assert_contains_keywords(text: str, keywords: list, case_sensitive: bool = False) -> bool:
    """
    Assert that text contains all specified keywords
    
    Args:
        text: Text to search
        keywords: List of keywords to find
        case_sensitive: Whether search is case sensitive
        
    Returns:
        True if all keywords found
    """
    if not case_sensitive:
        text = text.lower()
        keywords = [kw.lower() for kw in keywords]
    
    return all(keyword in text for keyword in keywords)

# Custom pytest markers for E2E tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests (may be slow)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "deliverect: marks tests that require Deliverect API access"
    )

# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add appropriate markers."""
    for item in items:
        # Add slow marker to all E2E tests
        if "e2e" in item.keywords:
            item.add_marker(pytest.mark.slow)
            
        # Add deliverect marker to tests that verify orders
        if "deliverect" in item.name or "order" in item.name:
            item.add_marker(pytest.mark.deliverect)