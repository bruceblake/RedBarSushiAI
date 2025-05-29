#!/usr/bin/env python3
"""
Run all e2e tests and generate a comprehensive report.
"""

import subprocess
import sys
import os
from datetime import datetime

# Test categories
test_categories = {
    "ConversationRelay & FSM": [
        "tests/e2e/test_conversationrelay_fsm.py",
        "tests/e2e/test_llm_intent_detection.py"
    ],
    "Menu System": [
        "tests/e2e/test_menu_system_integration.py"
    ],
    "Ordering Flow": [
        "tests/e2e/test_complete_ordering_flow.py"
    ],
    "API Endpoints": [
        "tests/e2e/test_fastapi_voice_flow.py",
        "tests/e2e/webhook/test_voice_entry.py"
    ],
    "Agent System": [
        "tests/e2e/test_agent_orchestration.py",
        "tests/e2e/test_agents_sdk.py"
    ],
    "WebSocket": [
        "tests/e2e/test_websocket_connection_resilience.py",
        "tests/e2e/voice/test_voice_media_stream.py"
    ]
}

def run_tests():
    """Run all e2e tests with detailed reporting."""
    print("=" * 80)
    print("RedBarSushiAI E2E Test Suite")
    print(f"Started at: {datetime.now()}")
    print("=" * 80)
    
    total_passed = 0
    total_failed = 0
    failed_tests = []
    
    for category, test_files in test_categories.items():
        print(f"\n{category}")
        print("-" * len(category))
        
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                    capture_output=True,
                    text=True
                )
                
                # Parse results
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if " passed" in line and " failed" in line:
                        # Extract numbers
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "passed":
                                passed = int(parts[i-1])
                                total_passed += passed
                            elif part == "failed":
                                failed = int(parts[i-1])
                                total_failed += failed
                                if failed > 0:
                                    failed_tests.append(test_file)
                    elif "PASSED" in line or "FAILED" in line:
                        print(f"  {line.strip()}")
                
                # Print any errors
                if result.returncode != 0:
                    print(f"\nErrors in {test_file}:")
                    print(result.stderr[:500])  # First 500 chars of error
            else:
                print(f"  ⚠️  {test_file} not found")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    
    if failed_tests:
        print("\nFailed Tests:")
        for test in failed_tests:
            print(f"  ❌ {test}")
    else:
        print("\n✅ All tests passed!")
    
    print(f"\nCompleted at: {datetime.now()}")
    
    return total_failed == 0


def main():
    """Main entry point."""
    # Check if we're in Docker
    if os.path.exists("/.dockerenv"):
        print("Running in Docker container")
    else:
        print("Running locally")
        print("Consider running: docker-compose exec app python run_all_e2e_tests.py")
    
    success = run_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()