"""
OpenAI configuration and API initialization.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Get OpenAI API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "dummy_key")
AGENT_API_AVAILABLE = True

logger.info("Loading OpenAI configuration")

# Import and configure OpenAI
import openai
openai.api_key = OPENAI_API_KEY