# RedBarSushiAI Environment Setup Checklist

## Critical Environment Variables

These variables MUST be set in your Render dashboard for the application to function properly:

- [ ] `OPENAI_API_KEY` - Starts with `sk-` (Required for voice functionality)
- [ ] `TWILIO_ACCOUNT_SID` - Starts with `AC` (Required for Twilio integration)
- [ ] `TWILIO_AUTH_TOKEN` - Twilio authentication token
- [ ] `TWILIO_PHONE_NUMBER` - Formatted as `+1XXXXXXXXXX`
- [ ] `DATABASE_URL` - PostgreSQL connection string (starts with `postgresql://`)
- [ ] `REDIS_URL` - Redis connection string (starts with `redis://`)

## Important Environment Variables

These variables provide additional functionality:

- [ ] `STRIPE_API_KEY` - Starts with `sk_` (for payment processing)
- [ ] `DELIVERECT_API_KEY` - For Deliverect integration
- [ ] `DELIVERECT_CLIENT_ID` - For Deliverect authentication
- [ ] `DELIVERECT_CLIENT_SECRET` - For Deliverect authentication
- [ ] `BASE_URL` - Your application's base URL (e.g., `https://redbarsushiai-staging.onrender.com`)

## Setting Environment Variables in Render

1. Go to your [Render Dashboard](https://dashboard.render.com/)
2. Select your RedBarSushiAI service
3. Click on the "Environment" tab
4. Add or update each variable
5. Click "Save Changes"
6. Deploy the application again

## Verifying Environment Variables

After deployment, verify your environment variables are properly set:

1. SSH into your Render instance or check the logs
2. Run `python check_env_variables.py` to see which variables are properly configured
3. Check logs for any `name 'VARIABLE_NAME' is not defined` errors

## Setting Up Enhanced Debugging

To set up enhanced debugging for OpenAI Realtime API:

1. Upload the debugging files to your Render instance:
   - `check_env_variables.py`
   - `enhance_openai_client.py`
   - `render_debug_setup.sh`
   - `app/utils/enhanced_realtime_audio_async.py`

2. SSH into your Render instance
3. Run `./render_debug_setup.sh`
4. Make a test call to your Twilio number
5. Check logs for detailed connection information

## Debugging OpenAI Realtime Connection

Look for these key log patterns:

- Connection attempt: `[call_sid] Attempting to connect to OpenAI Realtime API...`
- Success: `[call_sid] Successfully connected to OpenAI Realtime API`
- Auth failure: `[call_sid] Authentication failed: Invalid API key (status 401)`
- General failure: `[call_sid] Failed to connect to OpenAI Realtime API: [error]`

If the authentication fails with a 401 status, your OPENAI_API_KEY is invalid or expired.

## After Setting Environment Variables

Once you've set all environment variables:

1. Redeploy your application
2. Make a test call to your Twilio number
3. Check logs for any remaining errors
4. Verify the application connects to OpenAI Realtime API successfully

Remember to use the enhanced debugging tools to get detailed information about any connection issues.