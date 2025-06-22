"""
Simple test to check cart agent AI functionality
"""
import asyncio
import logging
from app.agents.cart_async import AsyncCartAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_cart_ai():
    """Test if cart agent uses AI properly"""
    print("Testing Cart Agent AI functionality...")
    
    # Create cart agent directly
    cart_agent = AsyncCartAgent()
    
    print(f"Cart agent class: {cart_agent.__class__.__name__}")
    print(f"Cart agent MRO: {[c.__name__ for c in cart_agent.__class__.__mro__]}")
    print(f"Cart agent has process_with_ai: {hasattr(cart_agent, 'process_with_ai')}")
    print(f"Cart agent has _ai_client: {hasattr(cart_agent, '_ai_client')}")
    print(f"Cart agent has _ai_enabled: {hasattr(cart_agent, '_ai_enabled')}")
    
    # Test a simple order
    call_sid = "TEST_CART_AI"
    context = {"call_sid": call_sid}
    cart_agent.set_current_call(call_sid)
    
    # Test input
    test_input = "I want two california rolls"
    
    print(f"\nTesting input: '{test_input}'")
    
    try:
        response = await cart_agent.process_input(test_input, context)
        
        print(f"\nResponse:")
        print(f"  Text: {response.get('text')}")
        print(f"  AI Generated: {response.get('ai_generated', False)}")
        print(f"  Agent: {response.get('agent')}")
        print(f"  Cart: {response.get('cart')}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cart_ai())