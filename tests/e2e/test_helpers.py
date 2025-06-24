"""
Test helper utilities for E2E testing.

Provides enhanced assertion capabilities and test infrastructure.
"""

import re
from typing import Dict, Any, List, Optional, Callable
import json
from dataclasses import dataclass


@dataclass
class POSPayload:
    """Mock POS payload structure for validation."""
    order_id: str
    items: List[Dict[str, Any]]
    customer: Dict[str, Any]
    order_type: str
    payment_method: Optional[str] = None
    delivery_address: Optional[str] = None
    scheduled_time: Optional[str] = None
    special_instructions: Optional[str] = None
    
    def validate(self) -> Dict[str, Any]:
        """Validate POS payload structure."""
        errors = []
        
        # Check required fields
        if not self.order_id:
            errors.append("Missing order_id")
        
        if not self.items:
            errors.append("No items in order")
        
        # Validate each item
        for i, item in enumerate(self.items):
            if not item.get("plu"):
                errors.append(f"Item {i} missing PLU")
            if not item.get("name"):
                errors.append(f"Item {i} missing name")
            if item.get("quantity", 0) <= 0:
                errors.append(f"Item {i} invalid quantity")
            if item.get("unit_price", 0) <= 0:
                errors.append(f"Item {i} invalid price")
        
        # Validate customer info
        if not self.customer.get("phone"):
            errors.append("Missing customer phone")
        
        # Validate delivery requirements
        if self.order_type == "delivery":
            if not self.delivery_address:
                errors.append("Delivery order missing address")
            if not self.payment_method:
                errors.append("Delivery order missing payment method")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "item_count": len(self.items),
            "total_quantity": sum(item.get("quantity", 0) for item in self.items),
            "total_price": sum(
                item.get("quantity", 0) * item.get("unit_price", 0) 
                for item in self.items
            )
        }


class ResponseAssertions:
    """Enhanced assertions for AI responses."""
    
    @staticmethod
    def assert_greeting(response: str) -> bool:
        """Validate greeting response."""
        greetings = [
            "welcome", "hello", "hi", "good", "thank you for calling",
            "red bar sushi", "how can i help", "how may i assist"
        ]
        response_lower = response.lower()
        return any(greeting in response_lower for greeting in greetings)
    
    @staticmethod
    def assert_order_confirmation(response: str, expected_items: List[str]) -> bool:
        """Validate order confirmation contains all items."""
        response_lower = response.lower()
        
        # Check for confirmation language
        confirmation_words = ["order", "have", "confirm", "total", "includes"]
        if not any(word in response_lower for word in confirmation_words):
            return False
        
        # Check all items are mentioned
        for item in expected_items:
            if item.lower() not in response_lower:
                return False
        
        return True
    
    @staticmethod
    def assert_modifier_request(response: str, modifier_type: str) -> bool:
        """Validate AI is asking for specific modifier."""
        response_lower = response.lower()
        
        modifier_prompts = {
            "size": ["what size", "regular or large", "small, medium", "size would you"],
            "spice": ["how spicy", "spice level", "mild, medium", "hot"],
            "protein": ["which protein", "what kind of", "salmon", "tuna", "chicken"],
            "toppings": ["toppings", "would you like", "anything else", "add any"],
            "sauce": ["sauce", "on the side", "extra", "which sauce"]
        }
        
        expected_prompts = modifier_prompts.get(modifier_type, [])
        return any(prompt in response_lower for prompt in expected_prompts)
    
    @staticmethod
    def assert_quantity_in_response(response: str, item: str, quantity: int) -> bool:
        """Validate response mentions correct quantity of item."""
        response_lower = response.lower()
        item_lower = item.lower()
        
        # Check item is mentioned
        if item_lower not in response_lower:
            return False
        
        # Check quantity (handle both numeric and word forms)
        quantity_words = {
            1: ["1", "one", "a ", "an "],
            2: ["2", "two", "couple", "pair"],
            3: ["3", "three"],
            4: ["4", "four"],
            5: ["5", "five"],
            6: ["6", "six"]
        }
        
        expected_quantities = quantity_words.get(quantity, [str(quantity)])
        
        # Look for quantity near the item name
        for q in expected_quantities:
            # Create patterns to find quantity near item
            patterns = [
                f"{q} {item_lower}",
                f"{q} .{{0,20}} {item_lower}",  # Allow words between
                f"{item_lower} .{{0,10}} {q}"   # Quantity after item
            ]
            
            for pattern in patterns:
                if re.search(pattern, response_lower):
                    return True
        
        return False
    
    @staticmethod
    def extract_price_from_response(response: str) -> Optional[float]:
        """Extract price mentioned in response."""
        # Look for price patterns
        price_patterns = [
            r'\$(\d+\.?\d*)',           # $12.99
            r'(\d+\.?\d*) dollars?',     # 12.99 dollars
            r'total.{0,10}\$(\d+\.?\d*)', # total is $12.99
            r'total.{0,10}(\d+\.?\d*)',   # total: 12.99
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, response.lower())
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        return None


