# x11_init.py - Initialize X11 environment for OpenAI Realtime client
import os
import logging


def initialize_x11():
    """Initialize X11 environment for OpenAI Realtime client."""
    # If X11_SETUP_SUCCESS is set, ensure all X11 environment variables are properly set
    if os.environ.get("X11_SETUP_SUCCESS") == "true":
        if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
            # Default to display :99 if not set
            os.environ["DISPLAY"] = ":99"

        # Reset all X11-related environment variables
        os.environ["PYNPUT_HEADLESS"] = "0"
        os.environ["NO_X11"] = "0"
        os.environ["HEADLESS"] = "0"
        os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "0"

        logging.info(
            f"X11 environment initialized with DISPLAY={os.environ['DISPLAY']}"
        )
        return True

    return False
