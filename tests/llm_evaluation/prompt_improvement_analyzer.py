"""
Prompt Improvement Analyzer for RedBarSushiAI.

This module analyzes failed test cases and suggests improvements to prompts
based on patterns in failures.
"""

import json
import os
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
import re

from tests.llm_evaluation.prompt_test_cases import TestCategory


@dataclass
class PromptImprovement:
    """Suggested improvement for a prompt."""
    component: str  # Which component (intent_detector, agent, etc.)
    current_prompt: str
    suggested_prompt: str
    reason: str
    affected_tests: List[str]
    expected_impact: str


class PromptImprovementAnalyzer:
    """Analyzes test failures and suggests prompt improvements."""
    
    def __init__(self, evaluation_report_path: str):
        """Initialize with evaluation report."""
        with open(evaluation_report_path, 'r') as f:
            self.report = json.load(f)
        
        self.failed_tests = self.report.get('failed_tests', [])
        self.improvements: List[PromptImprovement] = []
    
    def analyze_failures(self) -> List[PromptImprovement]:
        """Analyze all failures and generate improvement suggestions."""
        # Group failures by category
        failures_by_category = defaultdict(list)
        for test in self.failed_tests:
            failures_by_category[test['category']].append(test)
        
        # Analyze each category
        for category, failures in failures_by_category.items():
            if category == TestCategory.INTENT_DETECTION.value:
                self._analyze_intent_failures(failures)
            elif category == TestCategory.AGENT_RESPONSE.value:
                self._analyze_response_failures(failures)
            elif category == TestCategory.FUNCTION_CALLING.value:
                self._analyze_function_failures(failures)
            elif category == TestCategory.DISAMBIGUATION.value:
                self._analyze_disambiguation_failures(failures)
            elif category == TestCategory.GLOBAL_COMMANDS.value:
                self._analyze_global_command_failures(failures)
        
        return self.improvements
    
    def _analyze_intent_failures(self, failures: List[Dict[str, Any]]):
        """Analyze intent detection failures."""
        # Group by common patterns
        greeting_failures = []
        ordering_failures = []
        ambiguous_failures = []
        
        for failure in failures:
            test_id = failure['test_id']
            if 'greeting' in test_id:
                greeting_failures.append(failure)
            elif 'ordering' in test_id:
                ordering_failures.append(failure)
            elif 'edge' in test_id or 'ambig' in failure['description'].lower():
                ambiguous_failures.append(failure)
        
        # Generate improvements based on patterns
        if greeting_failures:
            self.improvements.append(PromptImprovement(
                component="intent_detector",
                current_prompt="User is giving their name or responding to name request",
                suggested_prompt=(
                    "User is giving their name or responding to name request. "
                    "Look for: direct names (just 'John'), full introductions "
                    "('My name is...'), or spelled names. Single words that could "
                    "be names should be treated as PROVIDE_NAME."
                ),
                reason="Multiple failures detecting simple name inputs",
                affected_tests=[f['test_id'] for f in greeting_failures],
                expected_impact="Better detection of name provision in various formats"
            ))
        
        if ambiguous_failures:
            self.improvements.append(PromptImprovement(
                component="intent_detector",
                current_prompt="Analyze the user's message and return ONLY ONE",
                suggested_prompt=(
                    "Analyze the user's message and return ONLY ONE intent. "
                    "For ambiguous inputs, prioritize based on conversation flow: "
                    "1) If multiple intents possible, choose the most likely given the state "
                    "2) 'Never mind' in ORDERING usually means REQUEST_CANCELLATION "
                    "3) Combined actions should return the FIRST action mentioned"
                ),
                reason="Ambiguous inputs not handled consistently",
                affected_tests=[f['test_id'] for f in ambiguous_failures],
                expected_impact="More consistent handling of ambiguous user inputs"
            ))
    
    def _analyze_response_failures(self, failures: List[Dict[str, Any]]):
        """Analyze agent response failures."""
        # Look for patterns in response failures
        greeting_responses = []
        confirmation_responses = []
        
        for failure in failures:
            if 'greeting' in failure['test_id'] or 'frontline' in failure['test_id']:
                greeting_responses.append(failure)
            elif 'confirm' in failure['description'].lower():
                confirmation_responses.append(failure)
        
        if greeting_responses:
            self.improvements.append(PromptImprovement(
                component="frontline_agent",
                current_prompt="You are a friendly restaurant host",
                suggested_prompt=(
                    "You are a friendly restaurant host for Red Bar Sushi. "
                    "ALWAYS mention 'Red Bar Sushi' in your greeting. "
                    "Keep responses warm but concise. "
                    "Example: 'Welcome to Red Bar Sushi! May I have your name?'"
                ),
                reason="Inconsistent greeting format and missing restaurant name",
                affected_tests=[f['test_id'] for f in greeting_responses],
                expected_impact="Consistent greetings with restaurant branding"
            ))
    
    def _analyze_function_failures(self, failures: List[Dict[str, Any]]):
        """Analyze function calling failures."""
        missing_calls = []
        incorrect_calls = []
        
        for failure in failures:
            actual = failure.get('actual', '')
            expected_func = failure.get('expected', [])
            
            if 'No function called' in actual and expected_func:
                missing_calls.append(failure)
            elif actual and actual not in expected_func:
                incorrect_calls.append(failure)
        
        if missing_calls:
            self.improvements.append(PromptImprovement(
                component="function_calling_prompt",
                current_prompt="You have access to functions",
                suggested_prompt=(
                    "You have access to the following functions that you SHOULD use "
                    "when appropriate:\n"
                    "- add_to_cart: Use when user wants to add items\n"
                    "- remove_from_cart: Use when user wants to remove items\n"
                    "- search_menu: Use when user asks about menu items\n"
                    "Always prefer using functions over plain text responses when available."
                ),
                reason="LLM not calling functions when expected",
                affected_tests=[f['test_id'] for f in missing_calls],
                expected_impact="More consistent function usage"
            ))
    
    def _analyze_disambiguation_failures(self, failures: List[Dict[str, Any]]):
        """Analyze disambiguation failures."""
        if not failures:
            return
        
        self.improvements.append(PromptImprovement(
            component="disambiguation_prompt",
            current_prompt="Multiple items found. Ask for clarification.",
            suggested_prompt=(
                "Multiple items match your request. I need to clarify which one you want. "
                "Present ALL options clearly with distinguishing features:\n"
                "- List each option with its unique characteristics (price, ingredients)\n"
                "- Use numbers if there are more than 2 options\n"
                "- Always ask 'Which would you like?' or similar\n"
                "Example: 'I found 3 spicy rolls: (1) Spicy Tuna Roll ($14.95), "
                "(2) Spicy Salmon Roll ($15.95), or (3) Spicy Yellowtail Roll ($16.95). "
                "Which would you like?'"
            ),
            reason="Disambiguation not presenting all options clearly",
            affected_tests=[f['test_id'] for f in failures],
            expected_impact="Clearer disambiguation with all options presented"
        ))
    
    def _analyze_global_command_failures(self, failures: List[Dict[str, Any]]):
        """Analyze global command detection failures."""
        if not failures:
            return
        
        false_positives = []
        missed_commands = []
        
        for failure in failures:
            if 'false_positive' in failure.get('tags', []):
                false_positives.append(failure)
            else:
                missed_commands.append(failure)
        
        if false_positives:
            self.improvements.append(PromptImprovement(
                component="global_command_patterns",
                current_prompt="Pattern: r'\\b(repeat|say)\\s+(that|it)'",
                suggested_prompt=(
                    "Pattern should check context more carefully:\n"
                    "- 'repeat' at start of sentence: likely REPEAT command\n"
                    "- 'repeat my order' or 'I'll repeat': likely NOT a command\n"
                    "- Add negative lookahead for 'I'll repeat' or 'to repeat'\n"
                    "New pattern: r'^(can you |please )?repeat (that|what you said)'"
                ),
                reason="False positive detections of global commands",
                affected_tests=[f['test_id'] for f in false_positives],
                expected_impact="Fewer false positive command detections"
            ))
    
    def generate_improvement_report(self) -> Dict[str, Any]:
        """Generate a report of all improvements."""
        # Group by component
        by_component = defaultdict(list)
        for improvement in self.improvements:
            by_component[improvement.component].append(improvement)
        
        # Calculate impact
        total_affected_tests = len(set(
            test_id 
            for imp in self.improvements 
            for test_id in imp.affected_tests
        ))
        
        return {
            "summary": {
                "total_improvements": len(self.improvements),
                "affected_components": list(by_component.keys()),
                "total_affected_tests": total_affected_tests,
                "potential_pass_rate_improvement": (
                    total_affected_tests / self.report['summary']['total_tests']
                )
            },
            "improvements_by_component": {
                component: [
                    {
                        "current": imp.current_prompt[:100] + "...",
                        "suggested": imp.suggested_prompt,
                        "reason": imp.reason,
                        "affected_tests": imp.affected_tests,
                        "impact": imp.expected_impact
                    }
                    for imp in improvements
                ]
                for component, improvements in by_component.items()
            }
        }
    
    def save_improvements(self, output_path: str = "prompt_improvements.json"):
        """Save improvement suggestions to file."""
        report = self.generate_improvement_report()
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Improvement suggestions saved to: {output_path}")
        
        # Also generate markdown report
        md_path = output_path.replace('.json', '.md')
        self._save_markdown_report(md_path, report)
    
    def _save_markdown_report(self, output_path: str, report: Dict[str, Any]):
        """Save improvements as a markdown report."""
        with open(output_path, 'w') as f:
            f.write("# Prompt Improvement Analysis\n\n")
            
            # Summary
            summary = report['summary']
            f.write("## Summary\n\n")
            f.write(f"- Total Improvements Suggested: {summary['total_improvements']}\n")
            f.write(f"- Components Affected: {', '.join(summary['affected_components'])}\n")
            f.write(f"- Tests That Could Be Fixed: {summary['total_affected_tests']}\n")
            f.write(f"- Potential Pass Rate Improvement: {summary['potential_pass_rate_improvement']:.1%}\n\n")
            
            # Improvements by component
            f.write("## Detailed Improvements\n\n")
            
            for component, improvements in report['improvements_by_component'].items():
                f.write(f"### {component}\n\n")
                
                for i, imp in enumerate(improvements, 1):
                    f.write(f"#### Improvement {i}\n\n")
                    f.write(f"**Reason:** {imp['reason']}\n\n")
                    f.write(f"**Current Prompt (excerpt):**\n```\n{imp['current']}\n```\n\n")
                    f.write(f"**Suggested Prompt:**\n```\n{imp['suggested']}\n```\n\n")
                    f.write(f"**Expected Impact:** {imp['impact']}\n\n")
                    f.write(f"**Affected Tests:** {', '.join(imp['affected_tests'])}\n\n")
                    f.write("---\n\n")
        
        print(f"Markdown report saved to: {output_path}")


def analyze_evaluation_results(report_path: str) -> Dict[str, Any]:
    """Analyze evaluation results and suggest improvements."""
    analyzer = PromptImprovementAnalyzer(report_path)
    
    # Analyze failures
    improvements = analyzer.analyze_failures()
    
    # Generate and save report
    report = analyzer.generate_improvement_report()
    
    # Save to file
    output_dir = os.path.dirname(report_path)
    output_path = os.path.join(output_dir, "prompt_improvements.json")
    analyzer.save_improvements(output_path)
    
    return report


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python prompt_improvement_analyzer.py <evaluation_report.json>")
        sys.exit(1)
    
    report_path = sys.argv[1]
    if not os.path.exists(report_path):
        print(f"Error: Report file not found: {report_path}")
        sys.exit(1)
    
    # Analyze and print summary
    report = analyze_evaluation_results(report_path)
    
    print("\n=== Prompt Improvement Analysis ===")
    print(f"Total improvements suggested: {report['summary']['total_improvements']}")
    print(f"Components to update: {', '.join(report['summary']['affected_components'])}")
    print(f"Potential pass rate improvement: {report['summary']['potential_pass_rate_improvement']:.1%}")