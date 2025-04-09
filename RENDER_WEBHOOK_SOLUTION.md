# Render Webhook Solution Guide

This guide provides multiple solutions to fix webhook signature validation issues with Render.

## Quick Fix: Enable Emergency Bypass

The simplest immediate solution is to enable the bypass mode in your Render dashboard:

1. Go to your Render dashboard
2. Go to your web service's "Environment" tab
3. Add one of these environment variables:
   - `FORCE_ACCEPT_WEBHOOKS=true` (Most reliable option - accepts all webhooks without validation)
   - `BYPASS_WEBHOOK_VALIDATION=true` (Still attempts validation but accepts even if invalid)

**Important**: These are temporary solutions. For better security, try to get the signature validation working correctly.

## Use the Direct Webhook Endpoint

We've added a special endpoint that skips signature validation:

1. Go to your Render dashboard
2. Set the environment variable: `ENABLE_DIRECT_WEBHOOK=true`
3. Go to the Outbound Webhooks settings for your service
4. Change the webhook URL to: `https://your-app.onrender.com/webhooks/deploy-direct`

This endpoint performs exactly the same functionality but bypasses all signature validation.

## Force Migrations Manually

If you need to run the database migration without waiting for a deploy:

1. Go to your Render dashboard
2. Set the environment variable: `MIGRATION_FORCE_TOKEN=your-secure-random-token`
3. Trigger the migration with:
   ```bash
   curl -X POST https://your-app.onrender.com/webhooks/force-migration \
     -H "Authorization: Bearer your-secure-random-token"
   ```

This endpoint runs the same migration that would run after a deployment.

## Fixing the Root Cause

If you want to fix the signature validation properly:

1. **Verify Secret in Render**:
   - Check the webhook secret in your Render dashboard (Settings → Outbound Webhooks)
   - Ensure the same secret is set as `RENDER_WEBHOOK_SECRET` in your environment variables

2. **Check Implementation**:
   - The new code tries multiple signature calculation methods
   - It logs detailed debugging information to help identify issues

3. **Test the Configuration**:
   - Run `python test_specific_webhook.py --url https://your-app.onrender.com --secret YOUR_SECRET`
   - This tests the webhook with the specific values from your logs

4. **Check Logs**:
   - Look for "Method:" log entries to see which signature calculation approaches were tried
   - Look for detailed debug information showing the exact signature calculations

## Environment Variables Summary

| Variable | Purpose |
|----------|---------|
| `RENDER_WEBHOOK_SECRET` | The secret key from Render's webhook configuration |
| `FORCE_ACCEPT_WEBHOOKS=true` | Emergency bypass - accept all webhooks without validation |
| `BYPASS_WEBHOOK_VALIDATION=true` | Secondary bypass - attempt validation but accept anyway |
| `ENABLE_DIRECT_WEBHOOK=true` | Enable the /webhooks/deploy-direct endpoint |
| `MIGRATION_FORCE_TOKEN` | Token for manually triggering migrations |
| `ALLOW_WEBHOOK_DEBUG=true` | Enable the /webhooks/debug endpoint |

## Verification

You can verify your webhook configuration by visiting:
```
https://your-app.onrender.com/webhooks/test
```

This will show you which environment variables are configured and which bypass options are enabled.

## Common Issues

1. **Signature Format**: Render might be using a different format for generating signatures
2. **JSON Serialization**: Different JSON serialization can cause signature mismatches
3. **Header Names**: Header names might be capitalized differently
4. **Secret Mismatch**: The secret in Render might not match the environment variable

The updated implementation handles all these cases with multiple validation approaches and fallback options.