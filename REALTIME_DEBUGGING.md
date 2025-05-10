# Debugging OpenAI Realtime API Issues in RedBarSushiAI

This document provides a guide for debugging OpenAI Realtime API connection issues for RedBarSushiAI voice ordering.

## Common Issues

The most common issue is the system greeting the user but then saying "it couldn't connect." This typically indicates:

1. The initial TTS for the greeting worked
2. The persistent WebSocket connection to OpenAI failed to establish or authenticate 
3. The most common cause is missing environment variables

## Required Environment Variables

To ensure proper functioning, these variables MUST be set:

- `OPENAI_API_KEY` - Your OpenAI API key (required for Realtime API)
- `TWILIO_ACCOUNT_SID` - Your Twilio account SID
- `TWILIO_AUTH_TOKEN` - Your Twilio auth token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number

## Using the Debug Script

We've provided a debugging script to help diagnose these issues:

```bash
# Run the debug script
./realtime_debug.sh
```

This script does the following:

1. Checks for critical environment variables
2. Enhances logging for the OpenAI Realtime client
3. Sets up additional voice API debugging
4. Provides guidance on viewing logs

## Checking Logs

After running the debug script, look for these key log files:

- `logs/realtime_audio.log` - OpenAI Realtime API interactions
- `logs/voice_debug.log` - Voice API call details
- `logs/app.log` - General application logs

Key things to look for:

### Environment Variable Issues
```
[ERROR] OPENAI_API_KEY is not configured. Cannot connect to OpenAI Realtime API.
```

### Authentication Failures
```
[ERROR] Failed to connect to OpenAI: Invalid status code 401.
[ERROR] Authentication failed (401). Check your OPENAI_API_KEY.
```

### API Connection Issues
```
[ERROR] Timeout connecting to OpenAI Realtime API.
```

### WebSocket Errors
```
[ERROR] WebSocket connection closed with error: Code 1002, Reason: Protocol error
```

## Steps to Fix

1. **Environment Variables**: Ensure all required environment variables are set correctly
   - In Render: Set these in your service's environment variables dashboard
   - In Docker: Ensure they're in your `.env.development` file

2. **API Key Validation**: Verify your OpenAI API key is valid and has access to Realtime API
   - Ensure it starts with "sk-"
   - Check that it has permission for the gpt-4o-realtime-preview-2024-10-01 model

3. **Network Issues**: If authentication is successful but connections fail
   - Check for firewall or proxy issues
   - Verify outbound connections to api.openai.com are allowed

4. **Cleanup After Debugging**:
   ```bash
   # Restore original files when done debugging
   mv app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py
   rm app/api/voice_debug.py
   ```

## Deploying Fixes to Render

For Render deployment:

1. Ensure environment variables are set in Render dashboard
2. Update deployment scripts:
   ```bash
   # Add OpenAI Realtime client fixes to fix_render_deploy.sh
   ./fix_render_deploy.sh
   ```

## Testing in Docker with ngrok

For local testing with Twilio:

1. Configure environment variables in `.env.development`
2. Start Docker with ngrok:
   ```bash
   ./start_docker_with_ngrok.sh
   ```
3. Update your Twilio webhook URLs to the ngrok URL

## Getting Help

If issues persist after following these steps:

1. Collect the logs mentioned above
2. Note the exact error messages and when they occur
3. Contact support with these details for further assistance