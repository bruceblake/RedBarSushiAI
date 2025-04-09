# Fixing SMS Status Updates with Celery on Render

This guide explains how to fix the SMS status notification issue by properly configuring the Celery worker service on Render.

## Issue Summary

The application is not sending SMS status updates because the Celery worker service is not properly processing the tasks. When `send_order_status_update_task.delay()` is called in `app/routes/order.py`, the task is not being executed by the Celery worker.

## Solution

1. **Temporary Fix (Implemented)**: 
   - Direct execution of the task without Celery
   - This has been implemented by modifying the code to call `send_order_status_update_task()` directly instead of using `.delay()`

2. **Permanent Fix**: 
   - Set up a proper Celery worker service on Render
   - Ensure Redis is correctly configured

## Setting Up Celery Worker on Render

### Option 1: Create a New Celery Worker Service

1. Log in to the [Render Dashboard](https://dashboard.render.com)

2. Click "New" → "Web Service"

3. Select your GitHub repository with the RedBarSushiAI code

4. Configure the service:
   - **Name**: `RedBarSushi-Celery-Worker`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `./fix_celery.sh`

5. Set Environment Variables:
   - Copy all environment variables from your main web service
   - Add/update these specific variables:
     ```
     PROCESS=celery
     PYTHONUNBUFFERED=1
     REDIS_URL=redis://your-redis-host:port/db
     CELERY_BROKER_URL=redis://your-redis-host:port/db
     CELERY_RESULT_BACKEND=redis://your-redis-host:port/db
     ```
   
   > **Note**: Replace `your-redis-host:port/db` with your actual Redis server details. If you don't have a Redis instance, create one on Render or use a managed service like Redis Labs.

6. Under Advanced settings:
   - Set Health Check Path to: `/`
   - Set Auto-Deploy to: `Yes`

7. Create the service and wait for deployment to complete

8. Verify it's working by checking the logs

### Option 2: Use Render Blueprint (recommended)

1. Add this `render.yaml` file to your repository:

```yaml
services:
  - type: web
    name: redbarsushi-web
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-class=gevent --workers=1 --threads=4 'run:app'
    envVars:
      - key: PROCESS
        value: web
      - key: PYTHONUNBUFFERED
        value: 1
      - key: REDIS_URL
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      # Add all other environment variables needed

  - type: worker
    name: redbarsushi-celery
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A celery_app worker --loglevel=INFO
    envVars:
      - key: PROCESS
        value: celery
      - key: PYTHONUNBUFFERED
        value: 1
      - key: REDIS_URL
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          name: redbarsushi-redis
          type: redis
          property: connectionString
      # Copy all other environment variables from web service

  - type: redis
    name: redbarsushi-redis
    ipAllowList:
      - source: 0.0.0.0/0
        description: everywhere
    plan: free
```

2. Deploy using this blueprint:
   - Go to the Render Dashboard
   - Click "New" → "Blueprint"
   - Select your repository
   - Follow the prompts to deploy all services
   
### Option 3: Update Existing Celery Service

If you already have a Celery worker service on Render:

1. Go to the Render Dashboard and navigate to your Celery worker service
2. Check if `PROCESS=celery` is set in Environment Variables 
3. Verify Redis configuration is correct:
   - Ensure `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` all have proper URLs
   - They should all start with `redis://`
4. Update the Start Command to:
   ```
   ./fix_celery.sh
   ```
   Or alternatively:
   ```
   celery -A celery_app worker --loglevel=INFO --concurrency=2 --max-memory-per-child=50000
   ```
5. Save changes and deploy

## Verifying the Fix

Once the Celery worker is running properly:

1. Revert the code changes in `app/routes/order.py` to use `.delay()` again:
   ```python
   # Replace direct task calls:
   send_order_status_update_task(order_id, status_message, location_id=order_record.location_id)
   
   # With the original async version:
   send_order_status_update_task.delay(order_id, status_message, location_id=order_record.location_id)
   ```

2. Commit and deploy the changes

3. Test the SMS functionality by placing a test order or updating an existing order's status

## Troubleshooting

If the issues persist:

1. Check Celery worker logs for errors:
   - Look for task registration issues
   - Check for Redis connection errors
   
2. Verify Redis connection:
   - Make sure the Redis URL format is correct
   - Test connectivity from your Celery worker

3. Run the diagnostics script:
   ```bash
   python fix_celery_worker.py --action check
   ```

4. If needed, SSH into the Render service to run manual tests:
   ```bash
   render ssh srv-YOUR_CELERY_SERVICE_ID
   
   # Once connected, try:
   python -c "from celery_app import celery; print(celery.tasks.keys())"
   ```