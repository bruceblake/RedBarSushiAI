#!/usr/bin/env python
"""
Test script for verifying OpenAI Realtime client imports.
This simpler version only tests the import capabilities to diagnose RealtimeClient issues.
"""

import os
import sys
import subprocess
import traceback

# Configure minimal logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Check if we want to force X11 mode for testing
USE_X11 = os.environ.get("USE_XVFB", "false").lower() in ("true", "t", "1", "yes", "y")

if USE_X11:
    # X11 mode - try to set up a virtual display if needed
    print("Running in X11 mode to test OpenAI Realtime client with display server")

    # Keep the existing DISPLAY variable if it's set
    if "DISPLAY" not in os.environ:
        # Try to set up Xvfb
        try:
            subprocess.run(
                ["which", "Xvfb"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print("Xvfb found, setting up virtual display")

            # Kill any existing Xvfb instances
            subprocess.run(["pkill", "Xvfb"], stderr=subprocess.PIPE)

            # Start Xvfb
            subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24", "-ac"])
            os.environ["DISPLAY"] = ":99"

            # Wait for Xvfb to start
            import time

            time.sleep(2)

            # Test display
            try:
                subprocess.run(
                    ["xdpyinfo"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                print(f"✅ X display server running on {os.environ['DISPLAY']}")

                # Configure for X11
                os.environ["PYNPUT_HEADLESS"] = "0"
                os.environ["NO_X11"] = "0"
                os.environ["HEADLESS"] = "0"
                os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "0"
            except subprocess.CalledProcessError:
                print(
                    "❌ Failed to connect to X display, falling back to headless mode"
                )
                os.environ["PYNPUT_HEADLESS"] = "1"
                os.environ["NO_X11"] = "1"
                os.environ["HEADLESS"] = "1"
                os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
        except subprocess.CalledProcessError:
            print("❌ Xvfb not found, cannot set up virtual display")
            # Fall back to headless mode
            os.environ["PYNPUT_HEADLESS"] = "1"
            os.environ["NO_X11"] = "1"
            os.environ["HEADLESS"] = "1"
            os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"
    else:
        print(f"Using existing X display: {os.environ['DISPLAY']}")
        # Configure for X11
        os.environ["PYNPUT_HEADLESS"] = "0"
        os.environ["NO_X11"] = "0"
        os.environ["HEADLESS"] = "0"
        os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "0"
else:
    # Headless mode
    print("Running in headless mode")
    os.environ["PYNPUT_HEADLESS"] = "1"
    os.environ["NO_X11"] = "1"
    os.environ["HEADLESS"] = "1"
    os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

    # Remove DISPLAY to prevent X11 connection attempts
    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]

# Make sure we can import from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_display_connection():
    """Test if there's a working X11 display connection."""
    display = os.environ.get("DISPLAY")
    print("\n=== Testing X11 Display Connection ===")
    print(f"DISPLAY environment variable: {display}")

    if not display:
        print("❌ No DISPLAY environment variable set")
        return False

    try:
        # Test with xdpyinfo
        subprocess.run(
            ["xdpyinfo"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print("✅ X11 display test succeeded with xdpyinfo")
        return True
    except Exception as e:
        print(f"❌ X11 display test failed with xdpyinfo: {e}")

    # If we're here, the xdpyinfo test failed
    print("❌ X11 display is not working")
    return False


def test_imports():
    """Test importing openai_realtime_client and checking available classes"""
    print("\n=== Testing OpenAI Realtime client imports ===")

    import_results = {}

    # Try importing the base module
    try:
        import openai_realtime_client

        print("✅ Successfully imported openai_realtime_client module")
        import_results["base_module"] = True

        # Check module contents
        module_contents = dir(openai_realtime_client)
        print(f"Module contents: {module_contents}")

        # Check version
        version = getattr(openai_realtime_client, "__version__", "unknown")
        print(f"OpenAI Realtime client version: {version}")

        # Look for RealtimeClient class
        if "RealtimeClient" in module_contents:
            print("✅ RealtimeClient class found in module")
            import_results["RealtimeClient_in_module"] = True

            # Try importing RealtimeClient directly
            try:
                from openai_realtime_client import RealtimeClient

                print("✅ Successfully imported RealtimeClient class")
                import_results["import_RealtimeClient"] = True

                # Try to get RealtimeClient methods
                client_methods = [
                    method
                    for method in dir(RealtimeClient)
                    if not method.startswith("_")
                ]
                print(f"RealtimeClient methods: {client_methods}")

                # Try creating a RealtimeClient instance
                try:
                    # Use a placeholder API key
                    client = RealtimeClient(api_key="sk-test")
                    print(f"✅ Successfully created RealtimeClient instance: {client}")
                    import_results["create_RealtimeClient"] = True
                except Exception as client_error:
                    print(f"❌ Error creating RealtimeClient instance: {client_error}")
                    traceback.print_exc()
                    import_results["create_RealtimeClient"] = False
            except ImportError as import_error:
                print(f"❌ Failed to import RealtimeClient: {import_error}")
                traceback.print_exc()
                import_results["import_RealtimeClient"] = False
        else:
            print("❌ RealtimeClient class not found in module")
            import_results["RealtimeClient_in_module"] = False

        # Check for client submodule
        if "client" in module_contents:
            print("\n=== Testing openai_realtime_client.client submodule ===")

            try:
                # Check client submodule contents
                client_module = openai_realtime_client.client
                client_contents = dir(client_module)
                print(f"client submodule contents: {client_contents}")

                # Look for Session class
                if "Session" in client_contents:
                    print("✅ Session class found in client submodule")
                    import_results["Session_in_client"] = True

                    # Try importing Session
                    try:
                        from openai_realtime_client.client import Session

                        print("✅ Successfully imported Session class")
                        import_results["import_Session"] = True

                        # Try creating a Session
                        try:
                            session = Session.create(api_key="sk-test")
                            print(f"✅ Successfully created Session: {session}")
                            import_results["create_Session"] = True
                        except Exception as session_error:
                            print(f"❌ Error creating Session: {session_error}")
                            traceback.print_exc()
                            import_results["create_Session"] = False
                    except ImportError as import_error:
                        print(f"❌ Failed to import Session: {import_error}")
                        traceback.print_exc()
                        import_results["import_Session"] = False
                else:
                    print("❌ Session class not found in client submodule")
                    import_results["Session_in_client"] = False
            except Exception as client_error:
                print(f"❌ Error inspecting client submodule: {client_error}")
                traceback.print_exc()
        else:
            print("❌ client submodule not found")
            import_results["client_submodule"] = False
    except ImportError as import_error:
        print(f"❌ Failed to import openai_realtime_client: {import_error}")
        traceback.print_exc()
        import_results["base_module"] = False

    # Print summary
    print("\n=== Import Test Summary ===")
    for test, result in import_results.items():
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{test}: {status}")

    return import_results


def run_tests():
    """Run all tests and return results"""
    # First check the X11 display connection
    if USE_X11:
        display_works = test_display_connection()
        print(f"X11 Display: {'✅ Working' if display_works else '❌ Not working'}")

    # Test imports
    import_results = test_imports()

    # Final verdict
    can_use_realtimeclient = import_results.get("import_RealtimeClient", False)
    print("\n=== Final Verdict ===")
    if can_use_realtimeclient:
        print("✅ The RealtimeClient class is available and can be imported")
        print("The implementation in realtime_audio.py should work with RealtimeClient")
    else:
        print("❌ The RealtimeClient class is NOT available or cannot be imported")
        print(
            "The implementation in realtime_audio.py will fall back to DirectRealtimeAudioProcessor"
        )

    # Provide recommendations
    print("\n=== Recommendations ===")
    if not import_results.get("base_module", False):
        print(
            "1. Install the openai-realtime-client package: pip install openai-realtime-client"
        )
    elif not can_use_realtimeclient:
        if USE_X11:
            print("1. Check if the X11 virtual display is properly set up")
            print("2. Make sure you have the correct version of openai-realtime-client")
        else:
            print(
                "1. Try running with X11 support: python test_realtime_client.py --with-x11"
            )
            print("2. Or use the DirectRealtimeAudioProcessor which works without X11")
    else:
        print("Everything looks good! The RealtimeClient implementation should work.")

    return import_results


if __name__ == "__main__":
    run_tests()
