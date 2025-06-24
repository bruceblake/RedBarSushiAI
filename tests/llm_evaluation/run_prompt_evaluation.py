"""
Script to run prompt evaluation tests.

This script provides a command-line interface for running LLM prompt evaluations
with various options and filters.
"""

import asyncio
import argparse
import sys
import os
import json
from typing import List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.llm_evaluation.prompt_evaluator import run_evaluation, PromptEvaluator
from tests.llm_evaluation.prompt_test_cases import TestCategory, get_all_test_cases


def print_summary(report: dict):
    """Print a formatted summary of the evaluation report."""
    print("\n" + "=" * 60)
    print("PROMPT EVALUATION SUMMARY")
    print("=" * 60)
    
    summary = report['summary']
    print(f"\nModel: {summary['model_used']}")
    print(f"Date: {summary['evaluation_date']}")
    print(f"\nTotal Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']} ({summary['overall_pass_rate']:.1%})")
    print(f"Failed: {summary['failed']}")
    
    print("\n" + "-" * 60)
    print("CATEGORY BREAKDOWN")
    print("-" * 60)
    
    for category, metrics in report['category_metrics'].items():
        print(f"\n{category}:")
        print(f"  Tests: {metrics['total']}")
        print(f"  Pass Rate: {metrics['pass_rate']:.1%} ({metrics['passed']}/{metrics['total']})")
        print(f"  Avg Time: {metrics['avg_execution_time']:.3f}s")
    
    if report['failed_tests']:
        print("\n" + "-" * 60)
        print("FAILED TESTS (Top 10)")
        print("-" * 60)
        
        for i, test in enumerate(report['failed_tests'][:10], 1):
            print(f"\n{i}. {test['test_id']}: {test['description']}")
            print(f"   Category: {test['category']}")
            print(f"   Expected: {test['expected']}")
            print(f"   Actual: {test['actual']}")
            if test.get('error'):
                print(f"   Error: {test['error']}")
    
    print("\n" + "=" * 60)
    print(f"Total execution time: {report['execution_stats']['total_time']:.2f}s")
    print(f"Average time per test: {report['execution_stats']['avg_time_per_test']:.3f}s")
    print("=" * 60 + "\n")


async def run_single_test(test_id: str, model: str = "gpt-4o-mini"):
    """Run a single test case by ID."""
    all_tests = get_all_test_cases()
    test_case = next((tc for tc in all_tests if tc.id == test_id), None)
    
    if not test_case:
        print(f"Error: Test case '{test_id}' not found")
        return
    
    print(f"\nRunning single test: {test_id}")
    print(f"Description: {test_case.description}")
    print(f"Category: {test_case.category.value}")
    
    evaluator = PromptEvaluator(model=model)
    result = await evaluator.evaluate_test_case(test_case)
    
    print(f"\nResult: {'PASSED' if result.passed else 'FAILED'}")
    print(f"Expected: {result.expected_outputs}")
    print(f"Actual: {result.actual_output}")
    if result.confidence_score is not None:
        print(f"Confidence: {result.confidence_score:.2f}")
    if result.error_message:
        print(f"Error: {result.error_message}")
    print(f"Execution time: {result.execution_time:.3f}s")


async def main():
    parser = argparse.ArgumentParser(
        description="Run LLM prompt evaluation tests for RedBarSushiAI"
    )
    
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=[cat.value for cat in TestCategory],
        help="Test categories to run"
    )
    
    parser.add_argument(
        "--tags",
        nargs="+",
        help="Test tags to filter by (e.g., greeting, menu, ordering)"
    )
    
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use for evaluation (default: gpt-4o-mini)"
    )
    
    parser.add_argument(
        "--test-id",
        help="Run a single test by ID"
    )
    
    parser.add_argument(
        "--list-tests",
        action="store_true",
        help="List all available test cases"
    )
    
    parser.add_argument(
        "--output-dir",
        default="test_results",
        help="Directory to save results (default: test_results)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output"
    )
    
    args = parser.parse_args()
    
    # List tests if requested
    if args.list_tests:
        print("\nAvailable Test Cases:")
        print("=" * 80)
        all_tests = get_all_test_cases()
        
        current_category = None
        for test in all_tests:
            if test.category != current_category:
                current_category = test.category
                print(f"\n{current_category.value}:")
                print("-" * 40)
            
            print(f"  {test.id}: {test.description}")
            if test.tags:
                print(f"    Tags: {', '.join(test.tags)}")
        
        print(f"\nTotal: {len(all_tests)} test cases")
        return
    
    # Run single test if specified
    if args.test_id:
        await run_single_test(args.test_id, args.model)
        return
    
    # Prepare categories
    categories = None
    if args.categories:
        categories = [TestCategory(cat) for cat in args.categories]
    
    # Run evaluation
    if not args.quiet:
        print(f"\nStarting prompt evaluation...")
        print(f"Model: {args.model}")
        if categories:
            print(f"Categories: {', '.join(args.categories)}")
        if args.tags:
            print(f"Tags: {', '.join(args.tags)}")
        print()
    
    try:
        report = await run_evaluation(
            categories=categories,
            tags=args.tags,
            model=args.model
        )
        
        # Print summary unless quiet
        if not args.quiet:
            print_summary(report)
        
        # Save report
        os.makedirs(args.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(
            args.output_dir,
            f"prompt_evaluation_report_{timestamp}.json"
        )
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nFull report saved to: {report_path}")
        
        # Exit with error if tests failed
        if report['summary']['failed'] > 0:
            sys.exit(1)
            
    except Exception as e:
        print(f"\nError during evaluation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())