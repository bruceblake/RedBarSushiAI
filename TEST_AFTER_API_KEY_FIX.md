# Testing Instructions After API Key Fix

After updating your OpenAI API key as described in the `API_KEY_INSTRUCTIONS.md` file, follow these steps to verify that the WebSocket fixes and API key are working correctly.

## 1. Test the OpenAI Realtime Client

Run the test script to verify the OpenAI Realtime client can successfully connect and handle API requests:

```bash
python test_realtime_client.py
```

You should see output indicating:
- Successful client initialization
- Successful WebSocket connection to OpenAI
- No `AttributeError` about missing `request_response` method
- No `RuntimeError` about `cannot call recv while another coroutine is already waiting`

## 2. Local Testing with Docker and ngrok

1. **Start Docker environment with rebuild**:
   ```bash
   ./force_rebuild.sh && ./restart_docker.sh
   ```

2. **Start ngrok for public URL tunneling**:
   ```bash
   ./setup_ngrok.sh
   ```
   Note the public URL displayed by ngrok. You'll use this to configure Twilio.

3. **Update Twilio webhook URL**:
   - Log in to your Twilio account dashboard
   - Go to the Phone Numbers section
   - Select your Twilio phone number
   - Under Voice & Fax > A Call Comes In
   - Update the webhook URL to: `https://YOUR-NGROK-URL/voice/webhook`
   - Save changes

4. **Monitor application logs**:
   ```bash
   docker logs -f redbarsushi-app-1
   ```

5. **Make a test call**:
   - Dial your Twilio phone number
   - Listen for the greeting message
   - Try to interact with the voice assistant

## 3. What to Look For in Logs

### Success Indicators

1. **Successful Twilio WebSocket Connection**:
   ```
   🟢 [CA...] WebSocket acceptance SUCCESSFUL
   🟢 [CA...] WebSocket connection FULLY ESTABLISHED
   ```

2. **Successful OpenAI Connection**:
   ```
   🟢 [CA...] SUCCESSFULLY CONNECTED to OpenAI Realtime API
   🟢 [CA...] Session configuration sent successfully
   ```

3. **Successful TTS Request**:
   ```
   🔄 [CA...] Sending greeting for TTS
   🟢 [CA...] Successfully sent greeting for TTS
   ```

4. **Audio Exchange**:
   ```
   Received audio event: response.audio.delta
   Forwarding audio data to Twilio
   ```

5. **Transcript Processing**:
   ```
   🟢 [CA...] RECEIVED TRANSCRIPT: [user's speech]
   ```

### Error States to Monitor

1. **API Key Problems**:
   - Error events with code `invalid_api_key`
   - Connection closed by OpenAI with reason containing "invalid_api_key"

2. **WebSocket Issues**:
   - `RuntimeError: cannot call recv while another coroutine is already waiting`
   - `WebSocket CONNECTION CLOSED WITH ERROR`

3. **Task Management Issues**:
   - Look for proper task cancellation messages when connections close
   - Check for graceful resource cleanup in the logs

## 4. Debugging Issues

If you encounter problems:

1. **Check API Key**:
   - Verify your API key is valid and has access to the required models
   - Run `python verify_env_variables.py` to check environment configuration

2. **Check WebSocket Stability**:
   - Look for connection closure messages and their reasons
   - Check if the OpenAI connection is established but then immediately closed

3. **Verify Audio Flow**:
   - Check if audio is being forwarded from Twilio to OpenAI
   - Check if OpenAI is generating TTS audio that gets sent back to Twilio

## 5. Next Steps

Once you confirm the voice system is working with a test call:

1. **Deploy to Staging**:
   - Push the changes to your staging branch
   - Update the API key in your Render environment variables
   - Test with a call to your staging deployment

2. **Deploy to Production**:
   - Only after successful staging tests
   - Update the API key in your production environment
   - Monitor logs for any issues

## Support

If you continue to experience issues:

1. Check the `FIX_SUMMARY.md` file for detailed explanations of the fixes
2. Review the `WEBSOCKET_FIX_CHANGES.md` file for code changes
3. Ensure your OpenAI account has proper access to the Realtime API and models