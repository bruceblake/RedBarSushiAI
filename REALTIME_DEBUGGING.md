# OpenAI Realtime API Debugging Guide

## Common Issues

1. **Authentication Failures**
   - **Symptoms**: "couldn't connect" after greeting, 401 status code in logs
   - **Solution**: Verify OPENAI_API_KEY is correct and has permissions for Realtime API
   - **Render Fix**: Update environment variable in Render dashboard > Environment tab

2. **Network/Connectivity Issues**
   - **Symptoms**: Connection failures, timeouts
   - **Solution**: Check network connectivity, firewall rules, proxy settings
   - **Render Fix**: Check if Render's IP addresses need to be allowlisted for OpenAI

3. **Configuration Problems**
   - **Symptoms**: Errors about invalid settings or parameters
   - **Solution**: Verify session.update configuration matches API requirements

4. **WebSocket Connection Issues**
   - **Symptoms**: Initial greeting works but then connection fails
   - **Solution**: Check WebSocket implementation, verify request headers and parameters

## Required Environment Variables

- **OPENAI_API_KEY**: Your OpenAI API key with access to the Realtime API
- **TWILIO_ACCOUNT_SID**: Your Twilio account SID for voice calls
- **TWILIO_AUTH_TOKEN**: Your Twilio auth token for API access
- **TWILIO_PHONE_NUMBER**: The phone number to use for outgoing calls

## Debugging Steps

1. **Check Environment Variables**
   ```bash
   env | grep OPENAI
   env | grep TWILIO
   ```

2. **Enable Enhanced Debugging**
   ```bash
   export LOG_LEVEL=DEBUG
   ```

3. **Check WebSocket Connection**
   - Look for "Successfully connected to OpenAI Realtime API" in logs
   - Watch for authentication errors (401) or other status codes

4. **Monitor Event Flow**
   - Verify session.update is sent and accepted
   - Check for successful tool registrations
   - Look for event handling of transcripts and audio

5. **Check API Key Permissions**
   - Verify your API key has access to the Realtime API features
   - Test key with a simple curl command to API

## Log Analysis

Enhanced logs will show these key events:

- **Connection attempts**: "Attempting to connect to OpenAI Realtime API"
- **Authentication status**: "Successfully connected" or "Authentication failed"
- **Session initialization**: "Initializing OpenAI Realtime session"
- **Transcription**: "Final transcript: [text]"
- **Tool execution**: "Sending function output for [function]"
- **Errors**: "OpenAI API Error: [message]"

## Testing on Render vs. Local

It's often helpful to test in both environments to isolate the issue:

1. **Local Testing with Docker**:
   - Run `./run_docker_fixed.sh` with enhanced debugging
   - Use ngrok to expose local server to Twilio
   - Make test calls and analyze logs

2. **Render Testing**:
   - Verify environment variables are set correctly
   - Enable DEBUG log level in Render environment
   - Deploy with enhanced debugging enabled
   - Check Render logs for connection issues

If it works in one environment but not the other, focus on the differences (network, environment variables, configuration).

## Common Error Messages and Solutions

### "Authentication failed: Invalid API key"
- **Issue**: Your API key is incorrect or expired
- **Solution**: Generate a new API key in OpenAI dashboard

### "Connection failed with status 403"
- **Issue**: Your account doesn't have access to the Realtime API
- **Solution**: Verify your OpenAI account has Realtime API access

### "Unknown error" or "Internal server error"
- **Issue**: OpenAI service issue or malformed request
- **Solution**: Check request format, verify API is operational

## Restoring Original Files

To restore the original implementation:

```bash
cp app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py
cp app/api/voice_async.py.bak app/api/voice_async.py
```