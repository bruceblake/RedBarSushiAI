# OpenAI API Key Configuration Instructions

## API Key Issue Detected!

Your RedBarSushiAI application is currently using a **dummy/test API key** (`sk-mytestapikey`) which is causing the OpenAI Realtime API to reject connections after the initial handshake.

## Fixing the API Key Issue

1. **Locate your environment file**:
   ```bash
   # Use our verification script to check all environment files
   python verify_env_variables.py
   ```

2. **Update the API key in your environment file**:
   - Edit `.env.development` for local Docker development
   - Update API key format: `OPENAI_API_KEY=sk-your_actual_api_key`
   - Ensure there are no quotes around the key value

3. **Verify Docker environment file mounting**:
   - Check your `docker-compose.yml` or `docker-compose.override.yml` file
   - Ensure the `env_file` directive points to the correct file:
     ```yaml
     services:
       app-dev:
         env_file:
           - ./.env.development  # Check this path is correct
     ```

4. **Rebuild and restart Docker**:
   ```bash
   ./force_rebuild.sh && ./restart_docker.sh
   ```

5. **For deployment environments**:
   - Update the API key in your Render dashboard
   - Go to the Environment section for your service
   - Update the `OPENAI_API_KEY` value with your actual API key

## Obtaining a Valid OpenAI API Key

1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Log in to your OpenAI account
3. Create a new API key with appropriate permissions
4. Ensure your account has access to the correct models:
   - `gpt-4o-realtime-preview-2024-10-01` (or your configured model)

## Verifying the Fix

After updating your API key, test the connection:

```bash
# Run our test script to verify OpenAI connection
python test_realtime_client.py
```

Then make a real voice call to test end-to-end functionality.

## Understanding the Logs

When using a valid API key, you should see these log events:

```
🟢 [CA...] SUCCESSFULLY CONNECTED to OpenAI Realtime API
🟢 [CA...] Session configuration successful
🟢 [CA...] Successfully sent greeting for TTS
```

With an invalid key, you'll see:

```
🔴 [CA...] RECEIVED ERROR EVENT FROM OPENAI: {"type":"error",...,"code":"invalid_api_key",...}
🔴 [CA...] INVALID API KEY ERROR FROM OPENAI - Signaling stop and will close connection
```

## Security Best Practices

1. **Never commit API keys to git**:
   - Keep keys in `.env.development` which should be in `.gitignore`
   - Use environment variable management for production

2. **Limit API key permissions**:
   - Grant only the minimum required permissions
   - Set usage limits in the OpenAI dashboard

3. **Rotate keys periodically**:
   - Create new keys and deprecate old ones regularly
   - Update all deployment environments when rotating keys