# RedBarSushiAI Environment Variables

This document lists all environment variables used by the RedBarSushiAI application.

## Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | None | Yes |
| `SQLALCHEMY_DATABASE_URI` | Alternative to DATABASE_URL | None | Yes if DATABASE_URL not set |
| `FLASK_APP` | Flask application entry point | run.py | No |
| `FLASK_DEBUG` | Enable Flask debug mode | 0 | No |
| `PORT` | Port to run the server on | 8080 | No |
| `BASE_URL` | Base URL of the application | https://redbarsushiai.onrender.com | No |

## Twilio Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID | None | Yes for SMS/voice |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token | None | Yes for SMS/voice |
| `TWILIO_NUMBER` | Twilio phone number | None | Yes for SMS/voice |

## OpenAI Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key | None | Yes for AI features |
| `OPENAI_API_VERSION` | OpenAI API version | None | No |
| `OPENAI_API_TYPE` | OpenAI API type (azure/openai) | None | No |
| `OPENAI_API_BASE` | OpenAI API base URL | None | No |
| `OPENAI_STREAMING` | Enable streaming responses | 1 | No |
| `OPENAI_REALTIME_NO_DISPLAY` | Force headless mode for realtime client | 0 | No |

## Stripe Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `STRIPE_API_KEY` | Stripe API key | None | Yes for payments |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | None | Yes for webhook notifications |
| `STRIPE_PRODUCT_ID` | Default Stripe product ID | None | Yes for payments |

## Redis Configuration (for Celery)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Redis connection string | None | Yes for Celery |
| `CELERY_BROKER_URL` | Celery broker URL (uses REDIS_URL if not set) | REDIS_URL | No |
| `CELERY_RESULT_BACKEND` | Celery result backend URL (uses REDIS_URL if not set) | REDIS_URL | No |
| `CELERY_CONCURRENCY` | Number of Celery worker processes | 2 | No |
| `CELERY_MAX_MEMORY` | Max memory per Celery worker (KB) | 50000 | No |
| `CELERY_PROFILE_MEMORY` | Enable memory profiling for Celery tasks | false | No |

## Webhook Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RENDER_WEBHOOK_SECRET` | Secret for Render webhook validation | None | Yes for webhooks |
| `WEBHOOK_SECRET` | Alternative name for webhook secret | None | No |
| `WEBHOOK_SIGNING_SECRET` | Alternative name for webhook secret | None | No |
| `RENDER_SIGNING_SECRET` | Alternative name for webhook secret | None | No |
| `WEBHOOK_BYPASS_SIGNATURE` | Bypass signature validation in debug mode | false | No |
| `ALLOW_UNSIGNED_WEBHOOKS` | Accept unsigned webhooks (use with caution!) | false | No |

## X11 Display Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DISPLAY` | X11 display identifier | :1 | No |
| `X11_SETUP_SUCCESS` | Indicates if X11 setup was successful | false | No |
| `X11_DISPLAY` | X11 display to use if X11_SETUP_SUCCESS is true | :1 | No |
| `USE_XVFB` | Use Xvfb virtual display server | false | No |
| `PYNPUT_HEADLESS` | Force pynput into headless mode | 1 | No |
| `NO_X11` | Disable X11 requirement | 1 | No |
| `HEADLESS` | Run in headless mode | 1 | No |

## Docker/Render Specific

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DOCKER` | Indicates running in Docker | false | No |
| `RENDER` | Indicates running on Render | false | No |
| `RENDER_SERVICE_ID` | Render service ID | None | No |
| `PROCESS` | Process type (web/celery/celery-beat) | web | No |
| `LOG_LEVEL` | Logging level | INFO | No |

## Using Environment Variables in Development

For local development, you can use a `.env` file to set environment variables:

```
# .env example
DATABASE_URL=postgresql://user:password@localhost:5432/redbar
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_NUMBER=+1...
```

In production environments like Render, set these variables in the environment configuration section.

## Debug Environment for Testing

To enable maximum debug capabilities, you can use:

```
FLASK_DEBUG=1
LOG_LEVEL=DEBUG
WEBHOOK_BYPASS_SIGNATURE=true
ALLOW_UNSIGNED_WEBHOOKS=true
```

**Note**: Do not use these settings in production!