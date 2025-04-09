# Render Webhook Configuration Guide

This guide explains how to set up and troubleshoot Render webhooks with this application.

## Setting Up Webhooks in Render

1. **Create a Webhook in Render Dashboard**:
   - Go to your Render dashboard
   - Select the service you want to set up webhooks for
   - Go to the "Settings" tab
   - Find the "Outbound Webhooks" section
   - Click "Add Webhook"

2. **Configure the Webhook**:
   - **Event**: Choose "Deploy Succeeded" (or another event)
   - **Payload URL**: Enter your application's webhook URL (e.g., `https://your-app.onrender.com/webhooks/deploy`)
   - **Secret**: Generate a secure random string (you can use `openssl rand -hex 32`)
   - Save the webhook configuration

3. **Set Environment Variable**:
   - Go to your service's "Environment" tab
   - Add a new environment variable:
     - Name: `RENDER_WEBHOOK_SECRET`
     - Value: The secret you generated for the webhook
   - Click "Save Changes" and redeploy your service

## Troubleshooting Webhook Signature Issues

If you're seeing "Invalid signature" errors, follow these steps:

### 1. Verify Environment Variables

Ensure the webhook secret is properly configured:

```bash
# Check if the RENDER_WEBHOOK_SECRET is set correctly
curl https://your-app.onrender.com/webhooks/test
```

This should return information about your webhook configuration, including whether a secret is configured.

### 2. Verify Header Format

Render sends webhook signatures with specific headers:
- `webhook-id`: A unique ID for the webhook event
- `webhook-timestamp`: The Unix timestamp when the webhook was sent
- `webhook-signature`: The signature in format `v1,base64_signature`

Our application checks for these headers in various formats (lowercase, uppercase, with x- prefix).

### 3. Test with Debug Tool

This repository includes a tool to help test webhook configurations:

```bash
# Run the testing tool
python test_render_webhook.py --url https://your-app.onrender.com --secret YOUR_SECRET

# Try different header formats
python test_render_webhook.py --url https://your-app.onrender.com --secret YOUR_SECRET --header-format uppercase
python test_render_webhook.py --url https://your-app.onrender.com --secret YOUR_SECRET --header-format x-prefix

# Use debug endpoint to see raw headers and payload
python test_render_webhook.py --url https://your-app.onrender.com --debug
```

### 4. Enable Debug Logging

To enable more detailed logging:

```bash
# Set environment variable to enable debug logs
export FLASK_DEBUG=1
export ALLOW_WEBHOOK_DEBUG=true

# Or set in Render environment variables
FLASK_DEBUG=1
ALLOW_WEBHOOK_DEBUG=true
```

### 5. Bypass Signature Validation (Development Only)

For testing purposes only, you can temporarily bypass signature validation:

```bash
# Set environment variable to bypass validation (NEVER in production)
export ALLOW_UNSIGNED_WEBHOOKS=true
```

## How Render Webhook Signatures Work

Render uses HMAC-SHA256 for webhook signature validation with this specific format:

1. Render sends these HTTP headers with each webhook:
   - `Webhook-Id`: A unique ID for the webhook event (e.g., `evt-cvqsus7gi27c73f8sqmg`)
   - `Webhook-Timestamp`: Unix timestamp when the webhook was sent
   - `Webhook-Signature`: Format `v1,base64_signature`

2. The signature is created using this exact format:
   ```
   message = webhook_id + "." + timestamp + "." + json_body + "." + webhook_secret
   signature = HMAC-SHA256(message, webhook_secret)
   base64_signature = Base64(signature)
   ```

3. Important details:
   - The JSON body must be exactly the same as what Render sends (no extra whitespace)
   - Headers may have different casing (our app checks multiple variations)
   - The webhook secret must be exactly the same on both sides
   - The signature uses the raw message, not a hashed version

The signature validation code is in `app/routes/webhook.py` in the `validate_signature` function.

## Common Issues and Solutions

1. **Missing headers**: Ensure Render is sending all required headers.
2. **Different header formatting**: We now check for multiple header formats.
3. **Incorrect secret**: Verify that the secret in Render matches your environment variable.
4. **Whitespace issues**: Ensure there's no whitespace in the secret.
5. **Timestamp tolerance**: Webhooks older than 5 minutes are rejected.

## Getting Help

If you're still having issues:

1. Check the application logs for detailed error messages
2. Use the `/webhooks/debug` endpoint to see raw headers and payload
3. Try the test tool with different header formats
4. Make sure your server clock is synchronized (NTP)