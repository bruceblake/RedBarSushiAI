"""
Webhook security for RedBarSushiAI.

This module provides request signing and verification for webhooks
to ensure authenticity and prevent tampering.
"""

import hmac
import hashlib
import time
import json
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

logger = logging.getLogger(__name__)


class WebhookSigner:
    """Signs outgoing webhook requests."""
    
    def __init__(self, secret: str):
        """Initialize with signing secret."""
        self.secret = secret.encode('utf-8')
    
    def sign_request(
        self,
        payload: Dict[str, Any],
        timestamp: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Sign a webhook request payload.
        
        Args:
            payload: The request payload to sign
            timestamp: Unix timestamp (defaults to current time)
            
        Returns:
            Dictionary with signature headers
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        # Serialize payload
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Create signature base string
        signature_base = f"{timestamp}.{payload_str}"
        
        # Generate signature
        signature = hmac.new(
            self.secret,
            signature_base.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Return headers
        return {
            'X-Webhook-Signature': signature,
            'X-Webhook-Timestamp': str(timestamp),
            'X-Webhook-Version': 'v1'
        }
    
    def verify_signature(
        self,
        payload: str,
        signature: str,
        timestamp: str,
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verify a webhook signature.
        
        Args:
            payload: The raw request payload
            signature: The provided signature
            timestamp: The provided timestamp
            max_age_seconds: Maximum age of request in seconds
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Check timestamp age
            request_timestamp = int(timestamp)
            current_timestamp = int(time.time())
            
            if abs(current_timestamp - request_timestamp) > max_age_seconds:
                logger.warning(f"Webhook timestamp too old: {request_timestamp}")
                return False
            
            # Recreate signature
            signature_base = f"{timestamp}.{payload}"
            expected_signature = hmac.new(
                self.secret,
                signature_base.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False


class TwilioWebhookVerifier:
    """Verifies Twilio webhook requests."""
    
    def __init__(self, auth_token: str):
        """Initialize with Twilio auth token."""
        self.auth_token = auth_token
    
    def compute_signature(
        self,
        url: str,
        params: Dict[str, str]
    ) -> str:
        """
        Compute Twilio webhook signature.
        
        Args:
            url: The full webhook URL
            params: The request parameters
            
        Returns:
            The computed signature
        """
        # Sort parameters by key
        sorted_params = sorted(params.items())
        
        # Build the string to sign
        data = url
        for key, value in sorted_params:
            data += key + str(value)
        
        # Compute signature
        signature = base64.b64encode(
            hmac.new(
                self.auth_token.encode('utf-8'),
                data.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        return signature
    
    async def verify_request(
        self,
        request: Request,
        url: str
    ) -> bool:
        """
        Verify a Twilio webhook request.
        
        Args:
            request: The FastAPI request object
            url: The webhook URL
            
        Returns:
            True if request is valid
        """
        try:
            # Get signature from header
            signature = request.headers.get('X-Twilio-Signature')
            if not signature:
                logger.warning("Missing X-Twilio-Signature header")
                return False
            
            # Get request parameters
            if request.method == "POST":
                form_data = await request.form()
                params = dict(form_data)
            else:
                params = dict(request.query_params)
            
            # Compute expected signature
            expected_signature = self.compute_signature(url, params)
            
            # Compare signatures
            return signature == expected_signature
            
        except Exception as e:
            logger.error(f"Error verifying Twilio webhook: {e}")
            return False


class DeliverectWebhookVerifier:
    """Verifies Deliverect webhook requests."""
    
    def __init__(self, webhook_secret: str):
        """Initialize with Deliverect webhook secret."""
        self.secret = webhook_secret.encode('utf-8')
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify Deliverect webhook signature.
        
        Args:
            payload: The raw request body
            signature: The provided signature
            
        Returns:
            True if signature is valid
        """
        try:
            # Deliverect uses HMAC-SHA256
            expected_signature = hmac.new(
                self.secret,
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(
                signature.lower(),
                expected_signature.lower()
            )
            
        except Exception as e:
            logger.error(f"Error verifying Deliverect webhook: {e}")
            return False


class WebhookAuthMiddleware:
    """Middleware for webhook authentication."""
    
    def __init__(self):
        """Initialize webhook verifiers."""
        self.twilio_verifier = None
        self.deliverect_verifier = None
        self.general_verifier = None
        
        # Initialize based on config
        if hasattr(settings, 'TWILIO_AUTH_TOKEN'):
            self.twilio_verifier = TwilioWebhookVerifier(settings.TWILIO_AUTH_TOKEN)
        
        if hasattr(settings, 'DELIVERECT_WEBHOOK_SECRET'):
            self.deliverect_verifier = DeliverectWebhookVerifier(
                settings.DELIVERECT_WEBHOOK_SECRET
            )
        
        if hasattr(settings, 'WEBHOOK_SECRET'):
            self.general_verifier = WebhookSigner(settings.WEBHOOK_SECRET)
    
    async def verify_twilio_webhook(
        self,
        request: Request,
        url: str
    ) -> None:
        """
        Verify Twilio webhook request.
        
        Raises:
            HTTPException: If verification fails
        """
        if not self.twilio_verifier:
            logger.warning("Twilio webhook verifier not configured")
            raise HTTPException(status_code=500, detail="Webhook verification not configured")
        
        if not await self.twilio_verifier.verify_request(request, url):
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    async def verify_deliverect_webhook(
        self,
        request: Request
    ) -> None:
        """
        Verify Deliverect webhook request.
        
        Raises:
            HTTPException: If verification fails
        """
        if not self.deliverect_verifier:
            logger.warning("Deliverect webhook verifier not configured")
            raise HTTPException(status_code=500, detail="Webhook verification not configured")
        
        # Get signature from header
        signature = request.headers.get('X-Deliverect-Signature')
        if not signature:
            logger.warning("Missing X-Deliverect-Signature header")
            raise HTTPException(status_code=401, detail="Missing signature header")
        
        # Get raw body
        body = await request.body()
        
        if not self.deliverect_verifier.verify_signature(body, signature):
            logger.warning("Invalid Deliverect webhook signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    async def verify_general_webhook(
        self,
        request: Request
    ) -> None:
        """
        Verify general webhook request.
        
        Raises:
            HTTPException: If verification fails
        """
        if not self.general_verifier:
            logger.warning("General webhook verifier not configured")
            raise HTTPException(status_code=500, detail="Webhook verification not configured")
        
        # Get headers
        signature = request.headers.get('X-Webhook-Signature')
        timestamp = request.headers.get('X-Webhook-Timestamp')
        
        if not signature or not timestamp:
            logger.warning("Missing webhook signature headers")
            raise HTTPException(status_code=401, detail="Missing signature headers")
        
        # Get raw body
        body = await request.body()
        
        if not self.general_verifier.verify_signature(
            body.decode('utf-8'),
            signature,
            timestamp
        ):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")


# Rate limiting for webhooks

class WebhookRateLimiter:
    """Rate limiter for webhook endpoints."""
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        """Initialize rate limiter."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts: Dict[str, list] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed.
        
        Args:
            identifier: Unique identifier (e.g., IP address, API key)
            
        Returns:
            True if request is allowed
        """
        current_time = time.time()
        
        # Initialize if new identifier
        if identifier not in self.request_counts:
            self.request_counts[identifier] = []
        
        # Remove old requests outside window
        self.request_counts[identifier] = [
            timestamp for timestamp in self.request_counts[identifier]
            if current_time - timestamp < self.window_seconds
        ]
        
        # Check if under limit
        if len(self.request_counts[identifier]) < self.max_requests:
            self.request_counts[identifier].append(current_time)
            return True
        
        return False
    
    def cleanup(self):
        """Clean up old entries."""
        current_time = time.time()
        
        # Remove identifiers with no recent requests
        identifiers_to_remove = []
        for identifier, timestamps in self.request_counts.items():
            if not timestamps or current_time - max(timestamps) > self.window_seconds:
                identifiers_to_remove.append(identifier)
        
        for identifier in identifiers_to_remove:
            del self.request_counts[identifier]


# Webhook security decorators

webhook_auth = WebhookAuthMiddleware()
webhook_rate_limiter = WebhookRateLimiter()


async def require_twilio_webhook(request: Request, url: str):
    """Dependency to require valid Twilio webhook."""
    await webhook_auth.verify_twilio_webhook(request, url)


async def require_deliverect_webhook(request: Request):
    """Dependency to require valid Deliverect webhook."""
    await webhook_auth.verify_deliverect_webhook(request)


async def require_webhook_auth(request: Request):
    """Dependency to require valid webhook authentication."""
    await webhook_auth.verify_general_webhook(request)


async def check_webhook_rate_limit(request: Request):
    """Dependency to check webhook rate limit."""
    # Use IP address as identifier
    client_ip = request.client.host
    
    if not webhook_rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for webhook from {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


# Utility functions

def generate_webhook_secret(length: int = 32) -> str:
    """Generate a secure webhook secret."""
    import secrets
    return secrets.token_urlsafe(length)


def create_webhook_headers(
    payload: Dict[str, Any],
    secret: str
) -> Dict[str, str]:
    """Create webhook headers with signature."""
    signer = WebhookSigner(secret)
    return signer.sign_request(payload)


# Example usage in FastAPI endpoints:
#
# @app.post("/webhooks/twilio")
# async def handle_twilio_webhook(
#     request: Request,
#     _: None = Depends(require_twilio_webhook)
# ):
#     # Webhook is verified
#     ...
#
# @app.post("/webhooks/deliverect")
# async def handle_deliverect_webhook(
#     request: Request,
#     _: None = Depends(require_deliverect_webhook),
#     __: None = Depends(check_webhook_rate_limit)
# ):
#     # Webhook is verified and rate limited
#     ...