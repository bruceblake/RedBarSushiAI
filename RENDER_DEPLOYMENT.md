# Deploying RedBarSushiAI to Render

This guide provides step-by-step instructions for deploying the RedBarSushiAI application to Render with WebSocket support.

## Prerequisites

1. A [Render account](https://render.com)
2. Your RedBarSushiAI codebase in a GitHub repository
3. Twilio, Stripe, and OpenAI API credentials

## Deployment Steps

### 1. Create a PostgreSQL Database Service on Render

1. Log in to your Render dashboard
2. Go to "New" > "PostgreSQL"
3. Configure your PostgreSQL instance:
   - Name: `redbar-db`
   - Database: `redbar_sushi`
   - User: Leave as auto-generated
   - Region: Choose closest to your customers
   - Plan: Start with the Free tier for testing
4. Click "Create Database"
5. Make note of the connection details (hostname, port, database name, username, password)

### 2. Create a Redis Service (for Celery)

1. Go to "New" > "Redis"
2. Configure Redis:
   - Name: `redbar-redis`
   - Region: Same as your PostgreSQL
   - Plan: Start with the Free tier
3. Click "Create Redis"
4. Make note of the Redis URL

### 3. Deploy the Web Service

1. Go to "New" > "Web Service"
2. Connect your GitHub repository
3. Configure the web service:
   - Name: `redbar-sushi-ai`
   - Environment: Docker
   - Branch: `main` (or your preferred branch)
   - Region: Same as your other services
   - Plan: Start with "Starter" plan (for WebSocket support)
   - Enable Auto-Deploy: Yes
4. Add the following environment variables:
   ```
   DB_USER=[your PostgreSQL username]
   DB_PASSWORD=[your PostgreSQL password]
   DB_NAME=redbar_sushi
   DB_HOST=[your PostgreSQL hostname].render.com
   DB_PORT=5432
   SQLALCHEMY_DATABASE_URI=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
   
   REDIS_URL=[your Redis URL]
   CELERY_BROKER_URL=[your Redis URL]
   CELERY_RESULT_BACKEND=[your Redis URL]
   
   TWILIO_ACCOUNT_SID=[your Twilio SID]
   TWILIO_AUTH_TOKEN=[your Twilio token]
   TWILIO_NUMBER=[your Twilio phone number]
   
   STRIPE_API_KEY=[your Stripe API key]
   STRIPE_PRODUCT_ID=[your Stripe product ID]
   
   APP_SECRET_KEY=[generate a secure random string]
   
   DELIVERECT_API_URL=https://api.staging.deliverect.com/v3/orders
   DELIVERECT_CLIENT_ID=[your Deliverect client ID]
   DELIVERECT_CLIENT_SECRET=[your Deliverect client secret]
   
   OPENAI_API_KEY=[your OpenAI API key]
   
   BASE_URL=https://redbar-sushi-ai.onrender.com
   ```
5. Click "Create Web Service"

### 4. Deploy Celery Worker and Beat (as Background Workers)

1. Go to "New" > "Background Worker"
2. Connect to the same GitHub repository
3. Configure for Celery Worker:
   - Name: `redbar-celery-worker`
   - Environment: Docker
   - Branch: Same as web service
   - Region: Same as other services
   - Plan: Start with "Starter" plan
   - Build Command: Leave blank (uses Dockerfile)
   - Start Command: `/docker-entrypoint.sh`
   - Add the environment variable: `PROCESS=celery`
   - Copy all other environment variables from the web service
4. Click "Create Background Worker"
5. Repeat steps 1-4 for Celery Beat:
   - Name: `redbar-celery-beat`
   - Start Command: `/docker-entrypoint.sh`
   - Environment variable: `PROCESS=celery-beat`

### 5. Update Twilio Webhook URLs

After your services are deployed, update your Twilio phone number to point to your new Render URLs:

1. Voice Webhook: `https://redbar-sushi-ai.onrender.com/`
2. SMS Webhook: `https://redbar-sushi-ai.onrender.com/sms`

## Testing Your Deployment

1. Visit your web service URL to ensure the application is running
2. Try making a test call to your Twilio number
3. Check the logs in the Render dashboard for any errors

## Monitoring and Scaling

- Monitor your application's performance in the Render dashboard
- Scale your services up or down as needed
- Set up custom health checks for more robust monitoring

## Troubleshooting

If you encounter issues:

1. Check the Render logs for errors
2. Ensure all environment variables are set correctly
3. Verify that your database migrations have run
4. Check your Twilio webhook settings
5. Ensure your Dockerfile is correctly configured

For more help, refer to the [Render documentation](https://render.com/docs) or open an issue in the RedBarSushiAI repository.