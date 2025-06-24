"""
CLI script to run E2E conversation tests.

This script provides a command-line interface for running end-to-end tests
with various options and filters.
"""

import asyncio
import argparse
import sys
import os
import json
import logging
from typing import Optional, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.e2e.e2e_test_runner import run_e2e_tests, E2ETestRunner
from tests.e2e.conversation_scenarios import ScenarioType, get_all_scenarios
from tests.e2e.websocket_test_utils import MockWebSocketServer, start_mock_server


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def print_summary(report: dict):
    """Print formatted test summary."""
    print("\n" + "=" * 60)
    print("E2E TEST RESULTS SUMMARY")
    print("=" * 60)
    
    summary = report['summary']
    print(f"\nTest Date: {summary['test_date']}")
    print(f"\nScenarios:")
    print(f"  Total: {summary['total_scenarios']}")
    print(f"  Passed: {summary['passed']} ({summary['pass_rate']:.1%})")
    print(f"  Failed: {summary['failed']}")
    
    print(f"\nConversation Turns:")
    print(f"  Total: {summary['total_turns']}")
    print(f"  Completed: {summary['completed_turns']} ({summary['turn_completion_rate']:.1%})")
    
    print("\n" + "-" * 60)
    print("RESULTS BY TYPE")
    print("-" * 60)
    
    for type_name, stats in report['by_type'].items():
        total = stats['passed'] + stats['failed']
        pass_rate = stats['passed'] / total if total > 0 else 0
        print(f"\n{type_name.upper()}:")
        print(f"  Passed: {stats['passed']}/{total} ({pass_rate:.1%})")
        if stats['failed'] > 0:
            print(f"  Failed: {stats['failed']}")
    
    if report['failed_scenarios']:
        print("\n" + "-" * 60)
        print("FAILED SCENARIOS")
        print("-" * 60)
        
        for failure in report['failed_scenarios'][:5]:  # Show first 5
            print(f"\n{failure['scenario_name']} ({failure['scenario_id']}):")
            if failure['errors']:
                for error in failure['errors'][:3]:  # Show first 3 errors
                    print(f"  - {error}")
            if failure['failed_turns']:
                print(f"  Failed turns: {len(failure['failed_turns'])}")
    
    print("\n" + "-" * 60)
    print("PERFORMANCE")
    print("-" * 60)
    print(f"Average Response Time: {report['performance']['avg_response_time']:.2f}s")
    print(f"Total Test Duration: {report['performance']['total_test_duration']:.1f}s")
    print("=" * 60 + "\n")


async def list_scenarios():
    """List all available test scenarios."""
    scenarios = get_all_scenarios()
    
    print("\nAvailable E2E Test Scenarios:")
    print("=" * 80)
    
    current_type = None
    for scenario in scenarios:
        if scenario.scenario_type != current_type:
            current_type = scenario.scenario_type
            print(f"\n{current_type.value.upper()}:")
            print("-" * 40)
        
        print(f"  {scenario.id}: {scenario.name}")
        print(f"    Description: {scenario.description}")
        print(f"    Turns: {len(scenario.turns)}")
        print(f"    Tags: {', '.join(scenario.tags)}")
    
    print(f"\nTotal: {len(scenarios)} scenarios")


async def run_single_scenario(scenario_id: str, base_url: str = None, ws_url: str = None):
    """Run a single scenario by ID."""
    scenarios = get_all_scenarios()
    scenario = next((s for s in scenarios if s.id == scenario_id), None)
    
    if not scenario:
        print(f"Error: Scenario '{scenario_id}' not found")
        return
    
    print(f"\nRunning scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"Turns: {len(scenario.turns)}")
    
    runner = E2ETestRunner(base_url=base_url, ws_url=ws_url)
    
    try:
        await runner.setup()
        result = await runner.run_scenario(scenario)
        
        # Print detailed results
        print(f"\nResult: {'PASSED' if result.passed else 'FAILED'}")
        print(f"Turns completed: {result.turns_completed}/{result.turns_total}")
        print(f"Duration: {result.total_duration:.2f}s")
        
        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
        
        if result.outcome_validation:
            print("\nOutcome Validation:")
            for key, validation in result.outcome_validation.items():
                if key != "passed" and isinstance(validation, dict):
                    status = "✓" if validation['passed'] else "✗"
                    print(f"  {status} {key}: expected={validation['expected']}, actual={validation['actual']}")
        
        # Show failed turns
        failed_turns = [tr for tr in result.turn_results if not tr.passed]
        if failed_turns:
            print(f"\nFailed Turns ({len(failed_turns)}):")
            for tr in failed_turns[:5]:  # Show first 5
                print(f"  Turn {tr.turn_number}: {tr.error}")
        
    finally:
        await runner.teardown()


async def main():
    parser = argparse.ArgumentParser(
        description="Run E2E conversation tests for RedBarSushiAI"
    )
    
    parser.add_argument(
        "--type",
        choices=[t.value for t in ScenarioType],
        help="Run scenarios of specific type"
    )
    
    parser.add_argument(
        "--tags",
        nargs="+",
        help="Run scenarios with specific tags"
    )
    
    parser.add_argument(
        "--scenario",
        help="Run a single scenario by ID"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available scenarios"
    )
    
    parser.add_argument(
        "--base-url",
        help="Base URL for HTTP API (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: ws://localhost:8000/ws)"
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock WebSocket server for testing"
    )
    
    parser.add_argument(
        "--output-dir",
        default="test_results",
        help="Directory to save results"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output except for errors"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    if not args.quiet:
        setup_logging(args.verbose)
    else:
        logging.basicConfig(level=logging.ERROR)
    
    # List scenarios if requested
    if args.list:
        await list_scenarios()
        return
    
    # Handle mock server
    mock_server = None
    if args.mock:
        print("Starting mock WebSocket server...")
        mock_server = await start_mock_server()
        args.ws_url = args.ws_url or "ws://localhost:8765"
    
    try:
        # Run single scenario if specified
        if args.scenario:
            await run_single_scenario(
                args.scenario,
                base_url=args.base_url,
                ws_url=args.ws_url
            )
            return
        
        # Convert type string to enum
        scenario_type = None
        if args.type:
            scenario_type = ScenarioType(args.type)
        
        # Run tests
        if not args.quiet:
            print("\nStarting E2E conversation tests...")
            if scenario_type:
                print(f"Type filter: {scenario_type.value}")
            if args.tags:
                print(f"Tag filter: {', '.join(args.tags)}")
            print()
        
        report = await run_e2e_tests(
            scenario_type=scenario_type,
            tags=args.tags,
            base_url=args.base_url,
            ws_url=args.ws_url
        )
        
        # Print summary unless quiet
        if not args.quiet:
            print_summary(report)
        
        # Save report
        os.makedirs(args.output_dir, exist_ok=True)
        report_path = os.path.join(
            args.output_dir,
            f"e2e_report_latest.json"
        )
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        if not args.quiet:
            print(f"\nFull report saved to: {report_path}")
        
        # Exit with error if tests failed
        if report['summary']['failed'] > 0:
            sys.exit(1)
            
    finally:
        # Stop mock server if started
        if mock_server:
            mock_server.stop()
            await mock_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())