"""
Test runner module for executing E2E tests against the RedBarSushiAI staging environment.
"""
import os
import subprocess
import tempfile
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from mcp.config import Config

logger = logging.getLogger(__name__)


class TestRunner:
    """
    Test runner that executes E2E tests against the RedBarSushiAI staging environment.
    """

    def __init__(self, config: Config):
        self.config = config
        self.repo_url = f"https://github.com/{config.GITHUB_REPO}.git"
        self.branch = config.GITHUB_TEST_BRANCH or "staging"
        self.base_url = config.TEST_BASE_URL

    def prepare_test_environment(self, work_dir: Path) -> Tuple[bool, str]:
        """
        Set up the test environment in the given directory.

        Args:
            work_dir: Directory to set up the test environment in.

        Returns:
            Tuple of (success, message).
        """
        try:
            # Clone the repository
            logger.info(f"Cloning repository {self.repo_url} (branch={self.branch})")
            cmd = [
                "git", 
                "clone", 
                "--depth", "1", 
                "--branch", self.branch, 
                self.repo_url, 
                str(work_dir)
            ]
            subprocess.check_call(cmd)

            # Create test environment file
            logger.info(f"Creating .env.test file in {work_dir}")
            env_file = work_dir / ".env.test"
            with open(env_file, "w") as f:
                f.write(f"TESTING=True\n")
                f.write(f"BASE_URL={self.base_url}\n")
                f.write(f"TWILIO_ACCOUNT_SID={self.config.TEST_TWILIO_ACCOUNT_SID}\n")
                f.write(f"TWILIO_AUTH_TOKEN={self.config.TEST_TWILIO_AUTH_TOKEN}\n")
                f.write(f"TWILIO_NUMBER={self.config.TEST_TWILIO_PHONE}\n")
                f.write(f"OPENAI_API_KEY={self.config.TEST_OPENAI_API_KEY}\n")
                f.write(f"DEFAULT_TEST_CUSTOMER_NUMBER={self.config.TEST_CUSTOMER_PHONE}\n")
                f.write(f"DATABASE_URL={self.config.TEST_DATABASE_URL}\n")
                f.write(f"REDIS_URL={self.config.TEST_REDIS_URL}\n")

            # Create virtual environment and install dependencies
            logger.info(f"Creating virtual environment in {work_dir}")
            subprocess.check_call(["python", "-m", "venv", ".venv"], cwd=work_dir)
            pip_path = work_dir / ".venv" / "bin" / "pip"

            # Install test dependencies
            logger.info(f"Installing dependencies")
            subprocess.check_call([str(pip_path), "install", "-r", "requirements.txt"], cwd=work_dir)
            subprocess.check_call(
                [str(pip_path), "install", "pytest", "pytest-playwright"],
                cwd=work_dir,
            )

            # Install Playwright browsers
            logger.info(f"Installing Playwright browsers")
            venv_python = work_dir / ".venv" / "bin" / "python"
            subprocess.check_call(
                [str(venv_python), "-m", "playwright", "install", "chromium"],
                cwd=work_dir,
            )

            return True, "Environment prepared successfully"
        except Exception as e:
            logger.error(f"Failed to prepare test environment: {e}")
            return False, f"Failed to prepare environment: {e}"

    def run_tests(self, specific_tests: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run the E2E tests and return results.

        Args:
            specific_tests: Optional list of specific tests to run.

        Returns:
            Dictionary with test results.
        """
        logger.info(f"Running E2E tests: {specific_tests if specific_tests else 'all'}")
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            success, message = self.prepare_test_environment(work_dir)

            if not success:
                logger.error(f"Failed to prepare test environment: {message}")
                return {
                    "success": False,
                    "message": message,
                    "tests": [],
                    "summary": {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "pass_rate": 0,
                    },
                }

            # Prepare command to run tests
            python_path = work_dir / ".venv" / "bin" / "python"
            cmd = [
                str(python_path),
                "-m",
                "pytest",
                "tests/e2e",
                "-v",
                "--junitxml=results.xml",
                "--log-cli-level=INFO",
            ]

            if specific_tests:
                cmd.extend(specific_tests)

            # Run the tests
            try:
                logger.info(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, cwd=work_dir, capture_output=True, text=True
                )
                logger.info(f"Tests completed with exit code {result.returncode}")

                # Parse the results XML file if it exists
                try:
                    tree = ET.parse(work_dir / "results.xml")
                    root = tree.getroot()

                    tests = []
                    for testcase in root.findall(".//testcase"):
                        test = {
                            "name": testcase.get("name"),
                            "classname": testcase.get("classname"),
                            "time": float(testcase.get("time")),
                            "success": True,
                            "error": None,
                            "failure": None,
                        }

                        # Check for errors or failures
                        error = testcase.find("error")
                        failure = testcase.find("failure")

                        if error is not None:
                            test["success"] = False
                            test["error"] = {
                                "message": error.get("message"),
                                "type": error.get("type"),
                                "text": error.text,
                            }

                        if failure is not None:
                            test["success"] = False
                            test["failure"] = {
                                "message": failure.get("message"),
                                "type": failure.get("type"),
                                "text": failure.text,
                            }

                        tests.append(test)

                    # Calculate overall success rate
                    total_tests = len(tests)
                    successful_tests = sum(1 for test in tests if test["success"])

                    return {
                        "success": result.returncode == 0,
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "tests": tests,
                        "summary": {
                            "total": total_tests,
                            "passed": successful_tests,
                            "failed": total_tests - successful_tests,
                            "pass_rate": successful_tests / total_tests
                            if total_tests > 0
                            else 0,
                        },
                    }
                except FileNotFoundError:
                    logger.error("results.xml not found, tests may have failed to run")
                    return {
                        "success": False,
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "message": "results.xml not found, tests may have failed to run",
                        "tests": [],
                        "summary": {
                            "total": 0,
                            "passed": 0,
                            "failed": 0,
                            "pass_rate": 0,
                        },
                    }

            except Exception as e:
                logger.error(f"Test execution failed: {e}")
                return {
                    "success": False,
                    "message": f"Test execution failed: {e}",
                    "tests": [],
                    "summary": {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "pass_rate": 0,
                    },
                }