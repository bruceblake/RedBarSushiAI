# Render CLI and API Guide for RedBarSushiAI

This document provides instructions on how to use both the Render CLI and Render API with the RedBarSushiAI application deployment.

## Setup

### 1. Install the Render CLI

#### On macOS with Homebrew:
```bash
brew update
brew install render
```

#### On Linux/macOS without Homebrew (Direct Download):
```bash
curl -L https://github.com/render-oss/cli/releases/download/v1.1.0/cli_1.1.0_linux_amd64.zip -o render.zip
unzip render.zip
sudo mv cli_v1.1.0 /usr/local/bin/render
```

### 2. Authenticate

```bash
render login
```

This will:
- Open your browser to authorize the CLI for your account
- Generate a CLI token that's saved locally
- Prompt you to select your active workspace

## Common Commands for RedBarSushiAI

### View All Services and Datastores

```bash
render services
```

### Deploy the Application

```bash
render deploys create YOUR_SERVICE_ID --wait
```

Add `--wait` to block until the deploy completes.

### Check Deployment Status

```bash
render deploys list YOUR_SERVICE_ID
```

### View Application Logs

```bash
render logs YOUR_SERVICE_ID
```

### Accessing PostgreSQL Database

```bash
render psql YOUR_DATABASE_ID
```

This opens a direct psql session to your database, which can be useful for:
- Running the migration script manually via SQL
- Verifying SMS tracking columns were added properly
- Debugging database issues

### SSH into Service

```bash
render ssh YOUR_SERVICE_ID
```

Use this to:
- Run the migration script directly on the server
- Check logs and troubleshoot issues
- Verify environment variables

## Testing Database Migrations on Render

To test or run the SMS tracking migration on Render:

1. SSH into your service:
   ```bash
   render ssh YOUR_SERVICE_ID
   ```

2. Run the migration script:
   ```bash
   python migrate_sms_tracking.py
   ```

3. Verify the migration with psql:
   ```bash
   render psql YOUR_DATABASE_ID
   ```

   Then run this SQL query:
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'order' 
   AND column_name IN ('sms_sid', 'sms_status', 'sms_error_code', 'sms_error_message');
   ```

## Continuous Integration

For CI/CD workflows, use environment variables instead of interactive login:

```bash
export RENDER_API_KEY=your_api_key
render deploys create YOUR_SERVICE_ID --output json --confirm
```

## Troubleshooting

### Authentication Issues
If the CLI token expires, re-authenticate with:
```bash
render login
```

### Database Connection Issues
If having trouble connecting to the database with the migration script:
1. Verify the DATABASE_URL environment variable is set correctly
2. Check that the database service is running:
   ```bash
   render services --output json | grep YOUR_DATABASE_ID
   ```

### Deployment Issues
If a deploy fails, check the logs:
```bash
render deploys list YOUR_SERVICE_ID
# Select the failed deploy
render logs YOUR_SERVICE_ID --deploy DEPLOY_ID
```

## Local Config

The Render CLI stores configuration at:
```
$HOME/.render/cli.yaml
```

You can change this by setting the `RENDER_CLI_CONFIG_PATH` environment variable.

## Using the Render API

In addition to the CLI, you can use the Render REST API to programmatically manage your resources.

### Setup

1. **Create an API Key**
   - Go to your Account Settings in the Render Dashboard
   - Create a new API key
   - Store it securely (it's only displayed once when created)

2. **Authentication**
   - Use Bearer token authentication in all API requests
   - Include your API key in the Authorization header

### Example API Requests

#### List Services
```bash
curl --request GET \
     --url 'https://api.render.com/v1/services?limit=20' \
     --header 'Accept: application/json' \
     --header 'Authorization: Bearer YOUR_API_KEY'
```

#### Trigger a Deploy
```bash
curl --request POST \
     --url 'https://api.render.com/v1/services/YOUR_SERVICE_ID/deploys' \
     --header 'Accept: application/json' \
     --header 'Authorization: Bearer YOUR_API_KEY'
```

#### Get Database Info
```bash
curl --request GET \
     --url 'https://api.render.com/v1/services/YOUR_DATABASE_ID' \
     --header 'Accept: application/json' \
     --header 'Authorization: Bearer YOUR_API_KEY'
```

### API Resources

- **Full API Reference**: [Render API Documentation](https://api-docs.render.com)
- **OpenAPI Spec**: Available at https://api-docs.render.com/openapi/6140fb3daeae351056086186
- **Programming Languages**: The API reference provides examples in multiple languages

## Render Webhooks

Webhooks allow you to set up notifications to external services when specific events occur in your Render services. This is particularly useful for automating workflows, such as triggering deployments or sending notifications when database migrations complete.

### Setting Up Webhooks (Requires Professional Plan or Higher)

1. **Create an HTTPS Endpoint**
   - Set up an endpoint that can receive webhook notifications
   - Endpoint must respond with a 2xx HTTP status code within 15 seconds
   - For testing, you can use a webhook testing tool

2. **Create the Webhook in Render Dashboard**
   - Go to Integrations > Webhooks in the Render Dashboard
   - Provide a name and the URL of your endpoint
   - Select which events will trigger notifications

3. **Implement Validation**
   - Webhook requests include signature headers for validation
   - Use the Standard Webhooks library to validate incoming notifications
   - Keep your signing secret secure

### Useful Webhook Events for RedBarSushiAI

These events are particularly useful for our database migration workflow:

#### Deployment Events
- `deploy_started`: Triggered when a deploy starts
- `deploy_ended`: Triggered when a deploy completes
- `build_ended`: Triggered when a build completes

#### Database Events
- `postgres_available`: Triggered when a Postgres database becomes available
- `postgres_restarted`: Triggered when a Postgres database restarts
- `postgres_backup_completed`: Triggered when a database backup completes

### Example: Automating Database Migrations with Render Webhooks

We've implemented a webhook system that automatically runs our database migration script after successful deployments:

1. The webhook endpoint is already implemented at `/webhooks/deploy`:
   ```python
   @webhook_bp.route("/webhooks/deploy", methods=["POST"])
   def handle_deploy_webhook():
       # Validates the webhook signature
       # If deploy_ended event is received:
       #   Runs migrate_sms_tracking.py in a separate thread
       return jsonify({"status": "success"}), 200
   ```

2. To configure this in Render:
   - Go to Integrations > Webhooks in your Render Dashboard
   - Create a new webhook with the following settings:
     - Name: "Deploy Database Migration"
     - URL: `https://your-app.onrender.com/webhooks/deploy`
     - Events: Select "Deploy Ended"

3. Set the RENDER_WEBHOOK_SECRET environment variable:
   - In your Render service dashboard, go to Environment
   - Add a new Secret File with:
     - Key: `RENDER_WEBHOOK_SECRET`
     - Value: A secure random string (make this very strong)

4. Testing the webhook setup:
   - Use the included test script: `./test_webhook.py --test`
   - Simulate a deploy event: `./test_webhook.py --event deploy_ended`

5. Monitor migration results in your Render logs