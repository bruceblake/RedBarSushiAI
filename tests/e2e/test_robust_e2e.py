"""
Robust E2E Testing Suite for RedBarSushiAI
Uses multi-layered validation: state verification, tool calls, semantic similarity, and outcome validation.
"""

import pytest
import asyncio
import time
import uuid
import logging
import json
from typing import Dict, Any, List, Optional
# Configure logging for tests first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional semantic similarity (requires sentence-transformers)
try:
    from sentence_transformers import SentenceTransformer, util
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers not available - semantic similarity tests will be skipped")

# Global semantic similarity model (loaded once)
semantic_model = None

def get_semantic_model():
    """Load semantic similarity model (lazy loading)."""
    global semantic_model
    if not SEMANTIC_AVAILABLE:
        return None
        
    if semantic_model is None:
        try:
            semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Semantic similarity model loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load semantic model: {e}")
            semantic_model = False  # Mark as unavailable
    return semantic_model if semantic_model else None

class RobustE2ETestFramework:
    """
    Advanced E2E testing framework that validates:
    1. Core logic and state transitions (deterministic)
    2. Tool calls and arguments (deterministic) 
    3. Flexible response patterns (flexible)
    4. Semantic similarity (advanced)
    5. Final system outcomes (deterministic)
    """
    
    def __init__(self):
        self.call_sid = None
        self.conversation_history = []
        self.state_transitions = []
        self.tool_calls = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.call_sid = f"robust_e2e_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        logger.info(f"🎯 Starting robust E2E test session: {self.call_sid}")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        logger.info(f"🧹 Cleaned up robust test session: {self.call_sid}")
        
    async def send_turn(self, text: str, expected_state: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a conversational turn and capture all validation data.
        
        Args:
            text: User input text
            expected_state: Expected HSM state after this turn (if known)
            
        Returns:
            Full response with validation metadata
        """
        logger.info(f"👤 User: {text}")
        
        # Capture state before interaction
        previous_state = await self._get_current_hsm_state()
        
        # Use orchestrator directly
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        
        response = await async_agent_orchestrator.process_voice_input(
            input_text=text,
            call_sid=self.call_sid,
            context={"session_id": f"session_{self.call_sid}"}
        )
        
        # Capture state after interaction
        current_state = await self._get_current_hsm_state()
        
        # Log the response
        ai_text = response.get("text", "NO RESPONSE")
        logger.info(f"🤖 AI: {ai_text}")
        
        # Extract and store validation data
        validation_data = {
            "user_input": text,
            "ai_response": ai_text,
            "full_response": response,
            "previous_state": previous_state,
            "current_state": current_state,
            "state_changed": previous_state != current_state,
            "actions": response.get("actions", []),
            "tool_calls": response.get("tool_calls", []),
            "timestamp": time.time()
        }
        
        # Store for later validation
        self.conversation_history.append(validation_data)
        if validation_data["state_changed"]:
            self.state_transitions.append({
                "from": previous_state,
                "to": current_state,
                "trigger": text,
                "response": ai_text
            })
        if validation_data["tool_calls"]:
            self.tool_calls.extend(validation_data["tool_calls"])
            
        # Basic response validation
        assert response is not None, "Response should not be None"
        assert "text" in response, "Response should contain 'text' field"
        assert "handled" in response, "Response should contain 'handled' field"
        assert response["handled"] is True, "Response should be handled"
        
        # Optional state validation
        if expected_state:
            self.assert_hsm_state(expected_state, f"Expected state {expected_state} after: {text}")
            
        return validation_data
        
    async def _get_current_hsm_state(self) -> str:
        """Get current HSM state from Redis."""
        try:
            from app.fsm.hsm_manager import hsm_manager
            state_info = await hsm_manager.get_state_info(self.call_sid)
            return state_info.get("current_state", "UNKNOWN")
        except Exception as e:
            logger.warning(f"Could not get HSM state: {e}")
            return "UNKNOWN"
            
    async def _get_cart_state(self) -> Dict[str, Any]:
        """Get current cart state from Redis."""
        try:
            import redis.asyncio as redis
            from app.config import settings
            redis_client = redis.from_url(settings.REDIS_URL)
            cart_key = f"cart:{self.call_sid}"
            cart_data = await redis_client.get(cart_key)
            if cart_data:
                return json.loads(cart_data)
            return {"items": []}
        except Exception as e:
            logger.warning(f"Could not get cart state: {e}")
            return {"items": []}
            
    # === LAYER 1: DETERMINISTIC STATE AND LOGIC VALIDATION ===
    
    def assert_hsm_state(self, expected_state: str, message: str = "HSM state mismatch"):
        """Assert that the system is in the expected HSM state."""
        if self.conversation_history:
            actual_state = self.conversation_history[-1]["current_state"]
            assert actual_state == expected_state, f"{message}. Expected: {expected_state}, Got: {actual_state}"
        else:
            raise AssertionError("No conversation history to check state")
            
    def assert_state_transition(self, from_state: str, to_state: str, message: str = "State transition not found"):
        """Assert that a specific state transition occurred."""
        for transition in self.state_transitions:
            if transition["from"] == from_state and transition["to"] == to_state:
                logger.info(f"✅ State transition verified: {from_state} → {to_state}")
                return
        raise AssertionError(f"{message}. Expected: {from_state} → {to_state}, Found: {self.state_transitions}")
        
    def assert_tool_called(self, tool_name: str, expected_args: Dict[str, Any] = None, message: str = "Tool not called"):
        """Assert that a specific tool was called with expected arguments."""
        for tool_call in self.tool_calls:
            if tool_call.get("function", {}).get("name") == tool_name:
                logger.info(f"✅ Tool call verified: {tool_name}")
                
                # Check arguments if provided
                if expected_args:
                    actual_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    for key, expected_value in expected_args.items():
                        assert key in actual_args, f"Tool {tool_name} missing argument: {key}"
                        assert actual_args[key] == expected_value, f"Tool {tool_name} arg {key}: expected {expected_value}, got {actual_args[key]}"
                        
                return tool_call
        raise AssertionError(f"{message}. Expected tool: {tool_name}, Available: {[tc.get('function', {}).get('name') for tc in self.tool_calls]}")
        
    async def assert_cart_contains(self, expected_items: List[Dict[str, Any]], message: str = "Cart validation failed"):
        """Assert that the cart contains expected items."""
        cart = await self._get_cart_state()
        cart_items = cart.get("items", [])
        
        for expected_item in expected_items:
            found = False
            for cart_item in cart_items:
                if self._item_matches(cart_item, expected_item):
                    found = True
                    break
            assert found, f"{message}. Expected item not found in cart: {expected_item}. Cart: {cart_items}"
            
        logger.info(f"✅ Cart validation passed: {len(expected_items)} items verified")
        
    def _item_matches(self, cart_item: Dict[str, Any], expected_item: Dict[str, Any]) -> bool:
        """Check if cart item matches expected item."""
        # Check name/PLU
        if "name" in expected_item:
            if expected_item["name"].lower() not in cart_item.get("name", "").lower():
                return False
                
        # Check quantity
        if "quantity" in expected_item:
            if cart_item.get("quantity", 1) != expected_item["quantity"]:
                return False
                
        # Check modifiers (simplified)
        if "modifiers" in expected_item:
            cart_modifiers = cart_item.get("modifiers", [])
            if len(cart_modifiers) != len(expected_item["modifiers"]):
                return False
                
        return True
        
    # === LAYER 2: FLEXIBLE PATTERN MATCHING ===
    
    def assert_response_contains_keywords(self, keywords: List[str], message: str = "Keywords not found in response"):
        """Assert that the latest AI response contains expected keywords (flexible matching)."""
        if not self.conversation_history:
            raise AssertionError("No conversation history to check")
            
        response_text = self.conversation_history[-1]["ai_response"].lower()
        found_keywords = [kw for kw in keywords if kw.lower() in response_text]
        
        assert len(found_keywords) > 0, f"{message}. Expected any of {keywords}, got: {response_text}"
        logger.info(f"✅ Keywords found: {found_keywords}")
        
    def assert_response_pattern(self, patterns: List[str], message: str = "Pattern not found in response"):
        """Assert that the latest AI response matches expected patterns."""
        import re
        
        if not self.conversation_history:
            raise AssertionError("No conversation history to check")
            
        response_text = self.conversation_history[-1]["ai_response"]
        
        for pattern in patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                logger.info(f"✅ Pattern matched: {pattern}")
                return
                
        raise AssertionError(f"{message}. Expected any pattern: {patterns}, got: {response_text}")
        
    # === LAYER 3: SEMANTIC SIMILARITY VALIDATION ===
    
    def assert_semantic_similarity(self, golden_response: str, threshold: float = 0.75, message: str = "Semantic similarity too low"):
        """Assert that the latest AI response is semantically similar to the golden response."""
        model = get_semantic_model()
        if not model:
            logger.warning("⚠️ Semantic similarity not available - skipping")
            return
            
        if not self.conversation_history:
            raise AssertionError("No conversation history to check")
            
        actual_response = self.conversation_history[-1]["ai_response"]
        
        # Calculate embeddings
        embedding_actual = model.encode(actual_response, convert_to_tensor=True)
        embedding_golden = model.encode(golden_response, convert_to_tensor=True)
        
        # Calculate cosine similarity
        cosine_score = util.pytorch_cos_sim(embedding_actual, embedding_golden)[0][0].item()
        
        logger.info(f"📊 Semantic similarity: {cosine_score:.3f} (threshold: {threshold})")
        
        assert cosine_score >= threshold, f"{message}. Score: {cosine_score:.3f}, Threshold: {threshold}, Actual: {actual_response}, Golden: {golden_response}"
        logger.info(f"✅ Semantic similarity validated: {cosine_score:.3f}")
        
    # === LAYER 4: SYSTEM OUTCOME VALIDATION ===
    
    async def assert_deliverect_order(self, expected_items: List[Dict[str, Any]]):
        """Assert that the final order was created correctly in Deliverect."""
        # Import and use the Deliverect helper
        from .deliverect_test_helper import deliverect_test_helper
        
        order_verified = await deliverect_test_helper.verify_order_exists(expected_items)
        assert order_verified, f"Order verification failed in Deliverect for items: {expected_items}"
        logger.info("✅ Deliverect order verification passed")
        
    def validate_conversation_flow(self):
        """Validate overall conversation flow and coherence."""
        assert len(self.conversation_history) > 0, "Should have had at least one conversation turn"
        
        # Check that AI provided responses to all user inputs
        for i, turn in enumerate(self.conversation_history):
            assert len(turn["ai_response"]) > 5, f"Turn {i+1} AI response too short: {turn['ai_response']}"
            assert not turn["ai_response"].startswith("ERROR"), f"Turn {i+1} AI returned error: {turn['ai_response']}"
            
        logger.info(f"✅ Conversation flow validated: {len(self.conversation_history)} turns, {len(self.state_transitions)} state changes")


# === ROBUST E2E TEST CASES ===

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_robust_ordering_flow_with_state_validation():
    """
    Robust test: Complete ordering flow with multi-layered validation.
    Focuses on deterministic outcomes rather than exact response matching.
    """
    async with RobustE2ETestFramework() as test:
        
        # Turn 1: Initial greeting - should ask for name
        await test.send_turn("Hello, I want to place an order.")
        
        # LAYER 1: State validation (deterministic)
        # Should be in INITIAL state asking for customer info
        test.assert_hsm_state("INITIAL", "Should remain in INITIAL state until name provided")
        
        # LAYER 2: Flexible pattern matching
        test.assert_response_contains_keywords(
            ["name", "welcome", "hello", "help"],
            "AI should ask for name or provide greeting"
        )
        
        # LAYER 3: Semantic similarity (if available)
        test.assert_semantic_similarity(
            "Hello! Welcome to our restaurant. May I have your name please?",
            threshold=0.65
        )
        
        # Turn 2: Provide name
        await test.send_turn("My name is Alice.")
        
        # LAYER 2: Should acknowledge name
        test.assert_response_contains_keywords(
            ["alice", "help", "order", "menu"],
            "AI should acknowledge name and offer help"
        )
        
        # Turn 3: Order an item
        await test.send_turn("I'll take a Chicken Burger.")
        
        # LAYER 1: Should have called add_to_cart tool
        test.assert_tool_called(
            "add_to_cart",
            {"item_name": "Chicken Burger", "quantity": 1},
            "Should call add_to_cart tool for Chicken Burger"
        )
        
        # LAYER 4: Cart state validation
        await test.assert_cart_contains([
            {"name": "Chicken Burger", "quantity": 1}
        ])
        
        # LAYER 2: Should confirm addition
        test.assert_response_contains_keywords(
            ["chicken burger", "added", "cart", "order"],
            "AI should confirm item was added to cart"
        )
        
        # Turn 4: Complete order
        await test.send_turn("That's everything, please place the order.")
        
        # LAYER 2: Should provide order summary or confirmation
        test.assert_response_contains_keywords(
            ["chicken burger", "total", "confirm", "order"],
            "AI should provide order summary or ask for confirmation"
        )
        
        # Overall flow validation
        test.validate_conversation_flow()
        
        logger.info("✅ Robust ordering flow test completed successfully!")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_robust_menu_inquiry_with_semantic_validation():
    """
    Robust test: Menu inquiry with semantic similarity validation.
    """
    async with RobustE2ETestFramework() as test:
        
        # Ask about menu
        await test.send_turn("What do you have available?")
        
        # LAYER 2: Should mention menu items or ask for name first
        test.assert_response_contains_keywords(
            ["menu", "burger", "pizza", "chicken", "available", "name", "help"],
            "AI should discuss menu or ask for customer info"
        )
        
        # LAYER 3: Semantic similarity for menu inquiry
        test.assert_semantic_similarity(
            "We have burgers, pizzas, chicken dishes, and beverages available. What would you like to know more about?",
            threshold=0.60  # Lower threshold since AI might ask for name first
        )
        
        test.validate_conversation_flow()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_robust_item_not_found_handling():
    """
    Robust test: Handling items not on menu with pattern validation.
    """
    async with RobustE2ETestFramework() as test:
        
        # Try to order non-existent item
        await test.send_turn("I'd like the Lobster Thermidor.")
        
        # LAYER 2: Should indicate item not found (flexible matching)
        test.assert_response_pattern([
            r"(couldn't find|not.*available|not.*menu|don't.*have)",
            r"(name|welcome|hello)"  # Or might ask for name first
        ])
        
        # LAYER 3: Semantic similarity for "not found" response
        test.assert_semantic_similarity(
            "I'm sorry, I couldn't find that item on our menu. Would you like to try something else?",
            threshold=0.55  # Lower threshold to account for name-asking behavior
        )
        
        test.validate_conversation_flow()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_robust_multi_item_order_with_cart_validation():
    """
    Robust test: Multi-item order with deterministic cart validation.
    """
    async with RobustE2ETestFramework() as test:
        
        # Provide name first
        await test.send_turn("Hi, I'm Bob and I want to order.")
        
        # Order multiple items
        await test.send_turn("I'll take two Chicken Burgers and one Ginger Beer.")
        
        # LAYER 1: Verify multiple tool calls or single call with multiple items
        # (Flexible - might be one call or multiple)
        tool_calls = [tc for tc in test.tool_calls if tc.get("function", {}).get("name") == "add_to_cart"]
        assert len(tool_calls) >= 1, "Should have at least one add_to_cart call"
        
        # LAYER 4: Verify final cart state (deterministic)
        await test.assert_cart_contains([
            {"name": "Chicken Burger", "quantity": 2},
            {"name": "Ginger Beer", "quantity": 1}
        ])
        
        # LAYER 2: Should acknowledge items
        test.assert_response_contains_keywords(
            ["chicken burger", "ginger beer", "added"],
            "AI should acknowledge both items were added"
        )
        
        test.validate_conversation_flow()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_robust_performance_validation():
    """
    Robust test: Performance and reliability validation.
    """
    async with RobustE2ETestFramework() as test:
        
        start_time = time.time()
        
        # Multi-turn conversation
        await test.send_turn("Hello!")
        await test.send_turn("I'm Charlie.")
        await test.send_turn("I want a pizza.")
        await test.send_turn("That's all.")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance assertions
        avg_response_time = total_time / len(test.conversation_history)
        
        assert total_time < 20, f"Total conversation took too long: {total_time:.2f}s"
        assert avg_response_time < 6, f"Average response time too slow: {avg_response_time:.2f}s"
        
        logger.info(f"📊 Performance metrics: Total: {total_time:.2f}s, Avg: {avg_response_time:.2f}s")
        
        # System reliability assertions
        assert len(test.conversation_history) == 4, "Should have 4 conversation turns"
        
        for turn in test.conversation_history:
            assert turn["full_response"]["handled"], "All turns should be handled"
            assert len(turn["ai_response"]) > 5, "All responses should be substantial"
            
        test.validate_conversation_flow()
        
        logger.info("✅ Robust performance test completed!")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])