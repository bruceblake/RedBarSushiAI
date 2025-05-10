# Critical Debugging for OpenAI Connection Issues

## Overview

This guide provides instructions for implementing critical-level debugging to troubleshoot the "couldn't connect" issue occurring after the initial greeting in voice calls.

## The Issue

The application successfully:
- Starts up without crashes
- Handles incoming HTTP requests
- Generates TwiML for Twilio
- Plays the initial greeting

But then fails with "couldn't connect" message, likely due to the OpenAI Realtime API connection failing.

## Debugging Steps

### 1. Force Detailed Logging

The `force_debug_logging.py` script will modify several files to add CRITICAL level logging specifically focused on the OpenAI connection process:

```bash
python force_debug_logging.py
```

This script makes the following changes:

- **app/main.py**: Forces all loggers to DEBUG level
- **app/utils/realtime_audio_async.py**: Adds critical logging to the `connect()` method
- **app/api/voice_async.py**: Adds detailed logging around OpenAI connection attempts
- **app/force_settings.py**: Creates a module to check critical environment variables

### 2. Verify Environment Variables in Render

Go to your Render dashboard and ensure these variables are set correctly:

- **OPENAI_API_KEY** - Most critical, must start with "sk-"
- **TWILIO_ACCOUNT_SID** - Must start with "AC"
- **TWILIO_AUTH_TOKEN** 
- **TWILIO_PHONE_NUMBER**

To verify the OPENAI_API_KEY value without exposing it fully:
1. Copy the value from Render dashboard
2. Check that it starts with "sk-"
3. Verify the key is active in your OpenAI account dashboard
4. Ensure there are no leading/trailing spaces

### 3. Deploy with Enhanced Logging

After making these changes:

1. Commit and push the changes
2. Deploy to Render
3. Make a test call to your Twilio number
4. Immediately check the logs in Render dashboard

### 4. Log Analysis

Look for these specific log patterns:

```
[CRITICAL] !!! OpenAIRealtimeClient.connect() ENTERED. API Key configured: NO - THIS IS THE PROBLEM!
```
This indicates the OPENAI_API_KEY environment variable is not set or not accessible.

```
[CRITICAL] CRITICAL: OpenAI Connect Failed: Invalid status 401. API Key used: True
```
This indicates the OPENAI_API_KEY is set but invalid (wrong key, expired, etc.).

```
[CRITICAL] WS Handler: !!! RESULT of openai_client_instance.connect(): False
[CRITICAL] WS Handler: !!! OpenAI CONNECTION FAILED - This is where 'couldn't connect' message likely originates
```
This confirms the location where the "couldn't connect" message is generated.

### 5. Fix Based on Logs

Based on the specific log messages you see:

- **If API Key is missing**: Update OPENAI_API_KEY in Render environment variables
- **If API Key is invalid (401)**: Generate a new API key in OpenAI dashboard and update in Render
- **If other WebSocket error**: Check error details for network/firewall issues

## Restoring Original Files

After debugging is complete, restore the original files:

```bash
cp app/main.py.bak app/main.py
cp app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py
cp app/api/voice_async.py.bak app/api/voice_async.py
rm app/force_settings.py
```

## Additional Environment Variable Issues

Once the OpenAI connection is working, also set these variables in Render to resolve remaining warnings:

- **TWILIO_ACCOUNT_SID**
- **TWILIO_AUTH_TOKEN**
- **TWILIO_PHONE_NUMBER**
- **STRIPE_API_KEY**

These will resolve the warnings in the logs:
```
Error parsing Twilio version: name 'TWILIO_ACCOUNT_SID' is not defined
Error initializing Twilio client: name 'TWILIO_ACCOUNT_SID' is not defined
Error initializing Stripe client: name 'STRIPE_API_KEY' is not defined
```

## Important Notes

- The enhanced logging is deliberately verbose and should only be used temporarily for debugging
- Some log messages may contain sensitive information (partial API keys), so remove them after debugging
- Restart the application after updating environment variables in Render
- The primary focus is to determine if the issue is with OPENAI_API_KEY