"""
OpenAI shim to handle cases where the OpenAI package is not available.
This provides fallback functionality for when OpenAI is not installed.
"""
import logging

# Flag for openai availability
OPENAI_AVAILABLE = False
OPENAI_AGENTS_AVAILABLE = False

# Try to import OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
    
    # Test Agent API availability
    try:
        from openai.agent.types import AgentAction, AgentFinish, AgentStep
        OPENAI_AGENTS_AVAILABLE = True
    except ImportError:
        OPENAI_AGENTS_AVAILABLE = False
except ImportError:
    # Create dummy classes and objects
    class DummyCompletion:
        def create(self, *args, **kwargs):
            return {"choices": [{"message": {"content": "OpenAI not available"}}]}
    
    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletion()
    
    class DummyOpenAI:
        def __init__(self):
            self.chat = DummyChat()
            
        def __getattr__(self, name):
            logging.warning(f"Attempted to access '{name}' but OpenAI package is not available")
            return self
            
    # Create the dummy openai module
    openai = DummyOpenAI()
    logging.warning("OpenAI package not available, using fallback implementation")

# Simple fallback functions
def fallback_analyze_user_input(text: str) -> dict:
    """Fallback function when OpenAI is not available"""
    logging.warning("Using fallback analysis - OpenAI not available")
    # Return a basic analysis with empty menu items
    return {
        "intent": "order_food",
        "menu_items": [],
        "confidence": 0
    }

def fallback_get_order_modifications(text: str, current_items: list) -> dict:
    """Fallback function when OpenAI is not available"""
    logging.warning("Using fallback modification - OpenAI not available")
    
    # Basic keyword-based fallback
    additions = []
    removals = []
    
    # Super simple keyword matching
    if any(word in text.lower() for word in ["add", "want", "with"]):
        # Add a simple placeholder - will be validated later
        additions.append({"name": "Unknown Item", "quantity": 1})
    
    if any(word in text.lower() for word in ["remove", "without", "no"]):
        # Create a removal - will be validated later
        removals.append({"name": "Unknown Item", "quantity": 1})
    
    # Return the modifications
    return {
        "additions": additions,
        "removals": removals
    }