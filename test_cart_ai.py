"""
Test cart agent AI functionality
"""
import asyncio
import logging
from app.agents.cart_async import AsyncCartAgent
from app.utils.agent_orchestration_async import async_agent_orchestrator

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_cart_ai():
    """Test if cart agent uses AI properly"""
    print("Testing Cart Agent AI functionality...")
    
    # Initialize orchestrator
    await async_agent_orchestrator.initialize()
    
    # Get cart agent
    cart_agent = async_agent_orchestrator._agents.get("cart")
    if not cart_agent:
        print("ERROR: Cart agent not found!")
        return
    
    print(f"Cart agent found: {cart_agent}")
    print(f"Cart agent class: {cart_agent.__class__.__name__}")
    print(f"Cart agent has AIIntelligenceMixin: {hasattr(cart_agent, 'process_with_ai')}")
    
    # Test a simple order
    call_sid = "TEST_CART_AI"
    context = {"call_sid": call_sid}
    
    # Test input
    test_input = "I want two california rolls"
    
    print(f"\nTesting input: '{test_input}'")
    response = await cart_agent.process_input(test_input, context)
    
    print(f"\nResponse:")
    print(f"  Text: {response.get('text')}")
    print(f"  AI Generated: {response.get('ai_generated', False)}")
    print(f"  Agent: {response.get('agent')}")
    print(f"  Cart: {response.get('cart')}")

if __name__ == "__main__":
    asyncio.run(test_cart_ai())