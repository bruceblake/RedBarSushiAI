"""
Test file for enhanced E2E scenarios.

This file demonstrates how to run the enhanced scenarios with
comprehensive validations.
"""

import pytest
import asyncio
from typing import Dict, Any

from tests.e2e.enhanced_e2e_runner import EnhancedE2ETestRunner
from tests.e2e.enhanced_conversation_scenarios import (
    ModifierScenarios, DeliveryScenarios, EnhancedHappyPathScenarios
)
from tests.e2e.test_helpers import ResponseAssertions


class TestEnhancedScenarios:
    """Test class for enhanced E2E scenarios."""
    
    @pytest.mark.asyncio
    async def test_poke_bowl_with_modifiers(self):
        """Test comprehensive poke bowl ordering with modifiers."""
        runner = EnhancedE2ETestRunner()
        scenario = ModifierScenarios.poke_bowl_with_modifiers()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # Basic assertions
            assert result.passed, f"Scenario failed: {result.errors}"
            assert result.turns_completed == result.turns_total
            
            # Check modifier selection occurred
            assert result.final_context is not None
            cart = result.final_context.get("cart", [])
            assert len(cart) > 0, "Cart should not be empty"
            
            # Verify poke bowl has modifiers
            poke_bowl = next((item for item in cart if "poke" in item.get("name", "").lower()), None)
            assert poke_bowl is not None, "Poke bowl not found in cart"
            assert poke_bowl.get("modifiers"), "Poke bowl should have modifiers"
            assert poke_bowl["modifiers"].get("size") == "large", "Size modifier not set correctly"
            assert len(poke_bowl["modifiers"].get("proteins", [])) >= 2, "Should have multiple proteins"
            
            # Check conversation quality
            quality = result.outcome_validation.get("conversation_quality", {})
            assert quality.get("quality_score", 0) >= 70, f"Low conversation quality: {quality}"
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_delivery_order_complete_flow(self):
        """Test complete delivery order with address collection."""
        runner = EnhancedE2ETestRunner()
        scenario = DeliveryScenarios.complete_delivery_order()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # Basic assertions
            assert result.passed, f"Scenario failed: {result.errors}"
            
            # Check delivery-specific validations
            assert result.final_context is not None
            assert result.final_context.get("order_type") == "delivery"
            assert result.final_context.get("delivery_address") is not None
            assert "123 Main" in result.final_context.get("delivery_address", "")
            assert "94105" in result.final_context.get("delivery_address", "")
            assert result.final_context.get("payment_method") == "credit_card"
            
            # Verify POS payload would be valid
            pos_validation = result.outcome_validation.get("pos_validation", {})
            if pos_validation:  # Only if order was submitted to mock POS
                assert pos_validation.get("valid"), f"POS validation failed: {pos_validation.get('errors')}"
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_enhanced_simple_order(self):
        """Test enhanced simple order with comprehensive validations."""
        runner = EnhancedE2ETestRunner()
        scenario = EnhancedHappyPathScenarios.enhanced_simple_pickup_order()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # Should pass with enhanced validations
            assert result.passed, f"Enhanced scenario failed: {result.errors}"
            
            # Check that AI responses were validated
            failed_turns = [t for t in result.turn_results if not t.passed]
            for turn in failed_turns:
                print(f"Failed turn {turn.turn_number}: {turn.error}")
                print(f"  User: {turn.message}")
                print(f"  AI: {turn.response[:100]}...")
            
            # Verify final outcome validations ran
            assert result.outcome_validation is not None
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_spice_level_modifier(self):
        """Test spice level modifier selection."""
        runner = EnhancedE2ETestRunner()
        scenario = ModifierScenarios.sushi_roll_spice_level()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            assert result.passed, f"Scenario failed: {result.errors}"
            
            # Check spice modifiers were applied
            cart = result.final_context.get("cart", []) if result.final_context else []
            
            # Find spicy tuna roll
            spicy_tuna = next((item for item in cart if "spicy tuna" in item.get("name", "").lower()), None)
            assert spicy_tuna is not None
            assert spicy_tuna.get("modifiers", {}).get("spice_level") in ["hot", "extra_spicy"]
            
            # Find salmon roll (should not be spicy)
            salmon = next((item for item in cart if "salmon" in item.get("name", "").lower() and "spicy" not in item.get("name", "").lower()), None)
            assert salmon is not None
            
        finally:
            await runner.teardown()


