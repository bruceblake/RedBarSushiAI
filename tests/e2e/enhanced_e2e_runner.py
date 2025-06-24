"""
Enhanced E2E Test Runner with support for comprehensive validations.

This runner extends the base E2E runner with better validation support
and test infrastructure for the enhanced scenarios.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from tests.e2e.e2e_test_runner import E2ETestRunner, ScenarioResult
from tests.e2e.test_helpers import (
    ResponseAssertions, MockPOSService, ConversationAnalyzer, POSPayload
)
from tests.e2e.enhanced_conversation_scenarios import get_enhanced_scenarios
from tests.e2e.conversation_scenarios import ConversationScenario

logger = logging.getLogger(__name__)


class EnhancedE2ETestRunner(E2ETestRunner):
    """Enhanced E2E test runner with comprehensive validations."""
    
    def __init__(self, base_url: str = None, ws_url: str = None):
        super().__init__(base_url, ws_url)
        self.mock_pos = MockPOSService()
        self.response_assertions = ResponseAssertions()
        self.conversation_analyzer = ConversationAnalyzer()
        
    async def run_scenario(self, scenario: ConversationScenario) -> ScenarioResult:
        """Run scenario with enhanced validations."""
        logger.info(f"Running enhanced scenario: {scenario.name}")
        
        # Configure mocks if needed
        if "pos_failure" in scenario.tags:
            self.mock_pos.set_failure_mode(True, max_failures=1)
        else:
            self.mock_pos.set_failure_mode(False)
        
        # Run base scenario
        result = await super().run_scenario(scenario)
        
        # Add enhanced validations
        if scenario.expected_outcome:
            # Validate final cart if specified
            if "final_cart_validation" in scenario.expected_outcome:
                cart = result.final_context.get("cart", []) if result.final_context else []
                cart_valid = scenario.expected_outcome["final_cart_validation"](cart)
                if not cart_valid:
                    result.errors.append("Final cart validation failed")
                    result.passed = False
            
            # Validate POS payload if order was placed
            if scenario.expected_outcome.get("order_placed") and self.mock_pos.get_last_order():
                pos_order = self.mock_pos.get_last_order()
                pos_payload = POSPayload(
                    order_id=pos_order.get("order_id", ""),
                    items=pos_order.get("items", []),
                    customer=pos_order.get("customer", {}),
                    order_type=pos_order.get("order_type", ""),
                    payment_method=pos_order.get("payment_method"),
                    delivery_address=pos_order.get("delivery_address")
                )
                
                validation = pos_payload.validate()
                if not validation["valid"]:
                    result.errors.extend(validation["errors"])
                    result.passed = False
                
                # Store validation results
                if not result.outcome_validation:
                    result.outcome_validation = {}
                result.outcome_validation["pos_validation"] = validation
        
        # Analyze conversation quality
        conversation_analysis = self.conversation_analyzer.analyze_conversation_flow(
            [turn.__dict__ for turn in result.turn_results]
        )
        
        if conversation_analysis["quality_score"] < 70:
            logger.warning(f"Low conversation quality score: {conversation_analysis['quality_score']}")
            logger.warning(f"Issues: {conversation_analysis['issues']}")
        
        # Add analysis to result
        if not result.outcome_validation:
            result.outcome_validation = {}
        result.outcome_validation["conversation_quality"] = conversation_analysis
        
        return result
    
    async def run_enhanced_test_suite(self) -> Dict[str, Any]:
        """Run the enhanced E2E test suite."""
        logger.info("Starting Enhanced E2E Test Suite")
        
        # Get enhanced scenarios
        scenarios = get_enhanced_scenarios()
        
        # Filter to priority scenarios for initial run
        priority_tags = ["modifiers", "delivery", "enhanced"]
        priority_scenarios = [
            s for s in scenarios 
            if any(tag in s.tags for tag in priority_tags)
        ]
        
        logger.info(f"Running {len(priority_scenarios)} priority scenarios")
        
        # Run scenarios
        results = []
        for scenario in priority_scenarios:
            try:
                result = await self.run_scenario(scenario)
                results.append(result)
                
                # Log detailed results
                logger.info(f"Scenario: {scenario.name}")
                logger.info(f"  Result: {'PASSED' if result.passed else 'FAILED'}")
                logger.info(f"  Turns: {result.turns_completed}/{result.turns_total}")
                logger.info(f"  Quality Score: {result.outcome_validation.get('conversation_quality', {}).get('quality_score', 'N/A')}")
                
                if not result.passed:
                    logger.error(f"  Errors: {result.errors}")
                    
            except Exception as e:
                logger.error(f"Failed to run scenario {scenario.name}: {e}")
                
        # Generate comprehensive report
        report = self._generate_enhanced_report(results)
        
        return report
    
    def _generate_enhanced_report(self, results: List[ScenarioResult]) -> Dict[str, Any]:
        """Generate enhanced test report with detailed analysis."""
        base_report = self.generate_report()
        
        # Add enhanced metrics
        total_quality_score = sum(
            r.outcome_validation.get("conversation_quality", {}).get("quality_score", 0)
            for r in results if r.outcome_validation
        ) / max(len(results), 1)
        
        # Check specific validations
        modifier_tests = [r for r in results if any("modifier" in tag for tag in ["modifiers"])]
        delivery_tests = [r for r in results if any("delivery" in tag for tag in ["delivery"])]
        
        enhanced_metrics = {
            "avg_conversation_quality": total_quality_score,
            "modifier_tests": {
                "total": len(modifier_tests),
                "passed": sum(1 for r in modifier_tests if r.passed)
            },
            "delivery_tests": {
                "total": len(delivery_tests),
                "passed": sum(1 for r in delivery_tests if r.passed)
            },
            "pos_validations": {
                "total": sum(1 for r in results if r.outcome_validation and "pos_validation" in r.outcome_validation),
                "valid": sum(
                    1 for r in results 
                    if r.outcome_validation and 
                    r.outcome_validation.get("pos_validation", {}).get("valid", False)
                )
            }
        }
        
        base_report["enhanced_metrics"] = enhanced_metrics
        
        # Add specific test insights
        insights = []
        
        if enhanced_metrics["modifier_tests"]["passed"] < enhanced_metrics["modifier_tests"]["total"]:
            insights.append("⚠️ Modifier selection tests need attention")
            
        if enhanced_metrics["delivery_tests"]["passed"] < enhanced_metrics["delivery_tests"]["total"]:
            insights.append("⚠️ Delivery flow tests have failures")
            
        if total_quality_score < 80:
            insights.append("⚠️ Overall conversation quality could be improved")
            
        if enhanced_metrics["pos_validations"]["valid"] < enhanced_metrics["pos_validations"]["total"]:
            insights.append("⚠️ POS payload validation issues detected")
        
        base_report["insights"] = insights
        
        return base_report


async def run_enhanced_e2e_tests():
    """Run the enhanced E2E test suite."""
    runner = EnhancedE2ETestRunner()
    
    try:
        await runner.setup()
        report = await runner.run_enhanced_test_suite()
        
        # Print summary
        print("\n" + "="*60)
        print("ENHANCED E2E TEST SUITE RESULTS")
        print("="*60)
        
        summary = report["summary"]
        print(f"\nTotal Scenarios: {summary['total_scenarios']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']:.1%})")
        print(f"Failed: {summary['failed']}")
        
        enhanced = report.get("enhanced_metrics", {})
        print(f"\nAverage Conversation Quality: {enhanced.get('avg_conversation_quality', 0):.1f}/100")
        
        print("\nTest Categories:")
        print(f"  Modifiers: {enhanced.get('modifier_tests', {}).get('passed', 0)}/{enhanced.get('modifier_tests', {}).get('total', 0)}")
        print(f"  Delivery: {enhanced.get('delivery_tests', {}).get('passed', 0)}/{enhanced.get('delivery_tests', {}).get('total', 0)}")
        print(f"  POS Valid: {enhanced.get('pos_validations', {}).get('valid', 0)}/{enhanced.get('pos_validations', {}).get('total', 0)}")
        
        if report.get("insights"):
            print("\nInsights:")
            for insight in report["insights"]:
                print(f"  {insight}")
        
        print("="*60 + "\n")
        
        return report
        
    finally:
        await runner.teardown()


if __name__ == "__main__":
    asyncio.run(run_enhanced_e2e_tests())