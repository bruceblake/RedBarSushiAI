"""
Fix generator for RedBarSushiAI MCP.
Generates fixes for common issues identified by the result analyzer.
"""
import logging
import re
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from mcp.config import Config

logger = logging.getLogger(__name__)


class FixGenerator:
    """
    Generates fixes for common issues identified by the result analyzer.
    """

    def __init__(self, config: Config):
        self.config = config

    def generate_fix(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for the identified issue.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Generating fix for issue: {issue['type']}")

        # Dispatch to appropriate fix method based on issue type
        if issue["type"] == "connection_error":
            return self._fix_connection_error(issue)
        elif issue["type"] == "timeout":
            return self._fix_timeout(issue)
        elif issue["type"] == "database_error":
            return self._fix_database_error(issue)
        elif issue["type"] == "redis_error":
            return self._fix_redis_error(issue)
        elif issue["type"] == "menu_assertion_error":
            return self._fix_menu_assertion_error(issue)
        elif issue["type"] == "order_assertion_error":
            return self._fix_order_assertion_error(issue)
        elif issue["type"] == "assertion_error":
            return self._fix_assertion_error(issue)
        elif issue["type"] == "api_error":
            return self._fix_api_error(issue)
        
        logger.warning(f"No fix strategy available for issue type: {issue['type']}")
        return None

    def _fix_connection_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for connection errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying connection error fix strategy for {issue['test']}")
        
        # This would typically involve:
        # 1. Checking Render service status
        # 2. Triggering a service restart if needed
        
        # For now, just generate a diagnostic report
        return {
            "type": "connection_error_fix",
            "issue": issue,
            "diagnostic": "Service connectivity issue detected",
            "restart_required": True,
            "automated_fix": False,
            "actions": [
                {
                    "type": "restart_service",
                    "service": "redbarsushi-staging",
                    "implemented": False  # This would be implemented via Render API
                }
            ],
            "manual_steps": [
                "Check Render service status",
                "Restart the service if it's unresponsive",
                "Verify database connectivity"
            ]
        }

    def _fix_timeout(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for timeout issues.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying timeout fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        increased_timeout = False
        test_file = self._extract_test_file_path(issue)
        
        if test_file and Path(test_file).exists():
            # Analyze the test file to find timeout values
            with open(test_file, "r") as f:
                content = f.read()
                
            # Look for timeout values in requests or configs
            timeout_matches = re.findall(r"timeout=(\d+)", content)
            
            if timeout_matches:
                original_timeout = int(timeout_matches[0])
                new_timeout = original_timeout * 2  # Double the timeout
                
                new_content = re.sub(
                    r"timeout=(\d+)", 
                    f"timeout={new_timeout}", 
                    content, 
                    count=1
                )
                
                # This would be implemented when we can write to files
                increased_timeout = True
        
        return {
            "type": "timeout_fix",
            "issue": issue,
            "diagnostic": "API response timeout detected",
            "increased_timeout": increased_timeout,
            "automated_fix": False,
            "actions": [
                {
                    "type": "increase_resource",
                    "resource": "memory",
                    "implemented": False  # This would be implemented via Render API
                },
                {
                    "type": "modify_timeout",
                    "file": test_file,
                    "implemented": False  # This would be implemented when we can write to files
                }
            ],
            "manual_steps": [
                "Increase the service resources on Render",
                "Consider optimizing API endpoints that are timing out",
                "Increase the timeout values in the test files"
            ]
        }

    def _fix_database_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for database errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying database error fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        
        # Check for common database errors
        connection_issue = "connection" in error_text.lower() or "connect" in error_text.lower()
        migration_issue = "migration" in error_text.lower() or "alembic" in error_text.lower()
        constraint_issue = "constraint" in error_text.lower() or "violates" in error_text.lower()
        
        # Determine the fix type
        if connection_issue:
            fix_type = "database_connection"
        elif migration_issue:
            fix_type = "database_migration"
        elif constraint_issue:
            fix_type = "database_constraint"
        else:
            fix_type = "database_general"
        
        return {
            "type": "database_error_fix",
            "issue": issue,
            "diagnostic": f"Database {fix_type} issue detected",
            "automated_fix": False,
            "actions": [
                {
                    "type": "check_database",
                    "database": "redbarsushi-staging",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Verify database connection settings",
                "Check for pending migrations that need to be applied",
                "Review database logs for detailed error information"
            ]
        }

    def _fix_redis_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for Redis errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying Redis error fix strategy for {issue['test']}")
        
        return {
            "type": "redis_error_fix",
            "issue": issue,
            "diagnostic": "Redis connectivity issue detected",
            "automated_fix": False,
            "actions": [
                {
                    "type": "restart_redis",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Verify Redis connection settings",
                "Check Redis service status",
                "Restart Redis if necessary"
            ]
        }

    def _fix_menu_assertion_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for menu assertion errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying menu assertion error fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        expected = issue["error_details"].get("expected", "unknown")
        actual = issue["error_details"].get("actual", "unknown")
        
        # Look for common menu assertion issues
        menu_structure = "structure" in error_text.lower() or "schema" in error_text.lower()
        menu_item = "item" in error_text.lower() or "product" in error_text.lower()
        menu_price = "price" in error_text.lower() or "$" in error_text or "cost" in error_text.lower()
        
        # Determine the fix type
        if menu_structure:
            fix_type = "menu_structure"
        elif menu_price:
            fix_type = "menu_price"
        elif menu_item:
            fix_type = "menu_item"
        else:
            fix_type = "menu_general"
        
        return {
            "type": "menu_assertion_fix",
            "issue": issue,
            "diagnostic": f"Menu {fix_type} assertion failure",
            "automated_fix": False,
            "actions": [
                {
                    "type": "check_menu_data",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Verify menu data is correctly formatted in the database",
                "Check that test expectations match the current menu structure",
                "Update test fixtures if the menu structure has legitimately changed"
            ]
        }

    def _fix_order_assertion_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for order assertion errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying order assertion error fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        expected = issue["error_details"].get("expected", "unknown")
        actual = issue["error_details"].get("actual", "unknown")
        
        # Look for common order assertion issues
        order_status = "status" in error_text.lower()
        order_items = "items" in error_text.lower() or "products" in error_text.lower()
        order_price = "price" in error_text.lower() or "$" in error_text or "total" in error_text.lower()
        
        # Determine the fix type
        if order_status:
            fix_type = "order_status"
        elif order_items:
            fix_type = "order_items"
        elif order_price:
            fix_type = "order_price"
        else:
            fix_type = "order_general"
        
        return {
            "type": "order_assertion_fix",
            "issue": issue,
            "diagnostic": f"Order {fix_type} assertion failure",
            "automated_fix": False,
            "actions": [
                {
                    "type": "check_order_processing",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Verify order processing workflow is functioning correctly",
                "Check for changes in the order API response format",
                "Update test expectations if the order structure has legitimately changed"
            ]
        }

    def _fix_assertion_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for general assertion errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying general assertion error fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        expected = issue["error_details"].get("expected", "unknown")
        actual = issue["error_details"].get("actual", "unknown")
        
        return {
            "type": "assertion_fix",
            "issue": issue,
            "diagnostic": "General assertion failure",
            "expected": expected,
            "actual": actual,
            "automated_fix": False,
            "actions": [
                {
                    "type": "update_assertion",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Review the assertion failure to determine if the expectation or implementation is incorrect",
                "Update the test if expectations have changed",
                "Fix the implementation if it's not meeting requirements"
            ]
        }

    def _fix_api_error(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for API errors.

        Args:
            issue: The issue dictionary.

        Returns:
            Fix dictionary or None if no fix could be generated.
        """
        logger.info(f"Applying API error fix strategy for {issue['test']}")
        
        error_text = issue["error_details"]["text"]
        
        # Look for status codes in the error
        status_match = re.search(r"status(?:[ _-])?code:? ?(\d+)", error_text, re.IGNORECASE)
        status_code = int(status_match.group(1)) if status_match else None
        
        if status_code:
            if status_code >= 500:
                fix_type = "server_error"
            elif status_code == 404:
                fix_type = "not_found"
            elif status_code == 401 or status_code == 403:
                fix_type = "auth_error"
            elif status_code >= 400:
                fix_type = "client_error"
            else:
                fix_type = f"status_{status_code}"
        else:
            fix_type = "api_general"
        
        return {
            "type": "api_error_fix",
            "issue": issue,
            "diagnostic": f"API {fix_type} error",
            "status_code": status_code,
            "automated_fix": False,
            "actions": [
                {
                    "type": "check_api_endpoint",
                    "implemented": False
                }
            ],
            "manual_steps": [
                "Verify API endpoint is properly implemented and accessible",
                "Check authentication credentials if relevant",
                "Review API logs for detailed error information"
            ]
        }

    def _extract_test_file_path(self, issue: Dict[str, Any]) -> Optional[str]:
        """
        Extract the test file path from the issue.

        Args:
            issue: The issue dictionary.

        Returns:
            The test file path or None if it couldn't be determined.
        """
        test_class = issue.get("test_class", "")
        test_name = issue.get("test", "")
        
        if not test_class:
            return None
        
        # Convert from test class name to file path
        # Example: tests.e2e.test_complete_order_flow -> tests/e2e/test_complete_order_flow.py
        components = test_class.split(".")
        
        # Handle the case where the class might be a TestCase class
        if len(components) > 0 and not components[-1].startswith("test_"):
            # Remove the class name
            components = components[:-1]
        
        if not components:
            return None
        
        # Construct the file path
        file_path = os.path.join(*components) + ".py"
        return file_path