class TestResponseValidations:
    """Test the response validation helpers."""
    
    def test_greeting_validation(self):
        """Test greeting response validation."""
        valid_greetings = [
            "Welcome to Red Bar Sushi, how can I help you today?",
            "Hello! Thank you for calling Red Bar Sushi.",
            "Hi there! This is Red Bar Sushi, how may I assist you?"
        ]
        
        for greeting in valid_greetings:
            assert ResponseAssertions.assert_greeting(greeting)
        
        invalid_responses = [
            "What would you like to order?",
            "Your total is $25.99"
        ]
        
        for response in invalid_responses:
            assert not ResponseAssertions.assert_greeting(response)
    
    def test_order_confirmation_validation(self):
        """Test order confirmation validation."""
        items = ["california roll", "miso soup"]
        
        valid_confirmations = [
            "I have 2 California rolls and 1 miso soup. Is that correct?",
            "Your order includes: California Roll (2), Miso Soup (1). Total is $18.99",
            "Let me confirm your order: California roll and miso soup"
        ]
        
        for confirmation in valid_confirmations:
            assert ResponseAssertions.assert_order_confirmation(confirmation, items)
        
        invalid_confirmations = [
            "Thank you for your order",  # Missing items
            "I have sushi rolls",  # Too vague
        ]
        
        for confirmation in invalid_confirmations:
            assert not ResponseAssertions.assert_order_confirmation(confirmation, items)
    
    def test_quantity_extraction(self):
        """Test quantity extraction from responses."""
        test_cases = [
            ("I've added 2 California rolls to your order", "california roll", 2, True),
            ("Two spicy tuna rolls have been added", "spicy tuna roll", 2, True),
            ("California roll - quantity: 3", "california roll", 3, True),
            ("Added one salmon roll", "salmon roll", 1, True),
            ("I've added rolls to your order", "california roll", 2, False),  # No specific quantity
        ]
        
        for response, item, quantity, expected in test_cases:
            result = ResponseAssertions.assert_quantity_in_response(response, item, quantity)
            assert result == expected, f"Failed for: {response}"
    
    def test_price_extraction(self):
        """Test price extraction from responses."""
        test_cases = [
            ("Your total is $25.99", 25.99),
            ("That comes to 18.50 dollars", 18.50),
            ("Total: $42", 42.0),
            ("The total is thirty dollars", None),  # Word form not supported
        ]
        
        for response, expected_price in test_cases:
            extracted = ResponseAssertions.extract_price_from_response(response)
            if expected_price is not None:
                assert extracted == expected_price
            else:
                assert extracted is None


@pytest.mark.asyncio
async def test_run_enhanced_suite():
    """Run the complete enhanced test suite."""
    from tests.e2e.enhanced_e2e_runner import run_enhanced_e2e_tests
    
    report = await run_enhanced_e2e_tests()
    
    # Suite should have reasonable pass rate
    assert report["summary"]["pass_rate"] >= 0.7, "Enhanced suite pass rate too low"
    
    # Check specific categories
    enhanced_metrics = report.get("enhanced_metrics", {})
    
    # Modifier tests should work
    modifier_stats = enhanced_metrics.get("modifier_tests", {})
    if modifier_stats.get("total", 0) > 0:
        assert modifier_stats.get("passed", 0) > 0, "No modifier tests passed"
    
    # Quality should be acceptable
    avg_quality = enhanced_metrics.get("avg_conversation_quality", 0)
    assert avg_quality >= 60, f"Conversation quality too low: {avg_quality}"