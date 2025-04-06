# Webhook URL Fix - RedBarSushiAI

## Issue
The webhook registration and activation was not using the proper base URL (`https://redbarsushiai.onrender.com`), causing webhook endpoints to fail.

## Changes Made

1. **Fixed BASE_URL Configuration**
   - Added a default local development BASE_URL in `app/config.py`
   - The configuration now properly sets BASE_URL in all environments

2. **Updated Webhook URL Generation**
   - Modified `get_location_webhook_urls()` in `app/utils/deliverect.py` to use the BASE_URL from the configuration
   - Removed hardcoded base URLs from webhook URL generation
   - Added proper error handling and logging

3. **Improved /register Endpoint**
   - Updated the `/register` endpoint in `app/routes/order.py` to directly use BASE_URL
   - Added logging of registered URLs for debugging

## Testing

A test script `test_webhook_urls.py` has been added to verify webhook URL generation works correctly. You can run it with:

```bash
python test_webhook_urls.py
```

## Configuring BASE_URL

The BASE_URL is set automatically based on these rules:

1. If running on Render (detected via environment variables):
   - Uses the value of `BASE_URL` environment variable if set
   - Defaults to `https://redbarsushiai.onrender.com` if not set

2. Otherwise (local development):
   - Uses the value of `BASE_URL` environment variable if set
   - Defaults to `http://localhost:5000` if not set

To override the BASE_URL, set the environment variable before starting the application:

```bash
export BASE_URL="https://your-custom-domain.com"
python run.py
```

## Verifying the Fix

1. When the `/register` or webhook activation endpoints are called, check the logs for:
   - "Registered webhooks with base URL: ..."
   
2. Ensure all webhook URLs returned contain the correct base URL and don't include any hardcoded URLs

## Additional Suggestions

1. **Webhook Testing Endpoint**:
   Consider adding a webhook testing endpoint that will send a test event to your registered webhook to verify it works end-to-end.

2. **Monitoring**:
   Set up monitoring for webhook failures to detect issues early.

3. **Webhook Configuration UI**:
   A simple UI for configuring and testing webhooks could make debugging easier.