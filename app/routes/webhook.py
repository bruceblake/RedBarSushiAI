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
    
    # Get payload as string
    payload_str = payload if isinstance(payload, str) else payload.decode('utf-8')
    logger.debug(f"Webhook ID: {id_header}")
    logger.debug(f"Timestamp: {timestamp_header}")
    logger.debug(f"Payload: {payload_str[:100]}...")
    
    # Try ALL possible message formats that Render might be using
    signature_methods = []
    
    # Method 1: Standard format with original payload
    standard_message = f"{id_header}.{timestamp_header}.{payload_str}.{signing_secret}"
    signature_methods.append(("Standard", standard_message))
    
    # Method 2: Try parsing and re-serializing to compact JSON
    try:
        payload_json = json.loads(payload_str)
        compact_payload = json.dumps(payload_json, separators=(',', ':'))
        compact_message = f"{id_header}.{timestamp_header}.{compact_payload}.{signing_secret}"
        signature_methods.append(("Compact JSON", compact_message))
        
        # Method 3: Try with json.dumps default formatting
        default_payload = json.dumps(payload_json)
        default_message = f"{id_header}.{timestamp_header}.{default_payload}.{signing_secret}"
        signature_methods.append(("Default JSON", default_message))
        
        # Method 4: Try with pretty-print formatting
        pretty_payload = json.dumps(payload_json, indent=2)
        pretty_message = f"{id_header}.{timestamp_header}.{pretty_payload}.{signing_secret}"
        signature_methods.append(("Pretty JSON", pretty_message))
        
        # Method 5: Try with data ID instead of webhook ID (Render might mix these up)
        if 'data' in payload_json and 'id' in payload_json['data']:
            data_id = payload_json['data']['id']
            data_id_message = f"{data_id}.{timestamp_header}.{compact_payload}.{signing_secret}"
            signature_methods.append(("Data ID", data_id_message))
    except:
        # If JSON parsing fails, we've already added the standard method
        pass
    
    # Try all methods
    for method_name, message in signature_methods:
        computed_sig = hmac.new(
            signing_secret.encode('utf-8'),
            message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        computed_sig_b64 = base64.b64encode(computed_sig).decode('utf-8')
        
        logger.debug(f"Method: {method_name}")
        logger.debug(f"Message: {message[:50]}...")
        logger.debug(f"Computed sig: {computed_sig_b64[:16]}...")
        logger.debug(f"Received sig: {received_sig[:16]}...")
        
        if hmac.compare_digest(received_sig, computed_sig_b64):
            logger.info(f"Signature validated using {method_name} method")
            return True
    
    # Emergency fallback - accept if bypass is configured
    fallback_env_vars = ["ALLOW_UNSIGNED_WEBHOOKS", "BYPASS_WEBHOOK_VALIDATION", "WEBHOOK_VALIDATION_BYPASS"]
    for var in fallback_env_vars:
        if os.environ.get(var) == "true":
            logger.warning(f"⚠️ Signature validation bypassed using {var}=true")
            return True
    
    # All methods failed
    logger.warning("All signature validation methods failed")
    return False

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


@webhook_bp.route("/webhooks/deploy-direct", methods=["POST"])
def handle_deploy_webhook_direct():
    """Direct webhook handler that skips signature validation.
    Only available when explicitly enabled via environment variable.
    """
    if os.environ.get("ENABLE_DIRECT_WEBHOOK") != "true":
        return jsonify({"status": "error", "message": "Direct webhook endpoint disabled"}), 403
        
    # Get request data
    payload = request.get_data()
    logger.warning("⚠️ Using DIRECT webhook endpoint without signature validation!")
    
    # Parse the payload
    try:
        data = json.loads(payload)
        event_type = data.get("type")
        logger.info(f"Processing direct webhook event type: {event_type}")
        
        # Handle deploy_ended event
        if event_type == "deploy_ended":
            logger.info("Detected deploy_ended event, triggering database migration")
            threading.Thread(target=run_migration_in_thread).start()
            return jsonify({"status": "success", "message": "Migration triggered"}), 200
            
        # Return success for other event types
        return jsonify({
            "status": "success", 
            "message": f"Received {event_type} event via direct endpoint"
        }), 200
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload in direct webhook")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception as e:
        logger.exception(f"Error processing direct webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
    
    # Get raw request data
    payload_str = payload if isinstance(payload, str) else payload.decode('utf-8')
    logger.debug(f"Raw payload: {payload_str[:200]}...")
    
    # Emergency bypass mode - always accept
    if os.environ.get("FORCE_ACCEPT_WEBHOOKS") == "true":
        logger.warning("⚠️ FORCE_ACCEPT_WEBHOOKS=true, accepting webhook without validation")
        # Process without validation
        trigger_migration = True
    # Normal validation mode
    elif not validate_signature(payload, signature, timestamp, webhook_id):
        # Validation failed, but still try to handle some special cases
        logger.warning("Invalid webhook signature")
        logger.info(f"Signature: {signature}, Timestamp: {timestamp}, ID: {webhook_id}")
        
        # Check if this is from our own test script
        if os.environ.get("BYPASS_WEBHOOK_VALIDATION") == "true":
            logger.warning("⚠️ BYPASS_WEBHOOK_VALIDATION=true, continuing despite invalid signature")
            trigger_migration = True
        # Normal failure case
        else:
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
                # Log first and last 3 chars of secret for verification (safe enough)
                for var in configured_vars:
                    secret = os.environ.get(var)
                    if secret and len(secret) > 6:
                        logger.debug(f"{var} hash: {hashlib.sha256(secret.encode()).hexdigest()[:8]}")
            else:
                logger.warning("No webhook secret environment variables set")
                
            return jsonify({"status": "error", "message": error_message}), 401
    else:
        # Validation succeeded
        trigger_migration = True
    
    # If we got here, either validation succeeded or bypass is enabled
    try:
        data = json.loads(payload_str)
        event_type = data.get("type")
        logger.info(f"Processing webhook event type: {event_type}")
        
        # Check if this is a deploy_ended event
        if event_type == "deploy_ended" and trigger_migration:
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
    
    bypass_vars = [
        "ALLOW_UNSIGNED_WEBHOOKS",
        "BYPASS_WEBHOOK_VALIDATION",
        "WEBHOOK_VALIDATION_BYPASS",
        "FORCE_ACCEPT_WEBHOOKS",
        "ENABLE_DIRECT_WEBHOOK"
    ]
    
    bypass_config = {var: os.environ.get(var) == "true" for var in bypass_vars}
    
    return jsonify({
        "status": "success",
        "message": "Webhook endpoint is configured correctly",
        "environment": {
            "debug": current_app.config.get("DEBUG", False),
            "test": current_app.config.get("TESTING", False),
            "webhook_secret_configured": signing_secret is not None,
            "configured_secret_vars": configured_vars,
            "bypass_config": bypass_config,
            "direct_endpoint_available": "/webhooks/deploy-direct"
        }
    })

@webhook_bp.route("/webhooks/debug", methods=["POST"])
def debug_webhook():
    """
    Debug endpoint for webhook troubleshooting.
    This endpoint logs all headers and request data for diagnostic purposes.
    Only enabled in debug mode or when explicitly allowed.
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

@webhook_bp.route("/webhooks/force-migration", methods=["POST"])
def force_migration():
    """
    Force a migration to run.
    This endpoint is protected by a special token to prevent unauthorized access.
    """
    expected_token = os.environ.get("MIGRATION_FORCE_TOKEN")
    if not expected_token:
        return jsonify({"status": "error", "message": "Force migration not configured"}), 403
        
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"status": "error", "message": "Missing or invalid Authorization header"}), 401
        
    token = auth_header[7:]  # Remove "Bearer " prefix
    if not hmac.compare_digest(token, expected_token):
        return jsonify({"status": "error", "message": "Invalid token"}), 401
        
    # Run migration in a thread
    logger.warning("⚠️ Manually triggered migration via force-migration endpoint")
    threading.Thread(target=run_migration_in_thread).start()
    
    return jsonify({
        "status": "success",
        "message": "Migration manually triggered"
    })