"""
Test cases for help and escalation E2E scenarios.

This module tests the help request and human escalation flows.
"""

import pytest
import asyncio
from typing import Dict, Any

from tests.e2e.enhanced_e2e_runner import EnhancedE2ETestRunner
from tests.e2e.escalation_scenarios import HelpEscalationScenarios, get_help_escalation_scenarios
from tests.e2e.test_helpers import ResponseAssertions, ConversationAnalyzer


class TestHelpEscalationScenarios:
    """Test class for help and escalation scenarios."""
    
    @pytest.mark.asyncio
    async def test_immediate_help_request(self):
        """Test customer requesting help at start of call."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.immediate_help_request()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # Basic assertions
            assert result.passed, f"Scenario failed: {result.errors}"
            assert result.turns_completed == result.turns_total
            
            # Verify help was provided
            help_turns = [
                t for t in result.turn_results 
                if "help" in t.message.lower() and t.speaker == "user"
            ]
            assert len(help_turns) > 0, "No help requests found"
            
            # Check that AI provided helpful responses
            for turn in help_turns:
                assert turn.response and len(turn.response) > 20, "Help response too short"
            
            # Verify customer proceeded to order after help
            assert result.final_state == "VALIDATION" or result.final_state == "ORDERING"
            assert len(result.final_context.get("cart", [])) > 0, "No items ordered after help"
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_manager_escalation_request(self):
        """Test explicit request to speak to a manager."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.manager_escalation()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # Should complete even if escalation state is terminal
            assert result.turns_completed >= 4, "Not enough turns completed"
            
            # Verify escalation was triggered
            escalation_turn = next(
                (t for t in result.turn_results if "speak to a manager" in t.message),
                None
            )
            assert escalation_turn is not None
            assert escalation_turn.state == "ESCALATION" or escalation_turn.agent == "escalation"
            
            # Check appropriate escalation response
            assert any(word in escalation_turn.response.lower() for word in [
                "transfer", "connect", "manager", "representative", "human"
            ]), "Escalation response missing key words"
            
            # Verify context tracking
            assert result.final_context.get("escalation_requested") == True
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_escalation_then_continue(self):
        """Test customer changing mind about escalation."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.escalation_then_continue()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            assert result.passed, f"Scenario failed: {result.errors}"
            
            # Verify escalation was considered but not completed
            escalation_request_turn = next(
                (t for t in result.turn_results if "speak to a person" in t.message),
                None
            )
            assert escalation_request_turn is not None
            
            # Verify continuation after escalation request
            continue_turn = next(
                (t for t in result.turn_results if "never mind" in t.message.lower()),
                None
            )
            assert continue_turn is not None
            assert continue_turn.state == "ORDERING"
            
            # Verify order was completed
            assert len(result.final_context.get("cart", [])) >= 2
            assert result.final_state in ["VALIDATION", "CONFIRMATION", "COMPLETED"]
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_allergy_help_request(self):
        """Test help with dietary restrictions and allergies."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.help_with_menu_allergies()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            assert result.passed, f"Scenario failed: {result.errors}"
            
            # Verify allergy was acknowledged
            allergy_turns = [
                t for t in result.turn_results 
                if "shellfish" in t.message.lower() and t.speaker == "user"
            ]
            assert len(allergy_turns) > 0
            
            # Check AI responses mention safe options
            for turn in allergy_turns:
                next_ai_turn = next(
                    (t for t in result.turn_results 
                     if t.turn_number > turn.turn_number and t.speaker != "user"),
                    None
                )
                if next_ai_turn:
                    response_lower = next_ai_turn.response.lower()
                    assert any(word in response_lower for word in [
                        "shellfish", "avoid", "safe", "vegetable", "california"
                    ]), "AI didn't acknowledge allergy properly"
            
            # Verify safe item was ordered
            cart = result.final_context.get("cart", [])
            assert len(cart) > 0
            ordered_items = [item.get("name", "").lower() for item in cart]
            # Should not have any shellfish items
            shellfish_items = ["shrimp", "crab", "lobster", "shellfish"]
            assert not any(
                shellfish in item_name 
                for item_name in ordered_items 
                for shellfish in shellfish_items
            ), "Shellfish item ordered despite allergy"
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_frustrated_customer_escalation(self):
        """Test escalation triggered by customer frustration."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.frustrated_customer_escalation()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            # May not fully pass if escalation is terminal, but should handle gracefully
            assert result.turns_completed >= 5, "Should complete most turns"
            
            # Verify AI tried to help before escalation
            help_attempts = [
                t for t in result.turn_results
                if t.speaker != "user" and any(word in t.response.lower() for word in [
                    "help", "describe", "which", "what"
                ])
            ]
            assert len(help_attempts) >= 2, "AI should attempt to help before escalating"
            
            # Verify escalation was triggered by frustration
            frustration_turn = next(
                (t for t in result.turn_results if "too difficult" in t.message),
                None
            )
            assert frustration_turn is not None
            
            # Check empathetic response
            assert any(word in frustration_turn.response.lower() for word in [
                "understand", "help", "sorry", "transfer", "connect"
            ]), "Response should be empathetic"
            
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_technical_help_success(self):
        """Test technical help that resolves the issue."""
        runner = EnhancedE2ETestRunner()
        scenario = HelpEscalationScenarios.technical_help_request()
        
        await runner.setup()
        try:
            result = await runner.run_scenario(scenario)
            
            assert result.passed, f"Scenario failed: {result.errors}"
            
            # Verify technical help was provided
            help_turn = next(
                (t for t in result.turn_results if "how do I remove" in t.message),
                None
            )
            assert help_turn is not None
            assert len(help_turn.response) > 50, "Technical help should be detailed"
            
            # Verify customer successfully used the feature
            removal_turn = next(
                (t for t in result.turn_results if "remove one" in t.message),
                None
            )
            assert removal_turn is not None
            assert any(word in removal_turn.response.lower() for word in [
                "removed", "updated", "changed", "now have 2"
            ])
            
            # Verify final cart reflects the change
            cart = result.final_context.get("cart", [])
            california_roll = next(
                (item for item in cart if "california" in item.get("name", "").lower()),
                None
            )
            assert california_roll is not None
            assert california_roll.get("quantity") == 2, "Quantity should be reduced to 2"
            
        finally:
            await runner.teardown()


class TestEscalationPatterns:
    """Test various escalation patterns and edge cases."""
    
    @pytest.mark.asyncio
    async def test_escalation_keywords(self):
        """Test that various escalation keywords trigger appropriate responses."""
        runner = EnhancedE2ETestRunner()
        
        escalation_phrases = [
            "I want to speak to a human",
            "Get me a real person",
            "Transfer me to customer service",
            "I need a manager",
            "This is an emergency",
            "I want to file a complaint"
        ]
        
        await runner.setup()
        try:
            for phrase in escalation_phrases:
                # Create a mini scenario for each phrase
                from tests.e2e.conversation_scenarios import ConversationScenario, ConversationTurn
                
                scenario = ConversationScenario(
                    id=f"escalation_keyword_{escalation_phrases.index(phrase)}",
                    name=f"Escalation: {phrase[:20]}",
                    description="Test escalation keyword",
                    scenario_type=ScenarioType.ERROR_RECOVERY,
                    turns=[
                        ConversationTurn(
                            speaker="system",
                            message="",
                            expected_state="GREETING"
                        ),
                        ConversationTurn(
                            speaker="user",
                            message="Hello",
                            expected_state="MAIN_MENU"
                        ),
                        ConversationTurn(
                            speaker="user",
                            message=phrase,
                            validation_function=lambda resp: any([
                                "transfer" in resp.lower(),
                                "connect" in resp.lower(),
                                "help" in resp.lower(),
                                "manager" in resp.lower(),
                                "representative" in resp.lower()
                            ])
                        )
                    ],
                    tags=["escalation", "keyword_test"]
                )
                
                result = await runner.run_scenario(scenario)
                
                # Should recognize escalation intent
                escalation_turn = result.turn_results[-1]
                assert any(word in escalation_turn.response.lower() for word in [
                    "transfer", "connect", "manager", "help", "representative"
                ]), f"Failed to recognize escalation for: {phrase}"
                
        finally:
            await runner.teardown()
    
    @pytest.mark.asyncio
    async def test_help_conversation_quality(self):
        """Test that help scenarios maintain high conversation quality."""
        runner = EnhancedE2ETestRunner()
        scenarios = get_help_escalation_scenarios()
        
        await runner.setup()
        try:
            quality_scores = []
            
            for scenario in scenarios:
                result = await runner.run_scenario(scenario)
                
                quality = result.outcome_validation.get("conversation_quality", {})
                quality_score = quality.get("quality_score", 0)
                quality_scores.append(quality_score)
                
                # Help scenarios should maintain good quality
                assert quality_score >= 60, f"Low quality in {scenario.name}: {quality}"
                
                # Check for specific quality issues
                issues = quality.get("issues", [])
                assert "Very short response" not in str(issues), "Help responses too short"
            
            # Average quality should be good across all help scenarios
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            assert avg_quality >= 70, f"Average help scenario quality too low: {avg_quality}"
            
        finally:
            await runner.teardown()


@pytest.mark.asyncio
async def test_complete_help_escalation_suite():
    """Run all help and escalation scenarios as a suite."""
    runner = EnhancedE2ETestRunner()
    scenarios = get_help_escalation_scenarios()
    
    await runner.setup()
    try:
        results = []
        for scenario in scenarios:
            result = await runner.run_scenario(scenario)
            results.append({
                "scenario": scenario.name,
                "passed": result.passed,
                "state": result.final_state,
                "errors": result.errors
            })
        
        # Summary
        passed = sum(1 for r in results if r["passed"])
        print(f"\nHelp/Escalation Suite Results: {passed}/{len(results)} passed")
        
        # At least 70% should pass (some escalation scenarios may be terminal)
        assert passed / len(results) >= 0.7, "Too many help/escalation scenarios failed"
        
        # Specific checks
        help_scenarios = [r for r in results if "help" in r["scenario"].lower()]
        escalation_scenarios = [r for r in results if "escalation" in r["scenario"].lower()]
        
        # Most help scenarios should fully pass
        help_passed = sum(1 for r in help_scenarios if r["passed"])
        assert help_passed / len(help_scenarios) >= 0.8, "Help scenarios have low pass rate"
        
    finally:
        await runner.teardown()