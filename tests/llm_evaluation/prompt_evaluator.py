"""
LLM Prompt Evaluator for RedBarSushiAI.

This module provides tools for evaluating the quality and accuracy of LLM prompts
used throughout the system, including intent detection, response generation,
and function calling.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import csv
import os
from openai import AsyncOpenAI

from app.config import settings
from app.utils.intent_detector_async import AsyncIntentDetector
from app.utils.global_commands import GlobalCommandDetector
from app.fsm.core import ConversationState
from tests.llm_evaluation.prompt_test_cases import (
    PromptTestCase, TestCategory, get_all_test_cases,
    get_test_cases_by_category, get_test_cases_by_tags
)

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test case evaluation."""
    test_id: str
    category: str
    description: str
    passed: bool
    actual_output: str
    expected_outputs: List[str]
    execution_time: float
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    model_used: str = "gpt-4o-mini"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PromptEvaluator:
    """Evaluates LLM prompts for quality and accuracy."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the evaluator with specified model."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        self.intent_detector = AsyncIntentDetector()
        self.global_command_detector = GlobalCommandDetector()
        self.results: List[TestResult] = []
    
    async def evaluate_test_case(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate a single test case."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if test_case.category == TestCategory.INTENT_DETECTION:
                result = await self._evaluate_intent_detection(test_case)
            elif test_case.category == TestCategory.AGENT_RESPONSE:
                result = await self._evaluate_agent_response(test_case)
            elif test_case.category == TestCategory.FUNCTION_CALLING:
                result = await self._evaluate_function_calling(test_case)
            elif test_case.category == TestCategory.DISAMBIGUATION:
                result = await self._evaluate_disambiguation(test_case)
            elif test_case.category == TestCategory.GLOBAL_COMMANDS:
                result = await self._evaluate_global_commands(test_case)
            else:
                result = TestResult(
                    test_id=test_case.id,
                    category=test_case.category.value,
                    description=test_case.description,
                    passed=False,
                    actual_output="",
                    expected_outputs=test_case.expected_outputs,
                    execution_time=0,
                    error_message=f"Unknown test category: {test_case.category}"
                )
            
            result.execution_time = asyncio.get_event_loop().time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating test case {test_case.id}: {e}")
            return TestResult(
                test_id=test_case.id,
                category=test_case.category.value,
                description=test_case.description,
                passed=False,
                actual_output="",
                expected_outputs=test_case.expected_outputs,
                execution_time=asyncio.get_event_loop().time() - start_time,
                error_message=str(e)
            )
    
    async def _evaluate_intent_detection(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate intent detection accuracy."""
        # Convert state string to ConversationState enum
        state = ConversationState[test_case.context.get("state", "GREETING")]
        
        # Detect intent
        detected_event = await self.intent_detector.detect_intent(
            transcript=test_case.user_input,
            current_state=state,
            context=test_case.context
        )
        
        # Get the intent name
        detected_intent = detected_event.name if detected_event else "NONE"
        
        # Check if detected intent matches expected
        passed = False
        if test_case.expected_intent:
            passed = detected_intent == test_case.expected_intent
        else:
            # Check against expected outputs
            passed = any(
                detected_intent.lower() in expected.lower() 
                for expected in test_case.expected_outputs
            )
        
        return TestResult(
            test_id=test_case.id,
            category=test_case.category.value,
            description=test_case.description,
            passed=passed,
            actual_output=detected_intent,
            expected_outputs=test_case.expected_outputs,
            execution_time=0  # Will be set by caller
        )
    
    async def _evaluate_agent_response(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate agent response generation."""
        # Build messages
        messages = [
            {"role": "system", "content": test_case.system_prompt}
        ]
        
        if test_case.user_input:
            messages.append({"role": "user", "content": test_case.user_input})
        
        # Add context as system message if needed
        if test_case.context:
            context_msg = f"Context: {json.dumps(test_case.context)}"
            messages.append({"role": "system", "content": context_msg})
        
        # Get response from LLM
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=150
        )
        
        actual_output = response.choices[0].message.content.strip()
        
        # Check if response contains expected elements
        passed = any(
            expected.lower() in actual_output.lower()
            for expected in test_case.expected_outputs
        )
        
        return TestResult(
            test_id=test_case.id,
            category=test_case.category.value,
            description=test_case.description,
            passed=passed,
            actual_output=actual_output,
            expected_outputs=test_case.expected_outputs,
            execution_time=0,
            model_used=self.model
        )
    
    async def _evaluate_function_calling(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate function calling accuracy."""
        # Prepare function definitions
        functions = []
        if "available_functions" in test_case.context:
            for func_name in test_case.context["available_functions"]:
                functions.append({
                    "name": func_name,
                    "description": f"Function to {func_name.replace('_', ' ')}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                })
        
        messages = [
            {"role": "system", "content": test_case.system_prompt},
            {"role": "user", "content": test_case.user_input}
        ]
        
        # Make request with function calling
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
        
        if functions:
            request_params["functions"] = functions
            request_params["function_call"] = "auto"
        
        response = await self.client.chat.completions.create(**request_params)
        
        # Check function call
        message = response.choices[0].message
        actual_function = None
        
        if hasattr(message, 'function_call') and message.function_call:
            actual_function = message.function_call.name
        
        # Evaluate result
        if test_case.expected_function is None:
            # Should not call any function
            passed = actual_function is None
            actual_output = "No function called" if passed else f"Called: {actual_function}"
        else:
            # Should call specific function
            passed = actual_function == test_case.expected_function
            actual_output = actual_function or "No function called"
        
        return TestResult(
            test_id=test_case.id,
            category=test_case.category.value,
            description=test_case.description,
            passed=passed,
            actual_output=actual_output,
            expected_outputs=test_case.expected_outputs,
            execution_time=0
        )
    
    async def _evaluate_disambiguation(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate disambiguation handling."""
        messages = [
            {"role": "system", "content": test_case.system_prompt},
            {"role": "system", "content": f"Context: {json.dumps(test_case.context)}"},
            {"role": "user", "content": test_case.user_input}
        ]
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=200
        )
        
        actual_output = response.choices[0].message.content.strip()
        
        # Check if all expected elements are mentioned
        mentioned_count = sum(
            1 for expected in test_case.expected_outputs
            if expected.lower() in actual_output.lower()
        )
        
        # Pass if most expected elements are mentioned
        passed = mentioned_count >= len(test_case.expected_outputs) * 0.7
        
        return TestResult(
            test_id=test_case.id,
            category=test_case.category.value,
            description=test_case.description,
            passed=passed,
            actual_output=actual_output,
            expected_outputs=test_case.expected_outputs,
            execution_time=0,
            confidence_score=mentioned_count / len(test_case.expected_outputs)
        )
    
    async def _evaluate_global_commands(self, test_case: PromptTestCase) -> TestResult:
        """Evaluate global command detection."""
        command, confidence = self.global_command_detector.detect_command(
            test_case.user_input
        )
        
        detected_command = command.value if command else "NONE"
        
        # Check if matches expected
        passed = False
        if test_case.expected_intent:
            passed = detected_command == test_case.expected_intent
        else:
            passed = any(
                detected_command.lower() in expected.lower()
                for expected in test_case.expected_outputs
            )
        
        return TestResult(
            test_id=test_case.id,
            category=test_case.category.value,
            description=test_case.description,
            passed=passed,
            actual_output=detected_command,
            expected_outputs=test_case.expected_outputs,
            execution_time=0,
            confidence_score=confidence
        )
    
    async def evaluate_all(self, test_cases: List[PromptTestCase] = None) -> List[TestResult]:
        """Evaluate all test cases or a specific list."""
        if test_cases is None:
            test_cases = get_all_test_cases()
        
        self.results = []
        
        # Run evaluations concurrently in batches
        batch_size = 5
        for i in range(0, len(test_cases), batch_size):
            batch = test_cases[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.evaluate_test_case(tc) for tc in batch]
            )
            self.results.extend(batch_results)
            
            # Log progress
            logger.info(f"Evaluated {min(i + batch_size, len(test_cases))}/{len(test_cases)} test cases")
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate evaluation report."""
        if not self.results:
            return {"error": "No results to report"}
        
        # Calculate metrics by category
        category_metrics = {}
        for category in TestCategory:
            category_results = [
                r for r in self.results 
                if r.category == category.value
            ]
            
            if category_results:
                passed = sum(1 for r in category_results if r.passed)
                total = len(category_results)
                category_metrics[category.value] = {
                    "total": total,
                    "passed": passed,
                    "failed": total - passed,
                    "pass_rate": passed / total,
                    "avg_execution_time": sum(r.execution_time for r in category_results) / total
                }
        
        # Overall metrics
        total_tests = len(self.results)
        total_passed = sum(1 for r in self.results if r.passed)
        
        # Failed tests details
        failed_tests = [
            {
                "test_id": r.test_id,
                "category": r.category,
                "description": r.description,
                "expected": r.expected_outputs,
                "actual": r.actual_output,
                "error": r.error_message
            }
            for r in self.results if not r.passed
        ]
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_tests - total_passed,
                "overall_pass_rate": total_passed / total_tests if total_tests > 0 else 0,
                "evaluation_date": datetime.now().isoformat(),
                "model_used": self.model
            },
            "category_metrics": category_metrics,
            "failed_tests": failed_tests[:10],  # Top 10 failures
            "execution_stats": {
                "total_time": sum(r.execution_time for r in self.results),
                "avg_time_per_test": sum(r.execution_time for r in self.results) / total_tests
            }
        }
    
    def save_results(self, filepath: str = "prompt_evaluation_results.csv"):
        """Save results to CSV file."""
        if not self.results:
            logger.warning("No results to save")
            return
        
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        
        with open(filepath, 'w', newline='') as f:
            fieldnames = [
                'test_id', 'category', 'description', 'passed',
                'actual_output', 'expected_outputs', 'execution_time',
                'confidence_score', 'error_message', 'timestamp'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                row = asdict(result)
                row['expected_outputs'] = json.dumps(row['expected_outputs'])
                row['timestamp'] = row['timestamp'].isoformat()
                writer.writerow(row)
        
        logger.info(f"Results saved to {filepath}")


async def run_evaluation(
    categories: List[TestCategory] = None,
    tags: List[str] = None,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """Run prompt evaluation with specified filters."""
    evaluator = PromptEvaluator(model=model)
    
    # Get test cases based on filters
    if categories:
        test_cases = []
        for category in categories:
            test_cases.extend(get_test_cases_by_category(category))
    elif tags:
        test_cases = get_test_cases_by_tags(tags)
    else:
        test_cases = get_all_test_cases()
    
    logger.info(f"Running evaluation on {len(test_cases)} test cases")
    
    # Run evaluation
    await evaluator.evaluate_all(test_cases)
    
    # Generate report
    report = evaluator.generate_report()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evaluator.save_results(f"test_results/prompt_evaluation_{timestamp}.csv")
    
    # Save report as JSON
    report_path = f"test_results/prompt_evaluation_report_{timestamp}.json"
    os.makedirs("test_results", exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report


if __name__ == "__main__":
    # Example usage
    async def main():
        # Run full evaluation
        report = await run_evaluation()
        
        # Print summary
        print("\n=== Prompt Evaluation Summary ===")
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Pass Rate: {report['summary']['overall_pass_rate']:.2%}")
        
        print("\n=== Category Breakdown ===")
        for category, metrics in report['category_metrics'].items():
            print(f"\n{category}:")
            print(f"  Pass Rate: {metrics['pass_rate']:.2%} ({metrics['passed']}/{metrics['total']})")
            print(f"  Avg Time: {metrics['avg_execution_time']:.3f}s")
        
        if report['failed_tests']:
            print("\n=== Failed Tests (Sample) ===")
            for test in report['failed_tests'][:5]:
                print(f"\n{test['test_id']}: {test['description']}")
                print(f"  Expected: {test['expected']}")
                print(f"  Actual: {test['actual']}")
    
    asyncio.run(main())