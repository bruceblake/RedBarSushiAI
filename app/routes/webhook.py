"""
Webhook handlers for Render deploy events.
This module provides endpoints for receiving and processing deploy events from Render webhooks.
"""

import os
import hmac
import hashlib
import time
import json
import logging
import base64
from flask import Blueprint, request, jsonify, current_app
import threading

# Import the migration function
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from migrate_sms_tracking import run_migration

# Configure logging
logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)

# Time tolerance for webhook validation (5 minutes in seconds)
TOLERANCE = 5 * 60

def get_signing_secret():
    """Get the webhook signing secret from environment variables."""
    # Try different environment variable names since Render might be using a different one
    for var_name in ["RENDER_WEBHOOK_SECRET", "WEBHOOK_SECRET", "WEBHOOK_SIGNING_SECRET", "RENDER_SIGNING_SECRET"]:
        secret = os.environ.get(var_name)
        if secret:
            logger.info(f"Using webhook signing secret from {var_name}")
            return secret
            
    # For development/testing, allow a special bypass if explicitly enabled
    if os.environ.get("WEBHOOK_BYPASS_SIGNATURE") == "true" and current_app.config.get("DEBUG", False):
        logger.warning("WEBHOOK_BYPASS_SIGNATURE is enabled - skipping signature validation in debug mode")
        return "debug_bypass_secret"
        
    logger.warning("No webhook signing secret found in environment variables!")
    return None

