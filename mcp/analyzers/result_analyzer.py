"""
Test result analyzer for RedBarSushiAI MCP.
Identifies patterns in test failures and categorizes issues.
"""
import logging
import re
from typing import Dict, List, Any, Optional

from mcp.config import Config

logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """
    Analyzes test results and identifies common issues.
    """

    def __init__(self, config: Config):
        self.config = config

    def analyze_test_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze test results and identify common issues.

        Args:
            results: The test results dictionary.

        Returns:
            List of identified issues.
        """
        logger.info("Analyzing test results")
        issues = []

        for test in results.get("tests", []):
            if not test["success"]:
                issue = self._identify_issue(test)
                if issue:
                    issues.append(issue)
                    logger.info(
                        f"Identified issue in test {test['name']}: {issue['type']} - {issue['description']}"
                    )

        return issues

    def _identify_issue(self, test: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Identify the issue based on test failure.

        Args:
            test: The test result dictionary.

        Returns:
            Issue dictionary or None if no known issue pattern is matched.
        """
        error_text = ""
        error_type = ""
        error_message = ""

        if test.get("error"):
            error_text = test["error"].get("text", "")
            error_type = test["error"].get("type", "")
            error_message = test["error"].get("message", "")
        elif test.get("failure"):
            error_text = test["failure"].get("text", "")
            error_type = test["failure"].get("type", "")
            error_message = test["failure"].get("message", "")
        else:
            return None

        # Connection errors
        if (
            "ConnectionError" in error_text
            or "Connection refused" in error_text
            or "ConnectionRefusedError" in error_text
        ):
            return {
                "type": "connection_error",
                "test": test["name"],
                "test_class": test["classname"],
                "description": "API connection error - possible service outage",
                "severity": "high",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                },
                "possible_fixes": ["restart_service", "check_network"],
            }

        # Timeout errors
        if "Timeout" in error_text or "TimeoutError" in error_text:
            return {
                "type": "timeout",
                "test": test["name"],
                "test_class": test["classname"],
                "description": "API response timeout - possible performance issue",
                "severity": "medium",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                },
                "possible_fixes": ["increase_timeout", "optimize_performance"],
            }

        # Database errors
        if (
            "DatabaseError" in error_text
            or "SQLAlchemyError" in error_text
            or "OperationalError" in error_text
            or "database" in error_text.lower()
        ):
            return {
                "type": "database_error",
                "test": test["name"],
                "test_class": test["classname"],
                "description": "Database error - possible connection or query issue",
                "severity": "high",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                },
                "possible_fixes": ["check_database_connection", "fix_database_query"],
            }

        # Redis errors
        if "Redis" in error_text or "RedisError" in error_text:
            return {
                "type": "redis_error",
                "test": test["name"],
                "test_class": test["classname"],
                "description": "Redis error - possible connection issue",
                "severity": "medium",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                },
                "possible_fixes": ["check_redis_connection", "restart_redis"],
            }

        # Assertion errors
        if "AssertionError" in error_type:
            # For menu-related assertions
            if "menu" in error_text.lower() or "item" in error_text.lower():
                return {
                    "type": "menu_assertion_error",
                    "test": test["name"],
                    "test_class": test["classname"],
                    "description": "Menu data assertion failed - possible menu structure issue",
                    "severity": "medium",
                    "error_details": {
                        "type": error_type,
                        "message": error_message,
                        "text": error_text,
                    },
                    "possible_fixes": ["check_menu_structure", "update_menu_data"],
                }

            # For order-related assertions
            if "order" in error_text.lower():
                return {
                    "type": "order_assertion_error",
                    "test": test["name"],
                    "test_class": test["classname"],
                    "description": "Order assertion failed - possible order processing issue",
                    "severity": "high",
                    "error_details": {
                        "type": error_type,
                        "message": error_message,
                        "text": error_text,
                    },
                    "possible_fixes": [
                        "check_order_processing",
                        "update_order_workflow",
                    ],
                }

            # Extract expected and actual values if available
            expected_match = re.search(r"Expected:?\s*(.+)", error_text)
            actual_match = re.search(r"Actual:?\s*(.+)", error_text)
            expected = expected_match.group(1) if expected_match else "unknown"
            actual = actual_match.group(1) if actual_match else "unknown"

            return {
                "type": "assertion_error",
                "test": test["name"],
                "test_class": test["classname"],
                "description": f"Test assertion failed - expected: {expected}, actual: {actual}",
                "severity": "medium",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                    "expected": expected,
                    "actual": actual,
                },
                "possible_fixes": ["update_assertion", "fix_data_validation"],
            }

        # API-related errors
        if "API" in error_text or "HTTP" in error_text or "Status code" in error_text:
            return {
                "type": "api_error",
                "test": test["name"],
                "test_class": test["classname"],
                "description": "API error - unexpected response or status code",
                "severity": "medium",
                "error_details": {
                    "type": error_type,
                    "message": error_message,
                    "text": error_text,
                },
                "possible_fixes": ["check_api_endpoints", "update_api_expectations"],
            }

        # Default/unknown error
        return {
            "type": "unknown_error",
            "test": test["name"],
            "test_class": test["classname"],
            "description": "Unknown error - requires manual investigation",
            "severity": "low",
            "error_details": {
                "type": error_type,
                "message": error_message,
                "text": error_text,
            },
            "possible_fixes": ["manual_investigation"],
        }