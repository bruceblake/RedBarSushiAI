#!/usr/bin/env python3
"""
Comprehensive WebSocket Test Runner for RedBarSushiAI

This script runs all the WebSocket tests we've created, including:
1. WebSocket Stability Test
2. Failure Mode Tests
3. Server Monitoring

It provides a comprehensive report on the reliability of the WebSocket implementation.

Usage:
    python run_websocket_tests.py [--url URL] [--duration SECONDS]
"""

import os
import sys
import time
import asyncio
import argparse
import logging
import subprocess
import json
import signal
import traceback
from datetime import datetime, timedelta
import concurrent.futures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket_tests.log')
    ]
)
logger = logging.getLogger("websocket_tests")

# Test results
test_results = {
    "start_time": None,
    "end_time": None,
    "total_duration": None,
    "stability_test": None,
    "failure_mode_tests": None,
    "server_test": None,
    "overall_result": None
}

def run_server_process(port=5000):
    """Run the WebSocket test server as a subprocess."""
    logger.info(f"Starting WebSocket test server on port {port}")
    server_cmd = ["python", "websocket_test_server.py"]
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    # Start the server process
    server_process = subprocess.Popen(
        server_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Give the server a moment to start
    time.sleep(2)
    
    # Check if process is still running
    if server_process.poll() is not None:
        logger.error(f"Server process failed to start with exit code {server_process.returncode}")
        stdout, _ = server_process.communicate()
        logger.error(f"Server output: {stdout}")
        return None
    
    logger.info(f"Server started with PID {server_process.pid}")
    return server_process

def run_stability_test(url, duration=60):
    """Run the WebSocket stability test."""
    logger.info(f"Running stability test against {url} for {duration}s")
    
    cmd = ["python", "websocket_stability_client.py", "--url", url, "--duration", str(duration)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Extract key statistics
        success = result.returncode == 0
        output = result.stdout
        error = result.stderr
        
        # Parse important metrics from output
        metrics = {}
        if output:
            # Extract key metrics
            try:
                # Look for connection duration
                connection_duration_match = re.search(r"Connection duration:\s+(\d+\.\d+)s", output)
                if connection_duration_match:
                    metrics["connection_duration"] = float(connection_duration_match.group(1))
                
                # Look for post-greeting duration
                post_greeting_match = re.search(r"Post-greeting time:\s+(\d+\.\d+)s", output)
                if post_greeting_match:
                    metrics["post_greeting_duration"] = float(post_greeting_match.group(1))
                
                # Look for message counts
                messages_received_match = re.search(r"Messages received:\s+(\d+)", output)
                if messages_received_match:
                    metrics["messages_received"] = int(messages_received_match.group(1))
                
                messages_sent_match = re.search(r"Messages sent:\s+(\d+)", output)
                if messages_sent_match:
                    metrics["messages_sent"] = int(messages_sent_match.group(1))
            except Exception as e:
                logger.error(f"Error parsing stability test metrics: {e}")
        
        return {
            "success": success,
            "output": output,
            "error": error,
            "metrics": metrics
        }
    
    except Exception as e:
        logger.error(f"Error running stability test: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "metrics": {}
        }

def run_failure_mode_tests(url):
    """Run the WebSocket failure mode tests."""
    logger.info(f"Running failure mode tests against {url}")
    
    cmd = ["python", "test_failure_modes.py", "--url", url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Extract key statistics
        success = result.returncode == 0
        output = result.stdout
        error = result.stderr
        
        # Parse test results
        tests_data = []
        if output:
            # Look for individual test results
            import re
            test_pattern = r"(✅ PASSED|❌ FAILED): ([^-]+) - (\d+\.\d+)s"
            for match in re.finditer(test_pattern, output):
                status = match.group(1) == "✅ PASSED"
                name = match.group(2).strip()
                duration = float(match.group(3))
                
                # Look for error reason (if any)
                error_reason = None
                if not status:
                    error_pattern = rf"❌ FAILED: {re.escape(name)}.*?\n\s+Reason: ([^\n]+)"
                    error_match = re.search(error_pattern, output, re.DOTALL)
                    if error_match:
                        error_reason = error_match.group(1).strip()
                
                tests_data.append({
                    "name": name,
                    "success": status,
                    "duration": duration,
                    "error": error_reason
                })
        
        # Parse summary metrics
        metrics = {}
        if output:
            # Look for test counts
            tests_run_match = re.search(r"Tests Run:\s+(\d+)", output)
            if tests_run_match:
                metrics["tests_run"] = int(tests_run_match.group(1))
            
            tests_passed_match = re.search(r"Tests Passed:\s+(\d+)", output)
            if tests_passed_match:
                metrics["tests_passed"] = int(tests_passed_match.group(1))
            
            tests_failed_match = re.search(r"Tests Failed:\s+(\d+)", output)
            if tests_failed_match:
                metrics["tests_failed"] = int(tests_failed_match.group(1))
            
            pass_rate_match = re.search(r"Pass Rate:\s+(\d+\.\d+)%", output)
            if pass_rate_match:
                metrics["pass_rate"] = float(pass_rate_match.group(1))
        
        return {
            "success": success,
            "output": output,
            "error": error,
            "metrics": metrics,
            "tests": tests_data
        }
    
    except Exception as e:
        logger.error(f"Error running failure mode tests: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "metrics": {},
            "tests": []
        }

def kill_process(process):
    """Kill a process and its children."""
    if process is None:
        return
    
    if sys.platform == "win32":
        # Windows - use taskkill to kill process tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)])
    else:
        # Unix-like - use os.killpg
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except:
            # Fallback to regular kill
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def verify_fixes():
    """Run the verification script to check if all fixes are properly applied."""
    logger.info("Verifying WebSocket fixes...")
    
    cmd = ["python", "verify_websocket_fixes.py"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Extract key statistics
        success = result.returncode == 0
        output = result.stdout
        error = result.stderr
        
        # Parse verification results
        checks = []
        if output:
            # Look for individual checks
            import re
            check_pattern = r"([^:]+): (✅ Found|❌ Missing)"
            for match in re.finditer(check_pattern, output):
                name = match.group(1).strip()
                status = match.group(2) == "✅ Found"
                
                checks.append({
                    "name": name,
                    "success": status
                })
        
        return {
            "success": success,
            "output": output,
            "error": error,
            "checks": checks
        }
    
    except Exception as e:
        logger.error(f"Error verifying fixes: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "checks": []
        }

def run_all_tests(url, duration=60):
    """Run all WebSocket tests and generate a comprehensive report."""
    logger.info(f"Starting comprehensive WebSocket testing against {url}")
    
    # Record start time
    test_results["start_time"] = datetime.now().isoformat()
    
    # First verify that all fixes are in place
    verification_result = verify_fixes()
    
    # Run stability test
    stability_result = run_stability_test(url, duration)
    test_results["stability_test"] = stability_result
    
    # Run failure mode tests
    failure_mode_result = run_failure_mode_tests(url)
    test_results["failure_mode_tests"] = failure_mode_result
    
    # Record end time and calculate duration
    test_results["end_time"] = datetime.now().isoformat()
    start_time = datetime.fromisoformat(test_results["start_time"])
    end_time = datetime.fromisoformat(test_results["end_time"])
    test_results["total_duration"] = (end_time - start_time).total_seconds()
    
    # Determine overall result
    stability_success = stability_result.get("success", False)
    failure_mode_success = failure_mode_result.get("success", False)
    verification_success = verification_result.get("success", False)
    
    # Overall result requires both tests to pass and verification to succeed
    test_results["overall_result"] = stability_success and failure_mode_success and verification_success
    
    # Include verification results
    test_results["verification"] = verification_result
    
    # Generate the report
    generate_report(test_results)
    
    return test_results["overall_result"]

def generate_report(results):
    """Generate a comprehensive report of all test results."""
    # Create HTML report
    html_file = "websocket_test_report.html"
    
    # Format start and end times
    start_time_str = datetime.fromisoformat(results["start_time"]).strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = datetime.fromisoformat(results["end_time"]).strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate HTML content
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test Report - {start_time_str}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }}
        h1, h2, h3 {{ color: #333; }}
        .report-header {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 30px; }}
        .test-result {{ margin-bottom: 15px; padding: 10px; border-radius: 5px; }}
        .success {{ background-color: #e6ffe6; border-left: 5px solid #4CAF50; }}
        .failure {{ background-color: #ffe6e6; border-left: 5px solid #f44336; }}
        .neutral {{ background-color: #e6f0ff; border-left: 5px solid #2196F3; }}
        .metrics {{ margin: 10px 0; }}
        .metric {{ margin: 5px 0; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .pass {{ color: #4CAF50; }}
        .fail {{ color: #f44336; }}
        pre {{ background-color: #f5f5f5; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="report-header">
        <h1>WebSocket Test Report</h1>
        <p><strong>Test Start:</strong> {start_time_str}</p>
        <p><strong>Test End:</strong> {end_time_str}</p>
        <p><strong>Total Duration:</strong> {results["total_duration"]:.2f} seconds</p>
        <p><strong>Overall Result:</strong> <span class="{'pass' if results['overall_result'] else 'fail'}">{results['overall_result']}</span></p>
    </div>
    
    <div class="section">
        <h2>Fix Verification</h2>
        <div class="test-result {'success' if results['verification']['success'] else 'failure'}">
            <h3>Verification Result: {'Success' if results['verification']['success'] else 'Failure'}</h3>
            
            <h4>Implemented Fixes</h4>
            <table>
                <tr>
                    <th>Check</th>
                    <th>Status</th>
                </tr>
"""
    
    # Add verification checks
    for check in results["verification"]["checks"]:
        html_content += f"""
                <tr>
                    <td>{check['name']}</td>
                    <td class="{'pass' if check['success'] else 'fail'}">{check['success']}</td>
                </tr>
"""
    
    html_content += """
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>Stability Test</h2>
        <div class="test-result {'success' if results['stability_test']['success'] else 'failure'}">
            <h3>Test Result: {'Success' if results['stability_test']['success'] else 'Failure'}</h3>
            
            <div class="metrics">
                <h4>Metrics</h4>
"""
    
    # Add stability metrics
    for key, value in results["stability_test"]["metrics"].items():
        # Format the metric value based on its type
        if isinstance(value, float):
            formatted_value = f"{value:.2f}"
        else:
            formatted_value = str(value)
        
        html_content += f"""
                <div class="metric"><strong>{key}:</strong> {formatted_value}</div>
"""
    
    html_content += """
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Failure Mode Tests</h2>
        <div class="test-result {'success' if results['failure_mode_tests']['success'] else 'failure'}">
            <h3>Overall Result: {'Success' if results['failure_mode_tests']['success'] else 'Failure'}</h3>
            
            <div class="metrics">
                <h4>Summary Metrics</h4>
"""
    
    # Add failure mode test metrics
    for key, value in results["failure_mode_tests"]["metrics"].items():
        # Format the metric value based on its type
        if isinstance(value, float):
            formatted_value = f"{value:.2f}"
            if key == "pass_rate":
                formatted_value += "%"
        else:
            formatted_value = str(value)
        
        html_content += f"""
                <div class="metric"><strong>{key}:</strong> {formatted_value}</div>
"""
    
    html_content += """
            </div>
            
            <h4>Individual Tests</h4>
            <table>
                <tr>
                    <th>Test</th>
                    <th>Result</th>
                    <th>Duration (s)</th>
                    <th>Error (if any)</th>
                </tr>
"""
    
    # Add individual failure mode tests
    for test in results["failure_mode_tests"]["tests"]:
        html_content += f"""
                <tr>
                    <td>{test['name']}</td>
                    <td class="{'pass' if test['success'] else 'fail'}">{test['success']}</td>
                    <td>{test['duration']:.2f}</td>
                    <td>{test.get('error', '')}</td>
                </tr>
"""
    
    html_content += """
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>Detailed Logs</h2>
        <div class="test-result neutral">
            <h3>Stability Test Output</h3>
            <pre>{}</pre>
            
            <h3>Failure Mode Tests Output</h3>
            <pre>{}</pre>
        </div>
    </div>
    
    <div class="report-header">
        <h2>Conclusion</h2>
        <p>The WebSocket implementation is {}.</p>
        <p>Report generated on {} by the RedBarSushiAI WebSocket Test Runner</p>
    </div>
</body>
</html>
""".format(
        results["stability_test"]["output"][:1000] + "..." if len(results["stability_test"]["output"]) > 1000 else results["stability_test"]["output"],
        results["failure_mode_tests"]["output"][:1000] + "..." if len(results["failure_mode_tests"]["output"]) > 1000 else results["failure_mode_tests"]["output"],
        "stable and reliable" if results["overall_result"] else "not stable enough",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Write HTML report
    with open(html_file, "w") as f:
        f.write(html_content)
    
    # Also write JSON report
    json_file = "websocket_test_report.json"
    with open(json_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test report generated: {html_file} and {json_file}")

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Comprehensive WebSocket Test Runner for RedBarSushiAI")
    parser.add_argument("--url", type=str, help="WebSocket URL to test (default: auto-start local server)")
    parser.add_argument("--duration", type=int, default=60, help="Duration of stability test in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Determine if we need to start a local server
    server_process = None
    test_url = args.url
    
    try:
        if not test_url:
            # Start local server
            port = 5000
            server_process = run_server_process(port)
            if server_process is None:
                logger.error("Failed to start local server, exiting")
                sys.exit(1)
            
            test_url = f"ws://localhost:{port}/ws/voice/media"
            logger.info(f"Using local test server at {test_url}")
        
        # Run all tests
        success = run_all_tests(test_url, args.duration)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Clean up server process if we started one
        if server_process is not None:
            logger.info(f"Shutting down test server (PID {server_process.pid})")
            kill_process(server_process)

if __name__ == "__main__":
    import re  # Import here to avoid any potential naming conflicts
    main()