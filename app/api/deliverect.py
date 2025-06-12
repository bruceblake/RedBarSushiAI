"""
Deliverect integration endpoints.

This module handles the channel registration and webhook management
for Deliverect integration following their official API documentation.
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# The ChannelRegistrationRequest and ChannelRegistrationResponse Pydantic models
# and the register_channel function were here.
# They have been removed as Vulture flagged register_channel as unused,
# and the models were exclusively used by this function.
