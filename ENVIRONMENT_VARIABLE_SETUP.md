# Environment Variable Setup for RedBarSushiAI

This document provides instructions for properly setting up environment variables for the RedBarSushiAI project, both locally and in Render.

## Critical Environment Variables

The following environment variables are **required** for full functionality:

| Variable | Purpose | Example Value | Status |
|----------|---------|---------------|--------|
| `OPENAI_API_KEY` | **CRITICAL**: Authenticates with OpenAI for Realtime API | `sk-abcd1234...` | ⚠️ Currently using dummy key |
| `TWILIO_ACCOUNT_SID` | Authenticates with Twilio | `ACb8391ed...` | ✅ Set in .env.development |
| `TWILIO_AUTH_TOKEN` | Authenticates with Twilio | `8bbdc0c60...` | ✅ Set in .env.development |
| `TWILIO_PHONE_NUMBER` | Phone number for outbound calls | `+17036467799` | ✅ Set in .env.development |
| `STRIPE_API_KEY` | Used for payment processing | `sk_test_...` | ❌ Missing or needs update |

## Local Development Setup

For local Docker development:

1. Update `.env.development` with your real API keys:

```bash
# Current values in .env.development that need updating
OPENAI_API_KEY=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
STRIPE_API_KEY=dummy-key-for-development  # Add this if missing
```

2. Start Docker using the environment-aware setup:

```bash
./docker_env_setup.sh
```

## Render Deployment Setup

For staging/production deployment on Render:

1. Go to the Render dashboard
2. Select your RedBarSushiAI service
3. Navigate to "Environment" tab
4. Add or update these environment variables:
   - `OPENAI_API_KEY`=sk-... (your real OpenAI API key)
   - `TWILIO_ACCOUNT_SID`=AC... (your Twilio Account SID)
   - `TWILIO_AUTH_TOKEN`=... (your Twilio Auth Token)
   - `TWILIO_PHONE_NUMBER`=+1... (your Twilio phone number)
   - `STRIPE_API_KEY`=sk_... (your Stripe API key)
5. Click "Save Changes"

## Getting Valid API Keys

- **OpenAI API Key**: Get from [OpenAI API Keys](https://platform.openai.com/account/api-keys)
  - Ensure your account has access to `gpt-4o-realtime-preview-2024-10-01` model
- **Twilio Credentials**: Get from [Twilio Console](https://console.twilio.com/)
- **Stripe API Key**: Get from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)

## Verifying Configuration

To verify your environment variables in Docker:

```bash
# Check environment variables in the app container
docker exec redbarsushi-app env | grep -v PATH | sort

# Test OpenAI connection (after fixing process_messages)
# Create a quick test script and run it in the container
```

## Troubleshooting

If you see error messages like:

- `Error initializing Twilio client: name 'TWILIO_ACCOUNT_SID' is not defined`
- `Incorrect API key provided: sk-mytes***ikey`

These indicate that your environment variables either aren't being loaded or contain invalid/dummy values.

The most common issue is using a placeholder API key like `sk-mytestapikey` which OpenAI will reject.

## Next Steps After Fixing Environment Variables

1. Deploy the process_messages fix:
   ```bash
   ./deploy_process_messages_fix.sh
   ```

2. Test with a real API key in your local Docker environment:
   ```bash
   ./docker_env_setup.sh --clean
   ```

3. Make a test call through Twilio