def validate_signature(payload, signature_header, timestamp_header, id_header):
    """
    Validate the webhook signature using HMAC-SHA256.
    
    Format: WEBHOOK_ID.WEBHOOK_TIMESTAMP.REQUEST_BODY.SIGNING_SECRET
    """
    if not all([signature_header, timestamp_header, id_header]):
        logger.error("Missing required headers for webhook validation")
        return False
    
    signing_secret = get_signing_secret()
    if not signing_secret:
        # If no secret is configured, we can't validate - treat as valid in dev
        return current_app.config.get("DEBUG", False)
    
    # Check timestamp to prevent replay attacks
    try:
        timestamp = int(timestamp_header)
        now = int(time.time())
        if abs(now - timestamp) > TOLERANCE:
            logger.error(f"Webhook timestamp too old or from future: {timestamp}")
            return False
    except (ValueError, TypeError):
        logger.error(f"Invalid webhook timestamp: {timestamp_header}")
        return False
    
    # Parse signature header
    try:
        sig_parts = signature_header.split(",")
        if len(sig_parts) != 2 or sig_parts[0] != "v1":
            logger.error(f"Invalid signature format: {signature_header}")
            return False
        received_sig = sig_parts[1]
    except (ValueError, IndexError):
        logger.error(f"Could not parse signature: {signature_header}")
        return False
    
    # Compute expected signature
    payload_str = payload if isinstance(payload, str) else payload.decode('utf-8')
    # Log message components for debugging
    logger.debug(f"Webhook ID: {id_header}")
    logger.debug(f"Timestamp: {timestamp_header}")
    logger.debug(f"Payload: {payload_str[:100]}...")
    
    message = f"{id_header}.{timestamp_header}.{payload_str}.{signing_secret}"
    logger.debug(f"Message format: [webhook_id].[timestamp].[payload].[secret]")
    
    computed_sig = hmac.new(
        signing_secret.encode('utf-8'),
        message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    computed_sig_b64 = base64.b64encode(computed_sig).decode('utf-8')
    
    # Log the first few characters of both signatures for comparison
    # (safe to log partial signatures for debugging)
    logger.debug(f"Received sig start: {received_sig[:10]}...")
    logger.debug(f"Computed sig start: {computed_sig_b64[:10]}...")
    
    # Compare signatures using constant-time comparison
    return hmac.compare_digest(received_sig, computed_sig_b64)

def run_migration_in_thread():
    """Run the migration script in a separate thread to not block the response."""
    try:
        logger.info("Starting database migration after deploy")
        success = run_migration()
        if success:
            logger.info("Database migration completed successfully")
        else:
            logger.error("Database migration failed")
    except Exception as e:
        logger.exception(f"Error running migration: {e}")


@webhook_bp.route("/webhooks/deploy", methods=["POST"])
def handle_deploy_webhook():
    """
    Handle deploy webhooks from Render.
    
    This endpoint receives webhook notifications about deploy events
    and triggers the SMS tracking migration if a deploy has completed successfully.
    """
    # Get request data and headers
    payload = request.get_data()
    
    # Try different header case variations
    signature = (request.headers.get("webhook-signature") or 
                request.headers.get("Webhook-Signature") or
                request.headers.get("WEBHOOK-SIGNATURE") or
                request.headers.get("x-webhook-signature") or
                request.headers.get("X-Webhook-Signature"))
    
    timestamp = (request.headers.get("webhook-timestamp") or 
                request.headers.get("Webhook-Timestamp") or
                request.headers.get("WEBHOOK-TIMESTAMP") or
                request.headers.get("x-webhook-timestamp") or
                request.headers.get("X-Webhook-Timestamp"))
    
    webhook_id = (request.headers.get("webhook-id") or 
                request.headers.get("Webhook-Id") or
                request.headers.get("WEBHOOK-ID") or
                request.headers.get("x-webhook-id") or
                request.headers.get("X-Webhook-Id"))
    
    # Log webhook receipt and all headers for debugging
    logger.info(f"Received webhook: ID={webhook_id}, Time={timestamp}")
    logger.debug(f"All headers: {dict(request.headers)}")
    
    # Validate the webhook signature
    # Allow bypass for testing if explicitly configured
    if os.environ.get("ALLOW_UNSIGNED_WEBHOOKS") == "true":
        logger.warning("⚠️ BYPASSING webhook signature validation (ALLOW_UNSIGNED_WEBHOOKS=true)")
        # Continue without validating
    elif not validate_signature(payload, signature, timestamp, webhook_id):
        # Log detailed debugging information
        logger.warning("Invalid webhook signature")
        logger.info(f"Signature: {signature}, Timestamp: {timestamp}, ID: {webhook_id}")
        # Check if any required components are missing
        missing = []
        if not signature: missing.append("Signature")
        if not timestamp: missing.append("Timestamp") 
        if not webhook_id: missing.append("Webhook ID")
        
        error_message = "Invalid signature"
        if missing:
            error_message += f" - Missing required headers: {', '.join(missing)}"
            
        # Log environment variable names for webhook secret
        secret_vars = ["RENDER_WEBHOOK_SECRET", "WEBHOOK_SECRET", "WEBHOOK_SIGNING_SECRET", "RENDER_SIGNING_SECRET"]
        configured_vars = [var for var in secret_vars if os.environ.get(var)]
        if configured_vars:
            logger.info(f"Webhook secret configured with: {', '.join(configured_vars)}")
        else:
            logger.warning("No webhook secret environment variables set")
            
        return jsonify({"status": "error", "message": error_message}), 401
    
    # Parse the payload
    try:
        data = json.loads(payload)
        event_type = data.get("type")
        logger.info(f"Processing webhook event type: {event_type}")
        
        # Check if this is a deploy_ended event
        if event_type == "deploy_ended":
            # Ideally fetch more details about the deploy to check if it succeeded
            # For now, we'll assume it succeeded and run the migration
            logger.info("Detected deploy_ended event, triggering database migration")
            
            # Run migration in separate thread to not block response
            threading.Thread(target=run_migration_in_thread).start()
            
            return jsonify({
                "status": "success", 
                "message": "Migration triggered"
            }), 200
            
        # Return success for other event types
        return jsonify({
            "status": "success", 
            "message": f"Received {event_type} event"
        }), 200
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@webhook_bp.route("/webhooks/test", methods=["GET"])
def test_webhook():
    """Test endpoint to verify webhook configuration."""
    # Check if webhook secret is configured
    signing_secret = get_signing_secret()
    secret_vars = ["RENDER_WEBHOOK_SECRET", "WEBHOOK_SECRET", "WEBHOOK_SIGNING_SECRET", "RENDER_SIGNING_SECRET"]
    configured_vars = [var for var in secret_vars if os.environ.get(var)]
    
    return jsonify({
        "status": "success",
        "message": "Webhook endpoint is configured correctly",
        "environment": {
            "debug": current_app.config.get("DEBUG", False),
            "test": current_app.config.get("TESTING", False),
            "webhook_secret_configured": signing_secret is not None,
            "configured_secret_vars": configured_vars,
            "allow_unsigned": os.environ.get("ALLOW_UNSIGNED_WEBHOOKS") == "true"
        }
    })

@webhook_bp.route("/webhooks/debug", methods=["POST"])
def debug_webhook():
    """
    Debug endpoint for webhook troubleshooting.
    This endpoint logs all headers and request data for diagnostic purposes.
    Only enabled in debug mode.
    """
    if not current_app.config.get("DEBUG", False) and os.environ.get("ALLOW_WEBHOOK_DEBUG") != "true":
        return jsonify({"status": "error", "message": "Debug endpoint only available in debug mode"}), 403
    
    # Get all headers
    headers = dict(request.headers)
    
    # Get request data
    payload = request.get_data()
    payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else payload
    
    # Try to parse as JSON
    try:
        payload_json = json.loads(payload_str)
    except:
        payload_json = None
    
    # Log everything
    logger.info(f"Debug webhook received")
    logger.debug(f"Headers: {headers}")
    logger.debug(f"Raw payload: {payload_str[:500]}...")
    
    # Return diagnostic information
    return jsonify({
        "status": "success",
        "message": "Webhook debug information",
        "headers": headers,
        "payload": payload_json or payload_str[:1000],
        "webhook_secret_configured": get_signing_secret() is not None
    })