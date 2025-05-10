"""
Order checkout and processing routes for RedBarSushiAI.
This module provides the routes for order checkout and final processing.
"""

import json
import logging
import requests
import uuid
import time
import re
from datetime import datetime
from flask import request, session, Response, url_for, redirect, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Import blueprint reference directly to avoid circular imports
from app.routes.order.__init__ import order_bp
from app.utils.order_utils import mark_unavailable_items, build_order_description, validate_modifiers
from app.utils.deliverect import (
    build_deliverect_order, 
    get_deliverect_headers, 
    send_order_to_deliverect,
    generate_order_id
)
from app.utils.helpers import log_info, commit_with_retry
from app.config import settings