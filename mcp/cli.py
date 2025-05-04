#!/usr/bin/env python
"""
Command line interface for RedBarSushiAI MCP.
Provides commands for running E2E tests, analyzing results, and fixing issues.
"""
import click
import logging
import json
import sys
from pathlib import Path
from typing import List, Optional

from mcp.config import Config
from mcp.runners.test_runner import TestRunner
from mcp.analyzers.result_analyzer import ResultAnalyzer
from mcp.analyzers.fix_generator import FixGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-cli")


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def cli(debug):
    """RedBarSushiAI MCP Tool for E2E Testing"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")


@cli.command()
@click.option("--test", "-t", multiple=True, help="Specific test to run")
@click.option(
    "--output", "-o", type=click.Path(), help="Output file for test results (JSON)"
)
def run_tests(test: List[str], output: Optional[str]):
    """Run E2E tests on the staging environment"""
    config = Config()
    runner = TestRunner(config)

    click.echo("Running tests on staging environment...")
    results = runner.run_tests(specific_tests=list(test) if test else None)

    # Display results summary
    click.echo(f"\nTest Results:")
    click.echo(f"  Total: {results['summary']['total']}")
    click.echo(f"  Passed: {results['summary']['passed']}")
    click.echo(f"  Failed: {results['summary']['failed']}")
    click.echo(f"  Pass Rate: {results['summary']['pass_rate'] * 100:.2f}%")

    # Show details for failed tests
    if results["summary"]["failed"] > 0:
        click.echo("\nFailed Tests:")
        for test in results["tests"]:
            if not test["success"]:
                click.echo(f"  - {test['name']} ({test['classname']})")
                if test.get("error"):
                    click.echo(f"    Error: {test['error']['message']}")
                if test.get("failure"):
                    click.echo(f"    Failure: {test['failure']['message']}")

    # Write results to file if requested
    if output:
        click.echo(f"\nWriting results to {output}")
        with open(output, "w") as f:
            json.dump(results, f, indent=2)

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


@cli.command()
@click.option("--test", "-t", multiple=True, help="Specific test to run")
@click.option(
    "--auto-fix/--no-auto-fix", default=False, help="Attempt to auto-fix issues"
)
@click.option(
    "--output", "-o", type=click.Path(), help="Output file for analysis results (JSON)"
)
def analyze(test: List[str], auto_fix: bool, output: Optional[str]):
    """Run tests, analyze results, and optionally fix issues"""
    config = Config()
    runner = TestRunner(config)
    analyzer = ResultAnalyzer(config)

    click.echo("Running tests...")
    results = runner.run_tests(specific_tests=list(test) if test else None)

    click.echo("\nAnalyzing results...")
    issues = analyzer.analyze_test_results(results)

    click.echo(f"\nIdentified {len(issues)} issues:")
    for i, issue in enumerate(issues):
        click.echo(
            f"{i+1}. {issue['type']} - {issue['description']} (Severity: {issue['severity']})"
        )
        click.echo(f"   Test: {issue['test']}")

    analysis_results = {
        "test_results": results,
        "issues": issues,
        "fixes": [],
    }

    if auto_fix and issues:
        click.echo("\nAttempting to fix issues...")
        fix_generator = FixGenerator(config)
        fixes = []
        for issue in issues:
            fix = fix_generator.generate_fix(issue)
            if fix:
                fixes.append(fix)
                click.echo(f"Generated fix for issue: {issue['type']}")
                if not fix.get("automated_fix", False):
                    click.echo("  Manual steps required:")
                    for step in fix.get("manual_steps", []):
                        click.echo(f"  - {step}")
            else:
                click.echo(f"No automatic fix available for issue: {issue['type']}")

        analysis_results["fixes"] = fixes

    # Write results to file if requested
    if output:
        click.echo(f"\nWriting analysis results to {output}")
        with open(output, "w") as f:
            json.dump(analysis_results, f, indent=2)

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


@cli.command()
@click.option(
    "--input", "-i", type=click.Path(exists=True), help="Input file with test results (JSON)"
)
def generate_fixes(input: str):
    """Generate fixes for issues from a previous test run"""
    if not input:
        click.echo("Error: Input file is required")
        sys.exit(1)

    # Load results from file
    with open(input, "r") as f:
        results = json.load(f)

    config = Config()
    analyzer = ResultAnalyzer(config)
    fix_generator = FixGenerator(config)

    # If it's a raw test result, analyze it first
    if "issues" not in results:
        click.echo("Analyzing test results...")
        issues = analyzer.analyze_test_results(results)
    else:
        # If it's already an analysis result, use the issues
        issues = results["issues"]

    click.echo(f"\nGenerating fixes for {len(issues)} issues:")
    fixes = []
    for i, issue in enumerate(issues):
        click.echo(f"{i+1}. {issue['type']} - {issue['description']}")
        fix = fix_generator.generate_fix(issue)
        if fix:
            fixes.append(fix)
            click.echo(f"  Generated fix: {fix['type']}")
            if not fix.get("automated_fix", False):
                click.echo("  Manual steps required:")
                for step in fix.get("manual_steps", []):
                    click.echo(f"  - {step}")
        else:
            click.echo(f"  No automatic fix available")

    # Write fixes to output file
    output = Path(input).with_suffix(".fixes.json")
    click.echo(f"\nWriting fixes to {output}")
    with open(output, "w") as f:
        json.dump(
            {
                "issues": issues,
                "fixes": fixes,
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    cli()