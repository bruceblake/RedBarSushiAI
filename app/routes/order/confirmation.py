"""
Order confirmation routes for RedBarSushiAI.
This module provides the routes for order confirmation and processing.
"""

import json
import logging
import requests
import uuid
import time
from datetime import datetime
from flask import request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse

# Import blueprint reference directly to avoid circular imports
from app.routes.order.__init__ import order_bp
from app.utils.order_utils import (
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
)
from app.utils.deliverect import build_deliverect_order, send_order_to_deliverect
from app.utils.agent_utils import OrderParsingAgent, get_order_modifications
from app.utils.helpers import log_info, commit_with_retry
from app.config import settings