class MockPOSService:
    """Mock POS service for testing failure scenarios."""
    
    def __init__(self):
        self.should_fail = False
        self.failure_count = 0
        self.max_failures = 1
        self.submitted_orders = []
    
    def set_failure_mode(self, should_fail: bool, max_failures: int = 1):
        """Configure failure behavior."""
        self.should_fail = should_fail
        self.max_failures = max_failures
        self.failure_count = 0
    
    async def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mock order submission."""
        # Convert to POSPayload for validation
        pos_payload = POSPayload(
            order_id=payload.get("order_id", ""),
            items=payload.get("items", []),
            customer=payload.get("customer", {}),
            order_type=payload.get("order_type", ""),
            payment_method=payload.get("payment_method"),
            delivery_address=payload.get("delivery_address")
        )
        
        validation = pos_payload.validate()
        
        # Check if we should fail
        if self.should_fail and self.failure_count < self.max_failures:
            self.failure_count += 1
            return {
                "success": False,
                "error": "POS system temporarily unavailable",
                "retry_available": True
            }
        
        # Store successful submission
        self.submitted_orders.append(payload)
        
        return {
            "success": True,
            "order_number": f"#{len(self.submitted_orders):04d}",
            "estimated_time": "20 minutes",
            "validation": validation
        }
    
    def get_last_order(self) -> Optional[Dict[str, Any]]:
        """Get the last submitted order."""
        return self.submitted_orders[-1] if self.submitted_orders else None


class ConversationAnalyzer:
    """Analyze conversation quality and patterns."""
    
    @staticmethod
    def analyze_conversation_flow(turns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze conversation for quality metrics."""
        total_turns = len(turns)
        user_turns = [t for t in turns if t.get("speaker") == "user"]
        ai_turns = [t for t in turns if t.get("speaker") == "assistant"]
        
        # Calculate metrics
        avg_response_time = sum(t.get("response_time", 0) for t in ai_turns) / max(len(ai_turns), 1)
        
        # Check for conversation issues
        issues = []
        
        # Check for repeated responses
        ai_responses = [t.get("response", "") for t in ai_turns]
        for i in range(1, len(ai_responses)):
            if ai_responses[i] == ai_responses[i-1]:
                issues.append(f"Repeated response at turn {i}")
        
        # Check for very short responses
        for i, turn in enumerate(ai_turns):
            if len(turn.get("response", "")) < 10:
                issues.append(f"Very short response at turn {i}")
        
        # Check for missing confirmations
        confirmation_words = ["yes", "correct", "confirm", "right"]
        for turn in user_turns:
            if any(word in turn.get("message", "").lower() for word in confirmation_words):
                # Check if AI acknowledged
                next_ai = next((t for t in ai_turns if t.get("turn_number", 0) > turn.get("turn_number", 0)), None)
                if next_ai and not any(
                    word in next_ai.get("response", "").lower() 
                    for word in ["got it", "understood", "confirmed", "perfect"]
                ):
                    issues.append(f"Missing acknowledgment after user confirmation")
        
        return {
            "total_turns": total_turns,
            "user_turns": len(user_turns),
            "ai_turns": len(ai_turns),
            "avg_response_time": avg_response_time,
            "issues": issues,
            "quality_score": max(0, 100 - (len(issues) * 10))  # Deduct 10 points per issue
        }